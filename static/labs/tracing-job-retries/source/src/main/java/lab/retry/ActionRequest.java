package lab.retry;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

record ActionRequest(String job_id, String action_id, String payload_digest,
                     String payload_json, Map<String, String> payload) {
    static ActionRequest create(String job, Map<String, String> payload) throws Exception {
        Map<String, String> frozen = Map.copyOf(payload);
        validate(frozen, job);
        return new ActionRequest(job, Event.actionId(job), Json.digest(frozen),
                Json.encode(new TreeMap<>(frozen)), frozen);
    }

    static ActionRequest from(Event intent) throws Exception {
        FlussStore.require(intent.event_type().equals("ACTION_REQUESTED"), "Expected persisted intent");
        Map<String, String> payload = parse(intent.detail());
        validate(payload, intent.job_id());
        String canonical = Json.encode(new TreeMap<>(payload));
        FlussStore.require(canonical.equals(intent.detail()), "Payload is not canonical");
        FlussStore.require(Json.digest(payload).equals(intent.payload_digest()), "Persisted payload digest mismatch");
        FlussStore.require(intent.action_id().equals(Event.actionId(intent.job_id())), "Persisted action binding mismatch");
        return new ActionRequest(intent.job_id(), intent.action_id(), intent.payload_digest(),
                intent.detail(), Map.copyOf(payload));
    }

    private static Map<String, String> parse(String value) throws Exception {
        FlussStore.require(!value.isEmpty(), "Missing persisted canonical payload");
        JsonNode body = Json.decode(value);
        FlussStore.require(body != null, "Missing persisted canonical payload");
        FlussStore.require(body.isObject(), "Persisted payload must be a JSON object");
        Map<String, String> fields = new TreeMap<>();
        Iterator<Map.Entry<String, JsonNode>> entries = body.fields();
        while (entries.hasNext()) {
            Map.Entry<String, JsonNode> entry = entries.next();
            FlussStore.require(entry.getValue().isTextual(), "Payload fields must be strings");
            fields.put(entry.getKey(), entry.getValue().textValue());
        }
        return fields;
    }

    private static void validate(Map<String, String> payload, String job) {
        FlussStore.require(payload.keySet().equals(Set.of("classification", "job_id", "ticket_id", "title")),
                "Persisted payload fields mismatch");
        for (String value : payload.values()) {
            Json.requireAscii(value);
        }
        FlussStore.require(payload.get("job_id").equals(job), "Persisted payload job mismatch");
        FlussStore.require(payload.get("ticket_id").equals("ticket-1042"), "Persisted synthetic ticket mismatch");
        FlussStore.require(job.matches("[A-Za-z0-9_./-]+/ticket-1042"), "Persisted synthetic job mismatch");
        FlussStore.require(payload.get("classification").equals("needs-followup"), "Persisted classification mismatch");
    }

    String envelope() throws Exception {
        return "{\"action_id\":" + Json.encode(action_id) + ",\"payload_digest\":"
                + Json.encode(payload_digest) + ",\"payload\":" + payload_json + "}";
    }
}
