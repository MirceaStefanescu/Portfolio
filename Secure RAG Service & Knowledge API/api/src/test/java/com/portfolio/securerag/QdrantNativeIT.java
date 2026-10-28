package com.portfolio.securerag;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.securerag.config.QdrantProperties;
import com.portfolio.securerag.config.RagProperties;
import com.portfolio.securerag.model.RetrievedChunk;
import com.portfolio.securerag.service.QdrantClient;
import com.portfolio.securerag.service.QdrantPoint;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;
import static org.junit.jupiter.api.Assertions.*;

/** Explicit native acceptance: run with -Dtest=QdrantNativeIT against an isolated fixture. */
class QdrantNativeIT {
    @Test
    void native1192RoundTripPaginationSelectiveDeleteAndErrorRecovery() {
        String url = Objects.requireNonNull(System.getenv("RAG_QDRANT_NATIVE_URL"), "isolated fixture URL required");
        URI endpoint = URI.create(url);
        assertEquals("http", endpoint.getScheme());
        assertEquals("127.0.0.1", endpoint.getHost());
        assertTrue(endpoint.getPort() > 0);
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(2000); factory.setReadTimeout(5000);
        var rest = new RestTemplate(factory);
        List<String> requests = new ArrayList<>();
        rest.getInterceptors().add((request, body, execution) -> {
            requests.add(request.getMethod() + " " + request.getURI().getPath());
            return execution.execute(request, body);
        });
        assertEquals("1.19.2", rest.getForObject(url + "/", JsonNode.class).path("version").asText());
        String collection = "codex_java_contract_" + UUID.randomUUID().toString().replace("-", "");
        var props = new QdrantProperties(); props.setUrl(url); props.setCollection(collection);
        var rag = new RagProperties(); rag.setVectorSize(2);
        var client = new QdrantClient(rest, new ObjectMapper(), props, rag);
        String collectionUrl = url + "/collections/" + collection;
        boolean created = false;
        try {
            client.ensureCollectionReady(); created = true;
            client.ensureCollectionReady();
            assertEquals(1, requests.stream().filter(s -> s.equals("PUT /collections/" + collection)).count());
            assertTrue(client.search(new float[]{1, 0}, 3).isEmpty());
            JsonNode config = rest.getForObject(collectionUrl, JsonNode.class).path("result").path("config");
            assertEquals(2, config.path("params").path("vectors").path("size").asInt());
            assertEquals("Cosine", config.path("params").path("vectors").path("distance").asText());
            List<QdrantPoint> points = new ArrayList<>();
            for (int i = 0; i < 520; i++) {
                String id = UUID.nameUUIDFromBytes(("point-" + i).getBytes(StandardCharsets.UTF_8)).toString();
                points.add(new QdrantPoint(id, i == 0 ? new float[]{1, 0} : new float[]{0, 1},
                        Map.of("documentId", i < 300 ? "docA" : "docB", "title", "title-" + i,
                                "source", "fixture", "text", "chunk-" + i)));
            }
            client.upsertPoints(points);
            var found = client.search(new float[]{1, 0}, 3);
            assertEquals(3, found.size());
            assertEquals("chunk-0", found.getFirst().text());
            assertEquals(1.0, found.getFirst().score(), 0.00001);
            int scrollBefore = (int) requests.stream().filter(s -> s.endsWith("/points/scroll")).count();
            var corpus = client.lexicalCorpus();
            assertEquals(520, corpus.size());
            assertEquals(520, corpus.stream().map(RetrievedChunk::text).distinct().count());
            assertEquals(3, requests.stream().filter(s -> s.endsWith("/points/scroll")).count() - scrollBefore);
            client.removeStaleChunks("docA", List.of(points.get(0).id(), points.get(1).id()));
            var remaining = client.lexicalCorpus();
            assertEquals(222, remaining.size());
            assertEquals(220, remaining.stream().filter(c -> c.documentId().equals("docB")).count());
            assertEquals(Set.of("chunk-0", "chunk-1"), new HashSet<>(remaining.stream()
                    .filter(c -> c.documentId().equals("docA")).map(RetrievedChunk::text).toList()));
            client.upsertPoints(List.of(new QdrantPoint(points.getFirst().id(), new float[]{1, 0},
                    Map.of("documentId", "docA", "title", "updated", "source", "fixture", "text", "updated"))));
            assertEquals(222, client.lexicalCorpus().size());
            assertEquals("updated", client.search(new float[]{1, 0}, 1).getFirst().text());
            assertThrows(IllegalStateException.class, () -> client.search(new float[]{1, 0, 0}, 1));
            assertThrows(IllegalStateException.class, () -> client.upsertPoints(List.of(
                    new QdrantPoint(UUID.randomUUID().toString(), new float[]{1, 0, 0}, Map.of("text", "invalid")))));
            assertEquals(222, client.lexicalCorpus().size());
            assertEquals("updated", client.search(new float[]{1, 0}, 1).getFirst().text());
            client.removeStaleChunks("docA", List.of());
            var finalCorpus = client.lexicalCorpus();
            assertEquals(220, finalCorpus.size());
            assertTrue(finalCorpus.stream().allMatch(c -> c.documentId().equals("docB")));
        } finally {
            if (created) rest.delete(collectionUrl);
        }
        assertFalse(rest.getForObject(collectionUrl + "/exists", JsonNode.class).path("result").path("exists").asBoolean());
        System.out.println("QDRANT_NATIVE version=1.19.2 points=520 scroll_pages=3 remaining=220 cleanup=PASS requests=" + requests.size());
    }
}
