package lab.retry;

import java.util.Map;

final class Worker {
    private final FlussStore store;
    private final Fixture fixture;
    private final String job;
    private final int attempt;
    private final String barrier;
    private int step;
    private String payloadDigest;

    Worker(FlussStore store, Fixture fixture, String job, int attempt, String barrier) {
        this.store = store;
        this.fixture = fixture;
        this.job = job;
        this.attempt = attempt;
        this.barrier = barrier;
    }

    void run(boolean recovering) throws Exception {
        History.Snapshot snapshot = store.snapshot();
        History history = new History(snapshot, job);
        validateAttempt(history, recovering);
        chooseDigest(history);
        Json.emit("REPLAY", history.output(snapshot.end_offset_exclusive()));
        if (history.contains("COMPLETED")) {
            result("COMPLETED");
            return;
        }
        emit("STARTED", "Synthetic ticket-1042; deterministic inference stand-in");
        if (history.contains("ACTION_REQUESTED")) {
            reconcile(history);
            return;
        }
        prepareComputation(history);
        Event intent = emit("ACTION_REQUESTED", Json.encode(new java.util.TreeMap<>(Event.payload(job))));
        pause("B1", "ACTION_REQUESTED future completed; POST /followups not invoked");
        String receipt = fixture.post(ActionRequest.from(intent));
        pause("B2", "Independent service committed; validated receipt received; ACTION_CONFIRMED append not invoked");
        finish(receipt);
    }

    private void validateAttempt(History history, boolean recovering) {
        FlussStore.require(attempt == history.maxAttempt() + 1, "Attempt must increment from Fluss history");
        if (recovering) {
            FlussStore.require(history.maxAttempt() > 0, "recover requires recorded previous attempt");
        } else {
            FlussStore.require(history.maxAttempt() == 0, "worker requires a new job; use recover");
        }
    }

    private void chooseDigest(History history) throws Exception {
        if (history.contains("ACTION_REQUESTED")) {
            payloadDigest = history.latest("ACTION_REQUESTED").orElseThrow().payload_digest();
            return;
        }
        payloadDigest = Json.digest(Event.payload(job));
    }

    private void prepareComputation(History history) throws Exception {
        if (history.contains("COMPUTE_FINISHED")) {
            FlussStore.require(history.latest("COMPUTE_FINISHED").orElseThrow().detail().equals("needs-followup"),
                    "Persisted classification is not the fixture stand-in result");
            return;
        }
        emit("COMPUTE_STARTED", "deterministic synthetic classifier");
        String classification = fixture.compute(job, attempt);
        pause("A", "Independent compute completed; COMPUTE_FINISHED append not invoked");
        emit("COMPUTE_FINISHED", classification);
    }

    private void reconcile(History history) throws Exception {
        Event intent = history.latest("ACTION_REQUESTED").orElseThrow();
        ActionRequest request = ActionRequest.from(intent);
        Fixture.Lookup lookup = fixture.lookup(request.job_id(), request.payload_digest());
        if (lookup.state().equals("UNKNOWN")) {
            emit("HOLD_UNKNOWN", lookup.receipt());
            result("HOLD_UNKNOWN");
            return;
        }
        emit("RECONCILED", lookup.state());
        String receipt = lookup.receipt();
        if (lookup.state().equals("ABSENT_ATOMIC")) {
            receipt = fixture.post(request);
        }
        finish(receipt);
    }

    private void finish(String receipt) throws Exception {
        emit("ACTION_CONFIRMED", receipt);
        emit("COMPLETED", "Synthetic follow-up receipt persisted");
        result("COMPLETED");
    }

    private Event emit(String type, String detail) throws Exception {
        step++;
        Event event = Event.create(job, attempt, step, type, detail, payloadDigest);
        store.append(event);
        return event;
    }

    private void pause(String point, String boundary) throws Exception {
        if (!barrier.equals(point)) {
            return;
        }
        Json.emit("BARRIER", Map.of("barrier", point, "boundary", boundary,
                "pid", ProcessHandle.current().pid(), "job_id", job, "attempt", attempt));
        while (true) {
            Thread.sleep(1000);
        }
    }

    private void result(String state) throws Exception {
        Json.emit("RESULT", Map.of("state", state, "job_id", job, "attempt", attempt,
                "pid", ProcessHandle.current().pid(), "restart_authority", "fresh Fluss bounded replay"));
    }
}
