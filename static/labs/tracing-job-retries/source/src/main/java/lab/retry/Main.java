package lab.retry;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class Main {
    private static final Set<String> COMMANDS = Set.of("init", "worker", "inspect", "recover",
            "duplicate-event", "conflict-event", "conflict-action", "invalid-intent", "frozen-intent");
    private static final Set<String> OPTIONS = Set.of("--bootstrap", "--service", "--timeout-seconds",
            "--job", "--attempt", "--barrier", "--raw-only", "--fault", "--title");

    public static void main(String[] args) throws Exception {
        try {
            dispatch(args);
        } catch (Exception failure) {
            Json.emit("FAILURE", Map.of("error", failure.toString()));
            failure.printStackTrace(System.err);
            System.exit(1);
        }
    }

    private static Map<String, String> options(String[] args) {
        FlussStore.require(args.length > 0, "Command required: init, worker, inspect, recover");
        FlussStore.require(COMMANDS.contains(args[0]), "Unknown command: " + args[0]);
        FlussStore.require(args.length % 2 == 1, "Options must have explicit values");
        Map<String, String> values = new HashMap<>();
        values.put("--bootstrap", "localhost:9123");
        values.put("--service", "http://127.0.0.1:18080");
        values.put("--timeout-seconds", "60");
        values.put("--barrier", "NONE");
        values.put("--raw-only", "false");
        Set<String> seen = new java.util.HashSet<>();
        for (int i = 1; i < args.length; i += 2) {
            FlussStore.require(OPTIONS.contains(args[i]), "Unknown option: " + args[i]);
            FlussStore.require(seen.add(args[i]), "Duplicate option: " + args[i]);
            values.put(args[i], args[i + 1]);
        }
        return values;
    }

    private static void dispatch(String[] args) throws Exception {
        Map<String, String> values = options(args);
        int timeout = Integer.parseInt(values.get("--timeout-seconds"));
        FlussStore.require(timeout >= 30 && timeout <= 600, "Timeout must be 30..600 seconds");
        try (FlussStore store = new FlussStore(values.get("--bootstrap"), timeout)) {
            if (args[0].equals("init")) {
                store.initialize();
                return;
            }
            String job = requiredJob(values);
            executeJobCommand(store, values, job, timeout, args[0]);
        }
    }

    private static void executeJobCommand(FlussStore store, Map<String, String> values,
                                           String job, int timeout, String command) throws Exception {
        switch (command) {
            case "inspect" -> inspect(store, job, values);
            case "duplicate-event", "conflict-event" -> duplicate(store, job, command);
            case "conflict-action" -> conflictAction(values, job, timeout);
            case "invalid-intent" -> invalidIntent(store, job, values.get("--fault"));
            case "frozen-intent" -> frozenIntent(store, job, values.get("--title"));
            case "worker", "recover" -> worker(store, values, job, timeout, command);
            default -> throw new IllegalArgumentException("Unexpected command");
        }
    }

    private static String requiredJob(Map<String, String> values) {
        String job = values.get("--job");
        FlussStore.require(job != null, "--job required");
        FlussStore.require(job.matches("[A-Za-z0-9_./-]+/ticket-1042"), "Use synthetic job ending /ticket-1042");
        FlussStore.require(!job.equals(Event.PROBE_JOB), "Offset probe job is reserved");
        return job;
    }

    private static void worker(FlussStore store, Map<String, String> values,
                               String job, int timeout, String command) throws Exception {
        FlussStore.require(values.containsKey("--attempt"), "--attempt required");
        String barrier = values.get("--barrier");
        FlussStore.require(Set.of("NONE", "A", "B1", "B2").contains(barrier), "Unknown barrier");
        int attempt = Integer.parseInt(values.get("--attempt"));
        Fixture fixture = new Fixture(values.get("--service"), timeout);
        new Worker(store, fixture, job, attempt, barrier).run(command.equals("recover"));
    }

    private static void inspect(FlussStore store, String job, Map<String, String> values) throws Exception {
        History.Snapshot snapshot = store.snapshot();
        String rawOnly = values.get("--raw-only");
        FlussStore.require(Set.of("true", "false").contains(rawOnly), "--raw-only must be true or false");
        if (rawOnly.equals("true")) {
            List<History.Raw> raw = snapshot.records().stream().filter(r -> r.event().job_id().equals(job)).toList();
            Json.emit("RESULT", Map.of("state", "RAW_ONLY", "raw", raw, "raw_count", raw.size(),
                    "end_offset_exclusive", snapshot.end_offset_exclusive()));
            return;
        }
        History history = new History(snapshot, job);
        Json.emit("RESULT", history.output(snapshot.end_offset_exclusive()));
    }

    private static Event duplicateEvent(String job, String detail) throws Exception {
        return new Event(job, job + "/1/1", 1, 1, "STARTED", Event.actionId(job),
                Json.digest(Event.payload(job)), 1700000000000L, detail);
    }

    private static void duplicate(FlussStore store, String job, String command) throws Exception {
        store.snapshot();
        if (command.equals("conflict-event")) {
            store.append(duplicateEvent(job, "changed immutable detail"));
        } else {
            Event event = duplicateEvent(job, "identical application event");
            store.append(event);
            store.append(event);
        }
        Json.emit("RESULT", Map.of("state", "APPENDED", "separate_writer_lifetimes", true));
    }

    private static void conflictAction(Map<String, String> values, String job, int timeout) throws Exception {
        Map<String, String> payload = new HashMap<>(Event.payload(job));
        payload.put("title", "Conflicting synthetic follow-up title");
        new Fixture(values.get("--service"), timeout).post(ActionRequest.create(job, payload));
        throw new IllegalStateException("Conflicting action unexpectedly accepted");
    }

    private static void invalidIntent(FlussStore store, String job, String fault) throws Exception {
        FlussStore.require(fault != null, "--fault required for invalid-intent");
        store.snapshot();
        Map<String, String> payload = new HashMap<>(Event.payload(job));
        String detail = Json.encode(new java.util.TreeMap<>(payload));
        String digest = Json.digest(payload);
        switch (fault) {
            case "missing" -> detail = "";
            case "noncanonical" -> detail = " " + detail;
            case "tampered" -> {
                payload.put("title", "tampered immutable title");
                detail = Json.encode(new java.util.TreeMap<>(payload));
            }
            case "digest" -> digest = "0".repeat(64);
            case "binding" -> {
                payload.put("job_id", "wrong-binding/ticket-1042");
                detail = Json.encode(new java.util.TreeMap<>(payload));
            }
            default -> throw new IllegalArgumentException("Unknown invalid-intent fault");
        }
        store.append(Event.create(job, 1, 1, "STARTED", "Deliberately invalid request fixture"));
        store.append(new Event(job, job + "/1/2", 1, 2, "ACTION_REQUESTED", Event.actionId(job),
                digest, System.currentTimeMillis(), detail));
        Json.emit("RESULT", Map.of("state", "INVALID_FIXTURE_APPENDED", "fault", fault));
    }

    private static void frozenIntent(FlussStore store, String job, String title) throws Exception {
        FlussStore.require(title != null, "--title required for frozen-intent");
        store.snapshot();
        Map<String, String> payload = new HashMap<>(Event.payload(job));
        payload.put("title", title);
        ActionRequest request = ActionRequest.create(job, payload);
        store.append(Event.create(job, 1, 1, "STARTED", "Positive persisted-request fixture"));
        store.append(Event.create(job, 1, 2, "ACTION_REQUESTED", request.payload_json(), request.payload_digest()));
        Json.emit("RESULT", Map.of("state", "FROZEN_FIXTURE_APPENDED", "pid", ProcessHandle.current().pid()));
    }
}
