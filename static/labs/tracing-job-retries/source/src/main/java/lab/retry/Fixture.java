package lab.retry;

import com.fasterxml.jackson.databind.JsonNode;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;

final class Fixture {
    static final String CONTRACT = "fixture-atomic-action-id-payload-v1";
    record Lookup(String state, String receipt) {}
    private final String base;
    private final Duration timeout;
    private final HttpClient client;

    Fixture(String base, int seconds) {
        URI uri = URI.create(base);
        FlussStore.require("http".equals(uri.getScheme()), "Fixture must use local HTTP");
        FlussStore.require("127.0.0.1".equals(uri.getHost()), "Fixture must bind/use 127.0.0.1");
        FlussStore.require(uri.getRawPath().isEmpty(), "Fixture base must have no path");
        this.base = base;
        timeout = Duration.ofSeconds(seconds);
        client = HttpClient.newBuilder().connectTimeout(timeout).build();
    }

    private HttpResponse<String> send(String method, String path, String body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(base + path)).timeout(timeout)
                .header("Content-Type", "application/json");
        if (body == null) {
            builder.GET();
        } else {
            builder.method(method, HttpRequest.BodyPublishers.ofString(body));
        }
        return client.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    String compute(String job, int attempt) throws Exception {
        HttpResponse<String> response = send("POST", "/compute",
                Json.encode(Map.of("job_id", job, "attempt", attempt, "ticket_id", "ticket-1042")));
        FlussStore.require(response.statusCode() == 200, "Compute HTTP " + response.statusCode());
        JsonNode body = Json.decode(response.body());
        FlussStore.require(body.path("invocation_id").asLong() > 0, "Missing independent compute receipt");
        FlussStore.require(body.path("classification").asText().equals("needs-followup"),
                "Unexpected stand-in classification");
        return body.path("classification").asText();
    }

    String post(ActionRequest request) throws Exception {
        HttpResponse<String> response = send("POST", "/followups", request.envelope());
        FlussStore.require(response.statusCode() == 200 || response.statusCode() == 201,
                "Action HTTP " + response.statusCode() + ": " + response.body());
        validateReceipt(response.body(), request.job_id(), request.payload_digest());
        return response.body();
    }

    Lookup lookup(String job, String digest) throws Exception {
        HttpResponse<String> response;
        try {
            response = send("GET", "/followups/" + URLEncoder.encode(Event.actionId(job), StandardCharsets.UTF_8), null);
        } catch (IOException unavailable) {
            return new Lookup("UNKNOWN", unavailable.toString());
        }
        if (response.statusCode() == 503) {
            return new Lookup("UNKNOWN", "Receipt lookup HTTP 503");
        }
        if (response.statusCode() == 200) {
            validateReceipt(response.body(), job, digest);
            return new Lookup("PRESENT", response.body());
        }
        if (response.statusCode() == 404) {
            validateNegative(response.body(), job);
            return new Lookup("ABSENT_ATOMIC", "Negative receipt under " + CONTRACT);
        }
        throw new IllegalStateException("Receipt lookup HTTP " + response.statusCode());
    }

    private static void validateNegative(String value, String job) throws Exception {
        JsonNode body = Json.decode(value);
        FlussStore.require(body.path("contract").asText().equals(CONTRACT), "Negative lookup lacks atomic contract");
        FlussStore.require(body.path("action_id").asText().equals(Event.actionId(job)), "Negative lookup key mismatch");
        FlussStore.require(body.path("absent").asBoolean(false), "Receipt is not explicitly absent");
    }

    private static void validateReceipt(String value, String job, String digest) throws Exception {
        JsonNode body = Json.decode(value);
        FlussStore.require(body.path("contract").asText().equals(CONTRACT), "Unknown receipt contract");
        FlussStore.require(body.path("action_id").asText().equals(Event.actionId(job)), "Receipt key mismatch");
        FlussStore.require(body.path("payload_digest").asText().equals(digest), "Receipt immutable digest mismatch");
        FlussStore.require(!body.path("receipt_id").asText().isEmpty(), "Receipt ID missing");
    }
}
