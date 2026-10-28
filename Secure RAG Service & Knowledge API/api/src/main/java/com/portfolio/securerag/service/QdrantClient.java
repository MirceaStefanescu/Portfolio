package com.portfolio.securerag.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.securerag.config.QdrantProperties;
import com.portfolio.securerag.config.RagProperties;
import com.portfolio.securerag.model.RetrievedChunk;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

@Component
public class QdrantClient {

    private static final Logger logger = LoggerFactory.getLogger(QdrantClient.class);

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;
    private final QdrantProperties qdrantProperties;
    private final RagProperties ragProperties;

    public QdrantClient(RestTemplate restTemplate,
                        ObjectMapper objectMapper,
                        QdrantProperties qdrantProperties,
                        RagProperties ragProperties) {
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
        this.qdrantProperties = qdrantProperties;
        this.ragProperties = ragProperties;
    }

    public void ensureCollectionReady() {
        int attempts = 0;
        while (attempts < 10) {
            checkInterrupted();
            try {
                getCollection();
                return;
            } catch (HttpClientErrorException.NotFound notFound) {
                checkInterrupted();
                try {
                    createCollection();
                    return;
                } catch (Exception ex) {
                    attempts++;
                    logger.warn("Failed to create collection (attempt {}): {}", attempts, ex.getMessage());
                    sleep(Duration.ofSeconds(2));
                }
            } catch (Exception ex) {
                attempts++;
                logger.warn("Waiting for Qdrant (attempt {}): {}", attempts, ex.getMessage());
                sleep(Duration.ofSeconds(2));
            }
        }
        throw new IllegalStateException("Qdrant collection unavailable after retries.");
    }

    public void upsertPoints(List<QdrantPoint> points) {
        if (points == null || points.isEmpty()) {
            return;
        }

        String url = qdrantProperties.getUrl() + "/collections/" + qdrantProperties.getCollection() + "/points?wait=true";
        Map<String, Object> body = new HashMap<>();
        body.put("points", points);
        try {
            restTemplate.exchange(url, HttpMethod.PUT, new HttpEntity<>(body, headers()), String.class);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to upsert points into Qdrant: " + ex.getMessage(), ex);
        }
    }

    public List<RetrievedChunk> search(float[] vector, int limit) {
        String url = qdrantProperties.getUrl() + "/collections/" + qdrantProperties.getCollection() + "/points/search";
        Map<String, Object> body = new HashMap<>();
        body.put("vector", vector);
        body.put("limit", limit);
        body.put("with_payload", true);

        try {
            ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.POST,
                    new HttpEntity<>(body, headers()), String.class);
            return parseResults(response.getBody());
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to query Qdrant: " + ex.getMessage(), ex);
        }
    }

    private void getCollection() {
        String url = qdrantProperties.getUrl() + "/collections/" + qdrantProperties.getCollection();
        restTemplate.exchange(url, HttpMethod.GET, new HttpEntity<>(headers()), String.class);
    }

    public void removeStaleChunks(String documentId, List<String> currentIds) {
        var filter = Map.of("must", List.of(Map.of("key", "documentId", "match", Map.of("value", documentId))),
                "must_not", List.of(Map.of("has_id", currentIds)));
        restTemplate.exchange(qdrantProperties.getUrl() + "/collections/" + qdrantProperties.getCollection()
                + "/points/delete?wait=true", HttpMethod.POST,
                new HttpEntity<>(Map.of("filter", filter), headers()), String.class);
    }

    /** Read the complete bounded corpus; never silently rank a truncated subset. */
    public List<RetrievedChunk> lexicalCorpus() {
        var chunks = new ArrayList<RetrievedChunk>();
        var seenOffsets = new HashSet<JsonNode>();
        JsonNode offset = null;
        do {
            checkInterrupted();
            var body = new HashMap<String, Object>();
            body.put("limit", 256); body.put("with_payload", true); body.put("with_vector", false);
            if (offset != null) body.put("offset", offset);
            var response = restTemplate.exchange(qdrantProperties.getUrl() + "/collections/"
                    + qdrantProperties.getCollection() + "/points/scroll", HttpMethod.POST,
                    new HttpEntity<>(body, headers()), JsonNode.class).getBody();
            if (response == null || !response.path("result").path("points").isArray()) {
                throw new IllegalStateException("Invalid Qdrant scroll response");
            }
            for (var node : response.path("result").path("points")) {
                var payload = node.path("payload");
                chunks.add(new RetrievedChunk(payload.path("documentId").asText(), payload.path("title").asText(),
                        payload.path("source").asText(), payload.path("text").asText(), 0));
            }
            if (chunks.size() > 10000) throw new IllegalStateException("Local BM25 corpus limit is 10000 chunks");
            offset = response.path("result").get("next_page_offset");
            if (offset != null && !offset.isNull() && !seenOffsets.add(offset)) {
                throw new IllegalStateException("Qdrant scroll returned a repeated page offset");
            }
        } while (offset != null && !offset.isNull());
        checkInterrupted();
        return chunks;
    }

    private void createCollection() {
        String url = qdrantProperties.getUrl() + "/collections/" + qdrantProperties.getCollection();
        Map<String, Object> vectors = new HashMap<>();
        vectors.put("size", ragProperties.getVectorSize());
        vectors.put("distance", "Cosine");
        Map<String, Object> body = new HashMap<>();
        body.put("vectors", vectors);

        restTemplate.exchange(url, HttpMethod.PUT, new HttpEntity<>(body, headers()), String.class);
    }

    private List<RetrievedChunk> parseResults(String responseBody) throws Exception {
        List<RetrievedChunk> results = new ArrayList<>();
        if (responseBody == null || responseBody.isBlank()) {
            throw new IllegalStateException("Empty Qdrant search response");
        }

        JsonNode root = objectMapper.readTree(responseBody);
        JsonNode result = root.path("result");
        if (!result.isArray()) {
            throw new IllegalStateException("Invalid Qdrant search response: result must be an array");
        }
        for (JsonNode node : result) {
            double score = node.path("score").asDouble();
            JsonNode payload = node.path("payload");
            String text = payload.path("text").asText("");
            String documentId = payload.path("documentId").asText("");
            String title = payload.path("title").asText("");
            String source = payload.path("source").asText("");
            results.add(new RetrievedChunk(documentId, title, source, text, score));
        }
        return results;
    }

    private HttpHeaders headers() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (qdrantProperties.getApiKey() != null && !qdrantProperties.getApiKey().isBlank()) {
            headers.add("api-key", qdrantProperties.getApiKey());
        }
        return headers;
    }

    private void sleep(Duration duration) {
        try {
            Thread.sleep(duration.toMillis());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Qdrant operation interrupted", ex);
        }
    }

    private void checkInterrupted() {
        if (Thread.currentThread().isInterrupted()) {
            throw new IllegalStateException("Qdrant operation interrupted");
        }
    }
}
