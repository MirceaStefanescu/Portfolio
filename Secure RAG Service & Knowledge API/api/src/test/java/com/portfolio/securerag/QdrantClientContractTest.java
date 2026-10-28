package com.portfolio.securerag;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.securerag.config.*;
import com.portfolio.securerag.service.*;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.function.Executable;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class QdrantClientContractTest {
    static final ObjectMapper JSON = new ObjectMapper();
    static final class Fixture {
        final RestTemplate rest = mock(RestTemplate.class);
        final QdrantProperties qdrant = new QdrantProperties();
        final RagProperties rag = new RagProperties();
        final QdrantClient client;
        Fixture() {
            qdrant.setUrl("http://127.0.0.1:1"); qdrant.setCollection("fixture"); rag.setVectorSize(2);
            client = new QdrantClient(rest, JSON, qdrant, rag);
        }
        void searchResponse(String body) {
            when(rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(String.class)))
                    .thenReturn(ResponseEntity.ok(body));
        }
        void scrollResponse(JsonNode body) {
            when(rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(JsonNode.class)))
                    .thenReturn(ResponseEntity.ok(body));
        }
    }
    static JsonNode json(String text) {
        try { return JSON.readTree(text); } catch (Exception ex) { throw new IllegalArgumentException(ex); }
    }
    static JsonNode page(int count, JsonNode next) {
        var result = JSON.createObjectNode(); var points = result.putArray("points");
        for (int i = 0; i < count; i++) {
            var point = points.addObject(); point.put("id", i);
            point.putObject("payload").put("documentId", "doc-" + i).put("text", "fixture text");
        }
        result.set("next_page_offset", next);
        return JSON.createObjectNode().set("result", result);
    }

    @Test void realLoopbackTransportPreservesHeadersBodiesAndPagination() throws Exception {
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        var requests = new AtomicInteger(); var pages = new AtomicInteger();
        var serverFailure = new AtomicReference<Throwable>();
        server.createContext("/collections/fixture", exchange -> {
            String response = "{\"result\":true,\"status\":\"ok\"}"; int code = 200;
            try {
                requests.incrementAndGet();
                assertEquals("fixture-only", exchange.getRequestHeaders().getFirst("api-key"));
                byte[] bytes = exchange.getRequestBody().readAllBytes();
                JsonNode body = bytes.length == 0 ? JSON.nullNode() : JSON.readTree(bytes);
                String path = exchange.getRequestURI().getPath();
                if (path.endsWith("/points/search")) {
                    assertEquals("POST", exchange.getRequestMethod()); assertEquals(3, body.path("limit").asInt());
                    assertEquals(2, body.path("vector").size()); assertTrue(body.path("with_payload").asBoolean());
                    response = "{\"result\":[{\"id\":1,\"score\":0.75,\"payload\":{\"documentId\":\"doc-a\",\"title\":\"Title\",\"source\":\"fixture\",\"text\":\"alpha\"}}]}";
                } else if (path.endsWith("/points/delete")) {
                    assertEquals("POST", exchange.getRequestMethod()); assertEquals("wait=true", exchange.getRequestURI().getQuery());
                    assertEquals("doc-a", body.at("/filter/must/0/match/value").asText());
                    assertEquals("00000000-0000-0000-0000-000000000001", body.at("/filter/must_not/0/has_id/0").asText());
                } else if (path.endsWith("/points/scroll")) {
                    assertEquals("POST", exchange.getRequestMethod()); assertEquals(256, body.path("limit").asInt());
                    assertFalse(body.path("with_vector").asBoolean()); assertTrue(body.path("with_payload").asBoolean());
                    if (pages.getAndIncrement() == 0) {
                        assertFalse(body.has("offset")); response = page(1, JSON.getNodeFactory().numberNode(42)).toString();
                    } else {
                        assertEquals(42, body.path("offset").asInt()); response = page(1, JSON.nullNode()).toString();
                    }
                } else if (path.endsWith("/points")) {
                    assertEquals("PUT", exchange.getRequestMethod()); assertEquals("wait=true", exchange.getRequestURI().getQuery());
                    assertEquals(1, body.path("points").size());
                    assertEquals("doc-a", body.at("/points/0/payload/documentId").asText());
                    assertEquals(2, body.at("/points/0/vector").size());
                } else {
                    assertEquals("GET", exchange.getRequestMethod());
                    response = "{\"result\":{\"config\":{\"params\":{\"vectors\":{\"size\":2,\"distance\":\"Cosine\"}}}}}";
                }
            } catch (Throwable ex) { serverFailure.compareAndSet(null, ex); code = 500; response = "{\"status\":\"fixture assertion failed\"}"; }
            try {
                byte[] bytes = response.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(code, bytes.length); exchange.getResponseBody().write(bytes);
            } finally { exchange.close(); }
        });
        server.start();
        try {
            var factory = new SimpleClientHttpRequestFactory(); factory.setConnectTimeout(2000); factory.setReadTimeout(2000);
            var props = new QdrantProperties(); props.setCollection("fixture"); props.setApiKey("fixture-only");
            props.setUrl("http://127.0.0.1:" + server.getAddress().getPort());
            var rag = new RagProperties(); rag.setVectorSize(2);
            var client = new QdrantClient(new RestTemplate(factory), JSON, props, rag);
            client.ensureCollectionReady();
            String id = "00000000-0000-0000-0000-000000000001";
            client.upsertPoints(List.of(new QdrantPoint(id, new float[]{1, 0}, Map.of("documentId", "doc-a", "text", "alpha"))));
            var found = client.search(new float[]{1, 0}, 3);
            assertEquals(1, found.size()); assertEquals("doc-a", found.getFirst().documentId()); assertEquals(0.75, found.getFirst().score());
            client.removeStaleChunks("doc-a", List.of(id));
            assertEquals(2, client.lexicalCorpus().size()); assertEquals(6, requests.get()); assertNull(serverFailure.get());
        } finally { server.stop(0); }
    }

    @Test void missingCollectionIsCreatedWithConfiguredVectorDimensions() {
        var f = new Fixture();
        when(f.rest.exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class)))
                .thenThrow(HttpClientErrorException.create(HttpStatus.NOT_FOUND, "fixture missing", HttpHeaders.EMPTY, new byte[0], StandardCharsets.UTF_8));
        when(f.rest.exchange(anyString(), eq(HttpMethod.PUT), any(HttpEntity.class), eq(String.class))).thenAnswer(call -> {
            JsonNode body = JSON.valueToTree(((HttpEntity<?>) call.getArgument(2)).getBody());
            assertEquals(2, body.at("/vectors/size").asInt()); assertEquals("Cosine", body.at("/vectors/distance").asText());
            return ResponseEntity.ok("{\"result\":true}");
        });
        f.client.ensureCollectionReady();
        verify(f.rest).exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class));
        verify(f.rest).exchange(anyString(), eq(HttpMethod.PUT), any(HttpEntity.class), eq(String.class));
    }

    @Test void emptyUpsertsDoNotIssueRequests() {
        var f = new Fixture(); f.client.upsertPoints(null); f.client.upsertPoints(List.of()); verifyNoInteractions(f.rest);
    }

    @Test void transportFailureCannotBecomeAnEmptySearch() {
        var f = new Fixture();
        when(f.rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(String.class)))
                .thenThrow(new ResourceAccessException("fixture connection failed"));
        assertInstanceOf(ResourceAccessException.class, assertThrows(IllegalStateException.class,
                () -> f.client.search(new float[]{1, 0}, 1)).getCause());
    }

    @Test void validEmptySearchArrayIsAccepted() {
        var f = new Fixture(); f.searchResponse("{\"result\":[],\"status\":\"ok\"}");
        assertEquals(List.of(), f.client.search(new float[]{1, 0}, 1));
    }

    @Test void incompleteSearchResponsesFailInsteadOfPretendingNothingMatched() {
        List<String> invalid = Arrays.asList(null, "", " ", "{}", "{\"result\":null}", "{\"result\":{}}", "not-json");
        assertAll(invalid.stream().map(body -> (Executable) () -> {
            var f = new Fixture(); f.searchResponse(body);
            assertThrows(IllegalStateException.class, () -> f.client.search(new float[]{1, 0}, 1), "body=" + body);
        }));
    }

    @Test void invalidScrollEnvelopesFail() {
        List<JsonNode> invalid = Arrays.asList(null, json("{}"), json("{\"result\":{}}"), json("{\"result\":{\"points\":null}}"));
        assertAll(invalid.stream().map(body -> (Executable) () -> {
            var f = new Fixture(); f.scrollResponse(body);
            assertThrows(IllegalStateException.class, f.client::lexicalCorpus);
        }));
    }

    @Test void repeatedOffsetStopsBeforeAnotherRequestEvenWhenPagesAreEmpty() {
        var f = new Fixture(); var requests = new AtomicInteger();
        when(f.rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(JsonNode.class))).thenAnswer(call -> {
            if (requests.incrementAndGet() > 2) throw new AssertionError("Bounded fixture: repeated cursor requested a third page");
            return ResponseEntity.ok(page(0, JSON.getNodeFactory().numberNode(7)));
        });
        assertThrows(IllegalStateException.class, f.client::lexicalCorpus);
        assertEquals(2, requests.get());
    }

    @Test void aLongerCursorCycleAlsoStopsWithoutReturningPartialCorpus() {
        var f = new Fixture(); var requests = new AtomicInteger();
        when(f.rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(JsonNode.class))).thenAnswer(call -> {
            int n = requests.incrementAndGet();
            if (n > 3) throw new AssertionError("Bounded fixture: cyclic cursor requested a fourth page");
            return ResponseEntity.ok(page(1, JSON.getNodeFactory().textNode(n == 2 ? "00000000-0000-0000-0000-000000000002" : "00000000-0000-0000-0000-000000000001")));
        });
        assertThrows(IllegalStateException.class, f.client::lexicalCorpus);
        assertEquals(3, requests.get());
    }

    @Test void corpusLimitAcceptsTenThousandButRejectsAnExtraChunk() {
        for (int total : List.of(10000, 10001)) {
            var f = new Fixture(); var emitted = new AtomicInteger();
            when(f.rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(JsonNode.class))).thenAnswer(call -> {
                int count = Math.min(256, total - emitted.get()); int upto = emitted.addAndGet(count);
                return ResponseEntity.ok(page(count, upto < total ? JSON.getNodeFactory().numberNode(upto) : JSON.nullNode()));
            });
            if (total == 10000) assertEquals(total, f.client.lexicalCorpus().size());
            else assertThrows(IllegalStateException.class, f.client::lexicalCorpus);
        }
    }

    @Test void failureOnLaterPageCannotReturnEarlierPartialData() {
        var f = new Fixture();
        when(f.rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(JsonNode.class)))
                .thenReturn(ResponseEntity.ok(page(1, JSON.getNodeFactory().numberNode(1))))
                .thenThrow(new ResourceAccessException("fixture later-page failure"));
        assertThrows(ResourceAccessException.class, f.client::lexicalCorpus);
    }

    @Test void interruptedCollectionSetupDoesNotStartAnHttpRequest() {
        var f = new Fixture();
        when(f.rest.exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class))).thenReturn(ResponseEntity.ok("{}"));
        Thread.currentThread().interrupt();
        try {
            assertThrows(IllegalStateException.class, f.client::ensureCollectionReady);
            assertTrue(Thread.currentThread().isInterrupted()); verifyNoInteractions(f.rest);
        } finally { Thread.interrupted(); }
    }

    @Test void interruptedRetrySleepPreservesCancellationAndStopsRetries() {
        var f = new Fixture(); var requests = new AtomicInteger();
        when(f.rest.exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class))).thenAnswer(call -> {
            requests.incrementAndGet(); Thread.currentThread().interrupt(); throw new ResourceAccessException("fixture connection failed");
        });
        try {
            assertThrows(IllegalStateException.class, f.client::ensureCollectionReady);
            assertTrue(Thread.currentThread().isInterrupted()); assertEquals(1, requests.get());
        } finally { Thread.interrupted(); }
    }

    @Test void interruptedScrollStopsBeforeTheNextPage() {
        var f = new Fixture(); var requests = new AtomicInteger();
        when(f.rest.exchange(anyString(), eq(HttpMethod.POST), any(HttpEntity.class), eq(JsonNode.class))).thenAnswer(call -> {
            if (requests.incrementAndGet() > 1) throw new AssertionError("Bounded fixture: request issued after cancellation");
            Thread.currentThread().interrupt(); return ResponseEntity.ok(page(1, JSON.getNodeFactory().numberNode(1)));
        });
        try {
            assertThrows(IllegalStateException.class, f.client::lexicalCorpus);
            assertTrue(Thread.currentThread().isInterrupted()); assertEquals(1, requests.get());
        } finally { Thread.interrupted(); }
    }

    @Test void collectionRetryEventuallySucceeds() {
        var f = new Fixture();
        when(f.rest.exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class)))
                .thenThrow(new ResourceAccessException("fixture transient failure")).thenReturn(ResponseEntity.ok("{}"));
        assertTimeoutPreemptively(Duration.ofSeconds(6), f.client::ensureCollectionReady);
        verify(f.rest, times(2)).exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class));
    }

    @Test void collectionRetryExhaustionIsBounded() {
        var f = new Fixture();
        when(f.rest.exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class)))
                .thenThrow(new ResourceAccessException("fixture unavailable"));
        assertTimeoutPreemptively(Duration.ofSeconds(25), () -> assertThrows(IllegalStateException.class, f.client::ensureCollectionReady));
        verify(f.rest, times(10)).exchange(anyString(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class));
    }
}
