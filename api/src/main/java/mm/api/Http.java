package mm.api;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.sun.net.httpserver.HttpExchange;

import java.io.IOException;
import java.io.OutputStream;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.sql.SQLException;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** The answers (JSON, UTF-8) and the errors of the service. */
final class Http {
    static final Gson GSON = new GsonBuilder().serializeNulls().disableHtmlEscaping().create();
    private static final Pattern MM_ERROR = Pattern.compile("(MM-1\\d\\d): ([^\\n]*)");

    private Http() {
    }

    /** an error with its HTTP status and a short code, for the client */
    static final class Fail extends RuntimeException {
        final int status;
        final String code;

        Fail(int status, String code, String message) {
            super(message);
            this.status = status;
            this.code = code;
        }
    }

    static Map<String, String> query(HttpExchange ex) {
        Map<String, String> q = new HashMap<>();
        String raw = ex.getRequestURI().getRawQuery();
        if (raw == null) {
            return q;
        }
        for (String part : raw.split("&")) {
            int i = part.indexOf('=');
            String k = URLDecoder.decode(i < 0 ? part : part.substring(0, i), StandardCharsets.UTF_8);
            String v = i < 0 ? "" : URLDecoder.decode(part.substring(i + 1), StandardCharsets.UTF_8);
            q.put(k, v);
        }
        return q;
    }

    static LocalDate date(Map<String, String> q, String name, LocalDate fallback) {
        String v = q.get(name);
        if (v == null || v.isBlank()) {
            return fallback;
        }
        try {
            return LocalDate.parse(v);
        } catch (DateTimeParseException e) {
            throw new Fail(400, "bad_date", name + ": YYYY-MM-DD");
        }
    }

    static int number(Map<String, String> q, String name, int fallback, int min, int max) {
        String v = q.get(name);
        if (v == null || v.isBlank()) {
            return fallback;
        }
        try {
            return Math.max(min, Math.min(max, Integer.parseInt(v)));
        } catch (NumberFormatException e) {
            throw new Fail(400, "bad_number", name + ": a number");
        }
    }

    static long id(String s) {
        try {
            return Long.parseLong(s);
        } catch (NumberFormatException e) {
            throw new Fail(404, "not_found", "no such id: " + s);
        }
    }

    /** the JSON object of a POST (at most 64 KB) */
    @SuppressWarnings("unchecked")
    static Map<String, Object> body(HttpExchange ex) throws IOException {
        byte[] b = ex.getRequestBody().readNBytes(64 * 1024 + 1);
        if (b.length > 64 * 1024) {
            throw new Fail(413, "too_large", "at most 64 KB");
        }
        if (b.length == 0) {
            return new HashMap<>();
        }
        try {
            Object o = GSON.fromJson(new String(b, StandardCharsets.UTF_8), Object.class);
            if (o instanceof Map<?, ?> m) {
                return (Map<String, Object>) m;
            }
        } catch (com.google.gson.JsonParseException e) {
            // below
        }
        throw new Fail(400, "bad_json", "a JSON object");
    }

    static String text(Map<String, Object> body, String name, boolean required) {
        Object v = body.get(name);
        if (v == null || String.valueOf(v).isBlank()) {
            if (required) {
                throw new Fail(400, "missing", name);
            }
            return null;
        }
        return String.valueOf(v);
    }

    static java.math.BigDecimal decimal(Map<String, Object> body, String name, java.math.BigDecimal fallback) {
        Object v = body.get(name);
        if (v == null) {
            return fallback;
        }
        try {
            return new java.math.BigDecimal(String.valueOf(v));
        } catch (NumberFormatException e) {
            throw new Fail(400, "bad_number", name + ": a number");
        }
    }

    static void send(HttpExchange ex, int status, Object body) throws IOException {
        byte[] b = GSON.toJson(body).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        ex.getResponseHeaders().set("Cache-Control", "no-store");
        ex.getResponseHeaders().set("X-Content-Type-Options", "nosniff");
        ex.sendResponseHeaders(status, b.length);
        try (OutputStream o = ex.getResponseBody()) {
            o.write(b);
        }
    }

    /**
     * an error of the database: MM-1xx of MM_CORE / MM_LEDGER / MM_AUTH as 400 with its words (the login:
     * MM-177 wrong name or password and MM-179 no session as 401, MM-178 locked as 423); else 500
     */
    static Fail fromSql(SQLException e) {
        Matcher m = MM_ERROR.matcher(String.valueOf(e.getMessage()));
        if (m.find()) {
            int status = switch (m.group(1)) {
                case "MM-177", "MM-179" -> 401;
                case "MM-178" -> 423;
                default -> 400;
            };
            return new Fail(status, m.group(1), m.group(2).trim());
        }
        System.err.println("== mm-api: " + e);
        return new Fail(500, "db_error", "database error");
    }

    static Map<String, Object> error(String code, String message) {
        Map<String, Object> m = new HashMap<>();
        m.put("error", code);
        m.put("message", message);
        return m;
    }
}
