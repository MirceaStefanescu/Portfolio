package com.portfolio.securerag.service;

import com.portfolio.securerag.config.QdrantProperties;
import com.portfolio.securerag.config.RagProperties;
import com.portfolio.securerag.model.IngestRequest;
import com.portfolio.securerag.model.IngestResponse;
import com.portfolio.securerag.model.QueryRequest;
import com.portfolio.securerag.model.QueryResponse;
import com.portfolio.securerag.model.RetrievedChunk;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class RagService {

    private final RagProperties ragProperties;
    private final QdrantProperties qdrantProperties;
    private final EmbeddingService embeddingService;
    private final Chunker chunker;
    private final QdrantClient qdrantClient;
    private final AnswerComposer answerComposer;
    private final AuditLogService auditLogService;
    private final Map<String, float[]> embeddings = new java.util.LinkedHashMap<>(512, 0.75f, true) {
        protected boolean removeEldestEntry(Map.Entry<String, float[]> entry) { return size() > 512; }
    };
    private record CachedRetrieval(long expires, List<RetrievedChunk> chunks) {}
    private final Map<String, CachedRetrieval> retrievals = new java.util.LinkedHashMap<>(128, 0.75f, true) {
        protected boolean removeEldestEntry(Map.Entry<String, CachedRetrieval> entry) { return size() > 128; }
    };

    public RagService(RagProperties ragProperties,
                      QdrantProperties qdrantProperties,
                      EmbeddingService embeddingService,
                      Chunker chunker,
                      QdrantClient qdrantClient,
                      AnswerComposer answerComposer,
                      AuditLogService auditLogService) {
        if (ragProperties.getTopK() < 1 || ragProperties.getTopK() > 100) {
            throw new IllegalArgumentException("Default top-k must be between 1 and 100.");
        }
        this.ragProperties = ragProperties;
        this.qdrantProperties = qdrantProperties;
        this.embeddingService = embeddingService;
        this.chunker = chunker;
        this.qdrantClient = qdrantClient;
        this.answerComposer = answerComposer;
        this.auditLogService = auditLogService;
        this.qdrantClient.ensureCollectionReady();
    }

    public synchronized IngestResponse ingest(IngestRequest request, String actor) {
        String documentId = request.documentId();
        if (documentId == null || documentId.isBlank()) {
            documentId = UUID.randomUUID().toString();
        }

        List<String> chunks = chunker.chunk(request.content(), ragProperties.getChunkSize(), ragProperties.getChunkOverlap());
        List<QdrantPoint> points = new ArrayList<>();
        List<float[]> vectors = embedBatch(chunks);
        int index = 0;
        for (String chunk : chunks) {
            float[] vector = vectors.get(index);
            Map<String, Object> payload = new java.util.HashMap<>();
            payload.put("text", chunk);
            payload.put("documentId", documentId);
            payload.put("title", request.title());
            payload.put("source", request.source() == null ? "" : request.source());
            payload.put("chunkIndex", index);
            if (request.tags() != null) {
                payload.put("tags", request.tags());
            }
            String pointId = UUID.nameUUIDFromBytes((documentId + "\u0000" + index)
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
            points.add(new QdrantPoint(pointId, vector, payload));
            index++;
        }

        retrievals.clear();
        qdrantClient.upsertPoints(points);
        qdrantClient.removeStaleChunks(documentId, points.stream().map(QdrantPoint::id).toList());
        auditLogService.record(actor, "INGEST", documentId, "OK", "chunks=" + chunks.size());
        return new IngestResponse(documentId, chunks.size(), qdrantProperties.getCollection());
    }

    public synchronized QueryResponse query(QueryRequest request, String actor) {
        int limit = request.topK() == null || request.topK() < 1 ? ragProperties.getTopK() : request.topK();
        long start = System.currentTimeMillis();
        String cacheKey = actor + "\u0000" + limit + "\u0000" + request.question();
        CachedRetrieval cached = retrievals.get(cacheKey);
        List<RetrievedChunk> retrieved;
        if (cached != null && cached.expires() > System.currentTimeMillis()) {
            retrieved = cached.chunks();
        } else {
            float[] vector = embedBatch(List.of(request.question())).getFirst();
            retrieved = HybridRanker.rank(request.question(),
                    qdrantClient.search(vector, Math.max(20, limit * 4)), qdrantClient.lexicalCorpus(), limit);
            retrievals.put(cacheKey, new CachedRetrieval(System.currentTimeMillis() + 5000, retrieved));
        }
        String answer = answerComposer.compose(request.question(), retrieved);
        long duration = System.currentTimeMillis() - start;
        auditLogService.record(actor, "QUERY", request.question(), "OK", "results=" + retrieved.size());
        return new QueryResponse(answer, retrieved, duration);
    }

    private List<float[]> embedBatch(List<String> texts) {
        var missing = texts.stream().filter(text -> !embeddings.containsKey(text)).distinct().toList();
        var generated = new java.util.HashMap<String, float[]>();
        for (int start = 0; start < missing.size(); start += 64) {
            var batch = missing.subList(start, Math.min(start + 64, missing.size()));
            var vectors = embeddingService.embedAll(batch);
            if (vectors.size() != batch.size()) throw new IllegalStateException("Embedding batch size mismatch");
            for (int i = 0; i < batch.size(); i++) {
                var vector = vectors.get(i);
                if (vector.length != ragProperties.getVectorSize()) {
                    throw new IllegalStateException("Embedding dimensions differ from RAG_VECTOR_SIZE");
                }
                for (float value : vector) if (!Float.isFinite(value)) {
                    throw new IllegalStateException("Embedding contains a nonfinite value");
                }
                generated.put(batch.get(i), vector);
            }
        }
        var result = texts.stream().map(text -> generated.containsKey(text)
                ? generated.get(text) : embeddings.get(text)).toList();
        embeddings.putAll(generated);
        return result;
    }
}
