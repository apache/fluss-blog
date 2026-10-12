package lab.retry;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.apache.fluss.client.Connection;
import org.apache.fluss.client.ConnectionFactory;
import org.apache.fluss.client.admin.Admin;
import org.apache.fluss.client.admin.OffsetSpec;
import org.apache.fluss.client.table.Table;
import org.apache.fluss.client.table.scanner.ScanRecord;
import org.apache.fluss.client.table.scanner.log.LogScanner;
import org.apache.fluss.client.table.scanner.log.ScanRecords;
import org.apache.fluss.client.table.writer.AppendResult;
import org.apache.fluss.client.table.writer.AppendWriter;
import org.apache.fluss.config.Configuration;
import org.apache.fluss.metadata.DatabaseDescriptor;
import org.apache.fluss.metadata.Schema;
import org.apache.fluss.metadata.TableDescriptor;
import org.apache.fluss.metadata.TableInfo;
import org.apache.fluss.metadata.TableBucket;
import org.apache.fluss.metadata.TablePath;
import org.apache.fluss.types.DataTypes;

final class FlussStore implements AutoCloseable {
    private static final TablePath PATH = TablePath.of("retry_lab", "job_events");
    private final Connection connection;
    private final Admin admin;
    private final int timeout;

    FlussStore(String bootstrap, int timeout) throws Exception {
        Configuration config = new Configuration();
        config.setString("bootstrap.servers", bootstrap);
        config.setString("client.writer.acks", "all");
        config.setString("client.writer.retries", "1");
        config.setString("client.request-timeout", "10s");
        config.setString("client.connect-timeout", "10s");
        config.setString("client.writer.buffer.wait-timeout", "10s");
        connection = ConnectionFactory.createConnection(config);
        admin = connection.getAdmin();
        this.timeout = timeout;
    }

    private static Schema schema() {
        return Schema.newBuilder().column("job_id", DataTypes.STRING())
                .column("event_id", DataTypes.STRING()).column("attempt", DataTypes.INT())
                .column("step", DataTypes.INT()).column("event_type", DataTypes.STRING())
                .column("action_id", DataTypes.STRING()).column("payload_digest", DataTypes.STRING())
                .column("emitted_at_ms", DataTypes.BIGINT()).column("detail", DataTypes.STRING()).build();
    }

    private Table table() throws Exception {
        TableInfo info = admin.getTableInfo(PATH).get(timeout, TimeUnit.SECONDS);
        require(info.getRowType().equals(schema().getRowType()), "Schema mismatch");
        require(!info.hasPrimaryKey(), "Expected append Log Table without primary key");
        require(!info.isPartitioned(), "Expected nonpartitioned table");
        require(info.getNumBuckets() == 1, "Expected one bucket");
        require(info.getBucketKeys().equals(List.of("job_id")), "Expected job_id bucket key");
        return connection.getTable(PATH);
    }

    void initialize() throws Exception {
        admin.createDatabase("retry_lab", DatabaseDescriptor.builder().build(), true)
                .get(timeout, TimeUnit.SECONDS);
        TableDescriptor descriptor = TableDescriptor.builder().schema(schema())
                .distributedBy(1, "job_id").property("table.log.ttl", "0ms").build();
        admin.createTable(PATH, descriptor, false).get(timeout, TimeUnit.SECONDS);
        require(offset(new OffsetSpec.EarliestSpec()) == 0, "Fresh table earliest must be 0");
        require(offset(new OffsetSpec.LatestSpec()) == 0, "Fresh table latest must be 0");
        append(Event.probe(1));
        require(offset(new OffsetSpec.LatestSpec()) == 1, "First append latest must be exclusive 1");
        History.Snapshot first = scanTo(1);
        require(first.records().get(0).event().equals(Event.probe(1)), "First probe read differs");
        append(Event.probe(2));
        require(offset(new OffsetSpec.LatestSpec()) == 2, "Second append latest must be exclusive 2");
        History.Snapshot second = scanTo(2);
        validateProbe(second);
        Json.emit("RESULT", Map.of("state", "INITIALIZED", "probe", second,
                "exclusive_end_verified", true, "client_writer_acks", "all", "log_ttl", "0ms"));
    }

