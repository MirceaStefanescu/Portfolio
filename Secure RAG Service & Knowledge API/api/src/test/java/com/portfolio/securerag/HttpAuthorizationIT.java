package com.portfolio.securerag;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.function.Executable;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import static org.junit.jupiter.api.Assertions.*;

/** Explicit full HTTP acceptance with a temporary Qdrant fixture and synthetic credentials. */
@SpringBootTest(classes = SecureRagApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"server.address=127.0.0.1", "rag.provider=local", "qdrant.api-key=",
                "rag.provider-base-url=http://127.0.0.1:1", "rag.provider-api-key=unused-fixture",
                "rag.chunk-size=200", "rag.chunk-overlap=20", "rag.vector-size=64",
                "security.dev-api-key=" + HttpAuthorizationIT.DEV_KEY,
                "security.jwt.secret=" + HttpAuthorizationIT.SIGNING_TEXT,
                "security.jwt.issuer=http-audit-fixture", "security.jwt.ttl-seconds=120",
                "logging.level.com.portfolio.securerag=WARN"})
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class HttpAuthorizationIT {
    static final String DEV_KEY = "fixture-only-dev-key-for-isolated-http-audit-00001";
    static final String SIGNING_TEXT = "fixture-only-signing-value-for-isolated-http-audit-00000000000001";
    static final ObjectMapper JSON = new ObjectMapper();
    static final String COLLECTION = "codex_http_" + UUID.randomUUID().toString().replace("-", "");
    static final String QDRANT = isolatedQdrant();
    @LocalServerPort int port;
    final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    String admin, user, outsider;

    static String isolatedQdrant() {
        String value = Objects.requireNonNull(System.getenv("RAG_QDRANT_NATIVE_URL"), "temporary Qdrant URL required");
        URI uri = URI.create(value);
        if (!"http".equals(uri.getScheme()) || !"127.0.0.1".equals(uri.getHost()) || uri.getPort() <= 0) {
            throw new IllegalArgumentException("Qdrant fixture must be HTTP loopback with an explicit port");
        }
        return value;
    }
    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry properties) {
        properties.add("qdrant.url", () -> QDRANT);
        properties.add("qdrant.collection", () -> COLLECTION);
    }
    record Reply(int status, JsonNode json, HttpHeaders headers, String raw) {}
    Reply request(String method, String path, Object body, Map<String, String> headers) throws Exception {
        String content = body == null ? null : body instanceof String s ? s : JSON.writeValueAsString(body);
        var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                .timeout(Duration.ofSeconds(8));
        headers.forEach(request::header);
        if (content != null) request.header("Content-Type", "application/json");
        request.method(method, content == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(content));
        var response = http.send(request.build(), HttpResponse.BodyHandlers.ofString());
        JsonNode parsed;
        try { parsed = JSON.readTree(response.body()); } catch (Exception invalidJson) { parsed = JSON.nullNode(); }
        return new Reply(response.statusCode(), parsed == null ? JSON.nullNode() : parsed, response.headers(), response.body());
    }
    Map<String, String> bearer(String token) { return Map.of("Authorization", "Bearer " + token); }
    String mint(String actor, List<String> roles) throws Exception {
        var body = new HashMap<String, Object>(); body.put("username", actor); body.put("roles", roles);
        var response = request("POST", "/api/auth/token", body, Map.of("X-Dev-Key", DEV_KEY));
        assertEquals(200, response.status(), "token endpoint");
        assertEquals(actor, response.json().path("username").asText());
        assertTrue(response.headers().allValues("Set-Cookie").isEmpty());
        return response.json().path("token").asText();
    }
    long pointCount() throws Exception {
        var request = HttpRequest.newBuilder(URI.create(QDRANT + "/collections/" + COLLECTION + "/points/count"))
                .timeout(Duration.ofSeconds(3)).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString("{\"exact\":true}")).build();
        var response = http.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
        return JSON.readTree(response.body()).path("result").path("count").asLong();
    }
    Map<String, Object> document(String id) {
        return Map.of("documentId", id, "title", "HTTP fixture", "content", "The audit fixture describes amber parrots and blue feathers.", "source", "local-test");
    }
    String signed(String subject, Object roles, String issuer, Instant expires) {
        return Jwts.builder().subject(subject).issuer(issuer).expiration(Date.from(expires)).claim("roles", roles)
                .signWith(Keys.hmacShaKeyFor(SIGNING_TEXT.getBytes(StandardCharsets.UTF_8)), Jwts.SIG.HS256).compact();
    }
    @BeforeAll void credentials() throws Exception {
        admin = mint("admin-fixture", List.of("ADMIN"));
        user = mint("user-fixture", List.of("USER"));
        outsider = mint("outsider-fixture", List.of("OBSERVER"));
    }
    @AfterAll void closeClient() { http.close(); }

    @Test void publicHealthAndAnonymousProtectionUseRealHttp() throws Exception {
        assertEquals(200, request("GET", "/api/health", null, Map.of()).status());
        assertEquals("UP", request("GET", "/actuator/health", null, Map.of()).json().path("status").asText());
        assertEquals(403, request("GET", "/api/audit", null, Map.of()).status());
        assertEquals(403, request("POST", "/api/query", Map.of("question", "amber"), Map.of()).status());
        assertEquals(403, request("POST", "/api/ingest", document("anonymous-denied"), Map.of()).status());
    }
    @Test void tokenEndpointRejectsMissingWrongAndMalformedCredentials() throws Exception {
        var body = Map.of("username", "denied-fixture");
        assertEquals(400, request("POST", "/api/auth/token", body, Map.of()).status());
        var denied = request("POST", "/api/auth/token", body, Map.of("X-Dev-Key", "wrong-fixture-key"));
        assertEquals(401, denied.status());
        assertFalse(denied.raw().contains(DEV_KEY));
        assertEquals(400, request("POST", "/api/auth/token", Map.of("username", " "), Map.of("X-Dev-Key", DEV_KEY)).status());
        assertEquals(400, request("POST", "/api/auth/token", "{", Map.of("X-Dev-Key", DEV_KEY)).status());
    }
    @Test void adminIngestUserQueryAndAdminAuditFormAnEndToEndFlow() throws Exception {
        String id = "round-trip-" + UUID.randomUUID();
        var ingest = request("POST", "/api/ingest", document(id), bearer(admin));
        assertEquals(200, ingest.status()); assertEquals(id, ingest.json().path("documentId").asText());
        assertTrue(ingest.json().path("chunksIngested").asInt() > 0);
        var query = request("POST", "/api/query", Map.of("question", "amber parrots", "topK", 4), bearer(user));
        assertEquals(200, query.status()); assertFalse(query.json().path("answer").asText().isBlank());
        var audit = request("GET", "/api/audit?limit=500", null, bearer(admin));
        assertEquals(200, audit.status()); assertTrue(audit.json().isArray());
        assertTrue(StreamSupport.stream(audit.json().spliterator(), false).anyMatch(e ->
                e.path("actor").asText().equals("admin-fixture") && e.path("action").asText().equals("INGEST") && e.path("resource").asText().equals(id)));
        assertTrue(StreamSupport.stream(audit.json().spliterator(), false).anyMatch(e ->
                e.path("actor").asText().equals("user-fixture") && e.path("action").asText().equals("QUERY")));
        assertFalse(audit.raw().contains(admin)); assertFalse(audit.raw().contains(SIGNING_TEXT));
    }
    @Test void userCannotWriteOrReadAuditAndDeniedWriteDoesNotMutateData() throws Exception {
        long before = pointCount();
        assertEquals(403, request("POST", "/api/ingest", document("user-denied"), bearer(user)).status());
        assertEquals(403, request("GET", "/api/audit", null, bearer(user)).status());
        assertEquals(before, pointCount());
    }
    @Test void unknownRoleCannotUseProtectedBusinessEndpoints() throws Exception {
        long before = pointCount();
        assertEquals(403, request("GET", "/api/audit", null, bearer(outsider)).status());
        assertEquals(403, request("POST", "/api/ingest", document("outsider-denied"), bearer(outsider)).status());
        assertEquals(403, request("POST", "/api/query", Map.of("question", "amber"), bearer(outsider)).status());
        assertEquals(before, pointCount());
    }
    @Test void invalidPayloadsKeepClientErrorStatusesAndDoNotWrite() throws Exception {
        long before = pointCount();
        assertAll(
                () -> assertEquals(400, request("POST", "/api/ingest", Map.of("title", "", "content", "x"), bearer(admin)).status()),
                () -> assertEquals(400, request("POST", "/api/query", Map.of("question", " "), bearer(user)).status()),
                () -> assertEquals(400, request("POST", "/api/query", Map.of("question", "x", "topK", 0), bearer(user)).status()),
                () -> assertEquals(400, request("POST", "/api/query", Map.of("question", "x", "topK", 101), bearer(user)).status()),
                () -> assertEquals(400, request("POST", "/api/query", "{", bearer(user)).status()),
                () -> assertEquals(400, request("GET", "/api/audit?limit=abc", null, bearer(admin)).status()));
        assertEquals(before, pointCount());
    }
    @Test void bearerSchemeComparisonIsCaseInsensitive() throws Exception {
        assertAll(List.of("bearer", "BEARER", "bEaReR").stream().map(scheme -> (Executable) () ->
                assertEquals(200, request("GET", "/api/audit", null, Map.of("Authorization", scheme + " " + admin)).status(), scheme)));
    }
    @Test void signedNullOrNonStringRolesAreRejectedCleanly() {
        assertAll(Arrays.asList(Arrays.asList((Object) null), List.of(7), List.of(Map.of("role", "ADMIN"))).stream().map(roles -> (Executable) () -> {
            String value = signed("fixture", roles, "http-audit-fixture", Instant.now().plusSeconds(60));
            var response = request("GET", "/api/audit", null, bearer(value));
            assertEquals(401, response.status());
            assertEquals("Invalid or expired token", response.json().path("error").asText());
        }));
    }
    @Test void signedTokensWithoutAnIdentityCannotReadAudit() {
        assertAll(Arrays.asList(null, "", "  ").stream().map(subject -> (Executable) () ->
                assertEquals(401, request("GET", "/api/audit", null, bearer(signed(subject, List.of("ADMIN"),
                        "http-audit-fixture", Instant.now().plusSeconds(60)))).status())));
    }
    @Test void invalidExpiredWrongIssuerAndWrongSignatureTokensReturn401() {
        var values = List.of("not-a-jwt",
                signed("fixture", List.of("ADMIN"), "http-audit-fixture", Instant.EPOCH),
                signed("fixture", List.of("ADMIN"), "wrong-issuer", Instant.now().plusSeconds(60)),
                Jwts.builder().subject("fixture").issuer("http-audit-fixture").signWith(Jwts.SIG.HS256.key().build()).compact(),
                Jwts.builder().subject("fixture").issuer("http-audit-fixture").compact());
        assertAll(values.stream().map(value -> (Executable) () -> {
            var response = request("GET", "/api/audit", null, bearer(value));
            assertEquals(401, response.status()); assertFalse(response.raw().contains(value));
        }));
    }
    @Test void bearerIdentityDoesNotLeakIntoCookiesOrLaterRequests() throws Exception {
        var first = request("GET", "/api/audit", null, bearer(admin));
        assertEquals(200, first.status()); assertTrue(first.headers().allValues("Set-Cookie").isEmpty());
        assertEquals(403, request("GET", "/api/audit", null, Map.of()).status());
        assertEquals(403, request("GET", "/api/audit", null, Map.of("Cookie", "Authorization=" + admin + "; JSESSIONID=fixture")).status());
        assertEquals(403, request("GET", "/api/audit", null, Map.of("Authorization", "Basic " + Base64.getEncoder().encodeToString("fixture:fixture".getBytes(StandardCharsets.UTF_8)))).status());
    }
    @Test void defaultAndNormalizedRolesKeepTheirIntendedPrivileges() throws Exception {
        String normal = mint("default-role-fixture", null);
        assertEquals(403, request("GET", "/api/audit", null, bearer(normal)).status());
        assertEquals(200, request("POST", "/api/query", Map.of("question", "amber"), bearer(normal)).status());
        String normalized = mint("normalized-role-fixture", List.of(" admin "));
        assertEquals(200, request("GET", "/api/audit", null, bearer(normalized)).status());
    }
    @Test void internalErrorHandlingDoesNotExposeTheErrorRouteOrDiagnostics() throws Exception {
        assertEquals(403, request("GET", "/error", null, Map.of()).status());
        var rejected = request("POST", "/api/query", "{", bearer(user));
        assertEquals(400, rejected.status());
        assertFalse(rejected.raw().contains("stackTrace"));
        assertFalse(rejected.raw().contains("com.portfolio"));
        assertFalse(rejected.raw().contains(SIGNING_TEXT));
        assertFalse(rejected.raw().contains(user));
    }
    @Test void parallelAdminAndUserRequestsKeepIdentityBoundaries() throws Exception {
        try (var pool = Executors.newFixedThreadPool(4)) {
            List<Callable<Integer>> calls = new ArrayList<>();
            for (int i = 0; i < 16; i++) {
                final boolean privileged = i % 2 == 0;
                calls.add(() -> request("GET", "/api/audit", null, bearer(privileged ? admin : user)).status());
            }
            var responses = pool.invokeAll(calls, 10, TimeUnit.SECONDS);
            for (int i = 0; i < responses.size(); i++) assertEquals(i % 2 == 0 ? 200 : 403, responses.get(i).get());
        }
    }
}
