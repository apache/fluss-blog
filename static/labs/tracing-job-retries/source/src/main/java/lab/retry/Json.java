package lab.retry;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonParser;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.TreeMap;

final class Json {
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
            .disable(JsonGenerator.Feature.WRITE_HEX_UPPER_CASE);

    static String encode(Object value) throws Exception {
        return MAPPER.writeValueAsString(value);
    }

    static JsonNode decode(String value) throws Exception {
        return MAPPER.readTree(value);
    }

    static String digest(Map<String, String> payload) throws Exception {
        byte[] bytes = encode(new TreeMap<>(payload)).getBytes(StandardCharsets.UTF_8);
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    static void requireAscii(String value) {
        for (int i = 0; i < value.length(); i++) {
            FlussStore.require(value.charAt(i) < 128, "Payload fields must be ASCII strings");
        }
    }

    static void emit(String kind, Map<String, ?> value) throws Exception {
        Map<String, Object> message = new TreeMap<>();
        message.putAll(value);
        message.put("kind", kind);
        System.out.println(encode(message));
        System.out.flush();
    }
}
