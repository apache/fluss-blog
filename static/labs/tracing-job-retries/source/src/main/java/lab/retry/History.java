package lab.retry;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

final class History {
    record Raw(int bucket, long offset, Event event) {}
    record Snapshot(long end_offset_exclusive, List<Raw> records) {}
    private final List<Raw> raw;
    private final List<Event> logical;

    History(Snapshot snapshot, String job) throws Exception {
        raw = snapshot.records().stream().filter(r -> r.event().job_id().equals(job)).toList();
        Map<String, Event> seen = new LinkedHashMap<>();
        for (Raw record : raw) {
            Event event = record.event();
            Event previous = seen.putIfAbsent(event.event_id(), event);
            if (previous != null && !previous.equals(event)) {
                throw new IllegalStateException("event identity conflict: " + event.event_id());
            }
        }
        logical = new ArrayList<>(seen.values());
        validateSequence();
        validateDigests(job);
    }

    private void validateDigest(Event event, String expectedDigest) {
        if (!event.payload_digest().equals(expectedDigest)) {
            throw new IllegalStateException("Event immutable payload digest mismatch");
        }
    }

    private void validateDigests(String job) throws Exception {
        String initialDigest = Json.digest(Event.payload(job));
        ActionRequest request = null;
        for (Event event : logical) {
            if (event.event_type().equals("ACTION_REQUESTED")) {
                ActionRequest recorded = ActionRequest.from(event);
                if (request != null) {
                    FlussStore.require(recorded.payload_json().equals(request.payload_json()),
                            "Action immutable payload changed after persisted intent");
                }
                request = recorded;
            }
            String expected = request == null ? initialDigest : request.payload_digest();
            validateDigest(event, expected);
        }
    }

    private void validateSequence() {
        int attempt = 0;
        int step = 0;
        for (Event event : logical) {
            if (event.attempt() < attempt) {
                throw new IllegalStateException("Attempt order regressed");
            }
            if (event.attempt() != attempt) {
                attempt = event.attempt();
                step = 0;
            }
            if (event.step() != step + 1) {
                throw new IllegalStateException("Missing attempt prefix or step gap");
            }
            step = event.step();
        }
    }

    Optional<Event> latest(String type) {
        return logical.stream().filter(e -> e.event_type().equals(type)).reduce((a, b) -> b);
    }

    boolean contains(String type) {
        return latest(type).isPresent();
    }

    int maxAttempt() {
        return logical.stream().mapToInt(Event::attempt).max().orElse(0);
    }

    String state() {
        if (logical.isEmpty()) {
            return "NEW";
        }
        return logical.get(logical.size() - 1).event_type();
    }

    Map<String, Object> output(long end) {
        return Map.of("end_offset_exclusive", end, "raw_count", raw.size(), "logical_count", logical.size(),
                "raw", raw, "logical", logical, "state", state());
    }
}
