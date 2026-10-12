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

    public IngestResponse ingest(IngestRequest request, String actor) {
        String documentId = request.documentId();
        if (documentId == null || documentId.isBlank()) {
            documentId = UUID.randomUUID().toString();
        }

        List<String> chunks = chunker.chunk(request.content(), ragProperties.getChunkSize(), ragProperties.getChunkOverlap());
        List<QdrantPoint> points = new ArrayList<>();
        int index = 0;
        for (String chunk : chunks) {
            float[] vector = embeddingService.embed(chunk);
            Map<String, Object> payload = new java.util.HashMap<>();
            payload.put("text", chunk);
            payload.put("documentId", documentId);
            payload.put("title", request.title());
            payload.put("source", request.source() == null ? "" : request.source());
            payload.put("chunkIndex", index);
            if (request.tags() != null) {
                payload.put("tags", request.tags());
            }
            points.add(new QdrantPoint(UUID.randomUUID().toString(), vector, payload));
            index++;
        }

        qdrantClient.upsertPoints(points);
        auditLogService.record(actor, "INGEST", documentId, "OK", "chunks=" + chunks.size());
        return new IngestResponse(documentId, chunks.size(), qdrantProperties.getCollection());
    }

    public QueryResponse query(QueryRequest request, String actor) {
        int limit = request.topK() == null || request.topK() < 1 ? ragProperties.getTopK() : request.topK();
        long start = System.currentTimeMillis();
        float[] vector = embeddingService.embed(request.question());
        List<RetrievedChunk> retrieved = qdrantClient.search(vector, limit);
        String answer = answerComposer.compose(request.question(), retrieved);
        long duration = System.currentTimeMillis() - start;
        auditLogService.record(actor, "QUERY", request.question(), "OK", "results=" + retrieved.size());
        return new QueryResponse(answer, retrieved, duration);
    }
}
