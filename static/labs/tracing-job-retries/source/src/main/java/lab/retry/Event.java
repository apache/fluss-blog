package lab.retry;

import java.util.Map;
import java.util.Set;
import org.apache.fluss.row.BinaryString;
import org.apache.fluss.row.GenericRow;
import org.apache.fluss.row.InternalRow;

record Event(String job_id, String event_id, int attempt, int step, String event_type,
             String action_id, String payload_digest, long emitted_at_ms, String detail) {
    static final String PROBE_JOB = "offset-probe/ticket-1042";
    static final Set<String> TYPES = Set.of("STARTED", "COMPUTE_STARTED", "COMPUTE_FINISHED",
            "ACTION_REQUESTED", "ACTION_CONFIRMED", "RECONCILED", "HOLD_UNKNOWN", "COMPLETED");

    Event {
        if (!TYPES.contains(event_type)) {
            throw new IllegalArgumentException("Unknown event type: " + event_type);
        }
        if (attempt < 1 || step < 1) {
            throw new IllegalArgumentException("Positive attempt and step required");
        }
        if (!event_id.equals(job_id + "/" + attempt + "/" + step)) {
            throw new IllegalArgumentException("Invalid event identity");
        }
        if (!action_id.equals(actionId(job_id))) {
            throw new IllegalArgumentException("Invalid action identity");
        }
    }

    static String actionId(String job) {
        return job + "/create-followup/v1";
    }

    static Map<String, String> payload(String job) {
        return Map.of("job_id", job, "ticket_id", "ticket-1042",
                "classification", "needs-followup", "title", "Follow up synthetic ticket-1042");
    }

    static Event create(String job, int attempt, int step, String type, String detail) throws Exception {
        return create(job, attempt, step, type, detail, Json.digest(payload(job)));
    }

    static Event create(String job, int attempt, int step, String type, String detail, String digest) {
        return new Event(job, job + "/" + attempt + "/" + step, attempt, step, type,
                actionId(job), digest, System.currentTimeMillis(), detail);
    }

    static Event probe(int step) throws Exception {
        String type = step == 1 ? "STARTED" : "COMPUTE_STARTED";
        return new Event(PROBE_JOB, PROBE_JOB + "/1/" + step, 1, step, type,
                actionId(PROBE_JOB), Json.digest(payload(PROBE_JOB)), 1L, "EXCLUSIVE_END_PROBE_" + step);
    }

    GenericRow row() {
        GenericRow row = new GenericRow(9);
        row.setField(0, BinaryString.fromString(job_id));
        row.setField(1, BinaryString.fromString(event_id));
        row.setField(2, attempt);
        row.setField(3, step);
        row.setField(4, BinaryString.fromString(event_type));
        row.setField(5, BinaryString.fromString(action_id));
        row.setField(6, BinaryString.fromString(payload_digest));
        row.setField(7, emitted_at_ms);
        row.setField(8, BinaryString.fromString(detail));
        return row;
    }

    static Event from(InternalRow row) {
        return new Event(row.getString(0).toString(), row.getString(1).toString(),
                row.getInt(2), row.getInt(3), row.getString(4).toString(),
                row.getString(5).toString(), row.getString(6).toString(), row.getLong(7),
                row.getString(8).toString());
    }
}