    void append(Event event) throws Exception {
        try (Table activeTable = table()) {
            AppendWriter writer = activeTable.newAppend().createWriter();
            CompletableFuture<AppendResult> appendFuture = writer.append(event.row());
            writer.flush();
            appendFuture.get(timeout, TimeUnit.SECONDS);
        }
        Json.emit("ACK", Map.of("event_id", event.event_id(), "event_type", event.event_type(),
                "attempt", event.attempt(), "pid", ProcessHandle.current().pid()));
    }

    private long offset(OffsetSpec spec) throws Exception {
        return admin.listOffsets(PATH, Collections.singletonList(0), spec)
                .bucketResult(0).get(timeout, TimeUnit.SECONDS);
    }

    History.Snapshot snapshot() throws Exception {
        long end = offset(new OffsetSpec.LatestSpec());
        require(end >= 2, "Initial exclusive-end probe missing; run init on a fresh table");
        History.Snapshot snapshot = scanTo(end);
        validateProbe(snapshot);
        return snapshot;
    }

    private History.Snapshot scanTo(long end) throws Exception {
        require(offset(new OffsetSpec.EarliestSpec()) == 0, "Retention gap: earliest is not zero");
        List<History.Raw> records = new ArrayList<>();
        long progress = 0;
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(timeout);
        Table activeTable = table();
        TableBucket expectedBucket = new TableBucket(activeTable.getTableInfo().getTableId(), 0);
        try (LogScanner scanner = activeTable.newScan().createLogScanner()) {
            scanner.subscribeFromBeginning(0);
            while (progress < end) {
                require(System.nanoTime() < deadline, "Bounded replay timed out before captured latest");
                ScanRecords batch = scanner.poll(Duration.ofMillis(250));
                collect(batch, records, end);
                progress = consumedProgress(batch, expectedBucket, progress, end, records.size());
            }
        }
        require(records.size() == end, "Required raw prefix missing despite exclusive scanner progress");
        require(offset(new OffsetSpec.LatestSpec()) == end, "Writer active during recovery snapshot");
        require(offset(new OffsetSpec.EarliestSpec()) == 0, "Retention changed during replay");
        return new History.Snapshot(end, List.copyOf(records));
    }

    private static long consumedProgress(ScanRecords batch, TableBucket expectedBucket,
                                         long progress, long end, long rawCount) {
        require(batch.buckets().size() <= 1, "Unexpected buckets in one-bucket replay");
        for (TableBucket bucket : batch.buckets()) {
            require(bucket.equals(expectedBucket), "Unexpected table bucket in replay");
            Long next = batch.consumedUpToOffset(bucket);
            require(next != null, "Missing exclusive scanner progress for polled bucket");
            require(next >= progress, "Exclusive scanner progress regressed");
            require(next <= end, "Exclusive scanner progress crossed captured latest");
            require(next >= rawCount, "Exclusive scanner progress precedes observed raw rows");
            progress = next;
        }
        return progress;
    }

    private static void collect(ScanRecords batch, List<History.Raw> records, long end) {
        for (ScanRecord record : batch) {
            require(record.logOffset() < end, "Read crossed captured latest; writer was not stopped");
            require(record.logOffset() == records.size(), "Missing prefix or noncontiguous log offset");
            records.add(new History.Raw(0, record.logOffset(), Event.from(record.getRow())));
        }
    }

    private static void validateProbe(History.Snapshot snapshot) throws Exception {
        require(snapshot.records().size() >= 2, "Offset probe prefix missing");
        require(snapshot.records().get(0).event().equals(Event.probe(1)), "Probe first row mismatch");
        require(snapshot.records().get(1).event().equals(Event.probe(2)), "Probe second row mismatch");
    }

    static void require(boolean condition, String error) {
        if (!condition) {
            throw new IllegalStateException(error);
        }
    }

    @Override
    public void close() throws Exception {
        try {
            admin.close();
        } finally {
            connection.close();
        }
    }
}
