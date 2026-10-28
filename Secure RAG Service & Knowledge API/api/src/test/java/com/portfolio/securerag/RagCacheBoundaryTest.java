package com.portfolio.securerag;

import com.portfolio.securerag.config.*;
import com.portfolio.securerag.model.*;
import com.portfolio.securerag.service.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/** Public-behavior checks: no reflection, real providers, shared services, or deployment credentials. */
class RagCacheBoundaryTest {
    static final class Fixture {
        final RagProperties properties = new RagProperties();
        final EmbeddingService embedder = mock(EmbeddingService.class);
        final QdrantClient store = mock(QdrantClient.class);
        final Chunker chunker = mock(Chunker.class);
        final AuditLogService audit = new AuditLogService(new AuditProperties());
        final RagService service;

        Fixture() {
            properties.setVectorSize(2);
            when(embedder.embedAll(anyList())).thenAnswer(call -> vectors(call.getArgument(0)));
            when(chunker.chunk(anyString(), anyInt(), anyInt())).thenAnswer(call -> List.of((String) call.getArgument(0)));
            when(store.search(any(), anyInt())).thenReturn(List.of());
            when(store.lexicalCorpus()).thenReturn(List.of());
            service = new RagService(properties, new QdrantProperties(), embedder, chunker, store,
                    new AnswerComposer(new MockLlmClient()), audit);
        }
        QueryResponse query(String question) { return query(question, "alice", 4); }
        QueryResponse query(String question, String actor, int topK) {
            return service.query(new QueryRequest(question, topK), actor);
        }
        IngestRequest document(String content) { return new IngestRequest("fixture-doc", "Fixture", content, "test", List.of()); }
    }

    static List<float[]> vectors(List<?> inputs) {
        return inputs.stream().map(ignored -> new float[]{1, 0}).toList();
    }

    @Test void retrievalCacheSeparatesActorsAndLimitsWhileSharingEmbeddings() {
        var f = new Fixture();
        f.query("same question", "alice", 1);
        f.query("same question", "alice", 1);
        f.query("same question", "bob", 1);
        f.query("same question", "alice", 2);
        verify(f.store, times(3)).search(any(), anyInt());
        verify(f.embedder, times(1)).embedAll(List.of("same question"));
        assertEquals(4, f.audit.list(10).size());
    }

    @Test void retrievalCapacityEvictsLeastRecentlyUsedEntry() {
        var f = new Fixture();
        for (int i = 0; i < 128; i++) f.query("question-" + i);
        f.query("question-0"); // Refresh the oldest entry before crossing the capacity.
        f.query("question-128");
        f.query("question-0");
        f.query("question-1");
        f.query("question-128");
        verify(f.store, times(130)).search(any(), anyInt());
        verify(f.embedder, times(129)).embedAll(anyList());
    }

    @Test void embeddingCapacityPreservesRecentlyUsedEntryAndRegeneratesEvictedEntry() {
        var f = new Fixture();
        for (int i = 0; i < 512; i++) f.query("embedding-" + i);
        f.query("embedding-0"); // Retrieval has expired from capacity, embedding is reused and touched.
        f.query("embedding-512");
        f.query("embedding-0");
        f.query("embedding-1");
        verify(f.embedder, times(514)).embedAll(anyList());
        verify(f.store, times(515)).search(any(), anyInt());
    }

    @Test void largeEmbeddingBatchDeduplicatesTextAndPreservesEveryChunkPosition() {
        var f = new Fixture();
        var chunks = new ArrayList<>(IntStream.range(0, 130).mapToObj(i -> "chunk-" + i).toList());
        chunks.add("chunk-0"); chunks.add("chunk-129");
        when(f.chunker.chunk(anyString(), anyInt(), anyInt())).thenReturn(chunks);
        assertEquals(132, f.service.ingest(f.document("fixture content"), "alice").chunksIngested());
        @SuppressWarnings("unchecked") ArgumentCaptor<List<String>> batch = ArgumentCaptor.forClass(List.class);
        verify(f.embedder, times(3)).embedAll(batch.capture());
        assertEquals(List.of(64, 64, 2), batch.getAllValues().stream().map(List::size).toList());
        assertEquals(chunks.subList(0, 130), batch.getAllValues().stream().flatMap(List::stream).toList());
        @SuppressWarnings("unchecked") ArgumentCaptor<List<QdrantPoint>> points = ArgumentCaptor.forClass(List.class);
        verify(f.store).upsertPoints(points.capture());
        assertEquals(132, points.getValue().size());
        assertEquals(132, points.getValue().stream().map(QdrantPoint::id).distinct().count());
        for (int i = 0; i < chunks.size(); i++) {
            assertEquals(chunks.get(i), points.getValue().get(i).payload().get("text"));
            assertArrayEquals(new float[]{1, 0}, points.getValue().get(i).vector());
        }
        f.service.ingest(f.document("fixture content"), "alice");
        verify(f.embedder, times(3)).embedAll(anyList());
    }

    @Test void malformedEmbeddingBatchesCannotMutateStoreOrPoisonSubsequentRetry() {
        List<List<float[]>> invalid = List.of(List.of(), List.of(new float[]{1}),
                List.of(new float[]{Float.NaN, 0}), List.of(new float[]{Float.POSITIVE_INFINITY, 0}));
        for (var bad : invalid) {
            var f = new Fixture();
            when(f.embedder.embedAll(anyList())).thenReturn(bad).thenAnswer(call -> vectors(call.getArgument(0)));
            assertThrows(IllegalStateException.class, () -> f.service.ingest(f.document("text"), "alice"));
            verify(f.store, never()).upsertPoints(anyList());
            verify(f.store, never()).removeStaleChunks(anyString(), anyList());
            f.service.ingest(f.document("text"), "alice");
            verify(f.embedder, times(2)).embedAll(List.of("text"));
            verify(f.store).upsertPoints(anyList());
        }
    }

    @Test void failedWriteInvalidatesRetrievalAndDoesNotDeleteOldChunks() {
        var f = new Fixture();
        f.query("question"); f.query("question");
        doThrow(new IllegalStateException("fixture write failed")).when(f.store).upsertPoints(anyList());
        assertThrows(IllegalStateException.class, () -> f.service.ingest(f.document("text"), "alice"));
        verify(f.store, never()).removeStaleChunks(anyString(), anyList());
        f.query("question");
        verify(f.store, times(2)).search(any(), anyInt());
    }

    @Test void failedRetrievalDoesNotCachePartialResult() {
        var f = new Fixture();
        when(f.store.lexicalCorpus()).thenThrow(new IllegalStateException("fixture read failed")).thenReturn(List.of());
        assertThrows(IllegalStateException.class, () -> f.query("question"));
        f.query("question"); f.query("question");
        verify(f.store, times(2)).search(any(), anyInt());
        verify(f.embedder, times(1)).embedAll(List.of("question"));
        assertEquals(2, f.audit.list(10).size());
    }

    @Test void retrievalExpiresAfterFiveSecondsButEmbeddingRemainsReusable() throws Exception {
        var f = new Fixture();
        f.query("expiring"); f.query("expiring");
        verify(f.store, times(1)).search(any(), anyInt());
        Thread.sleep(5_100); // Verify the real public TTL without modifying clocks or private state.
        f.query("expiring");
        verify(f.store, times(2)).search(any(), anyInt());
        verify(f.embedder, times(1)).embedAll(List.of("expiring"));
    }

    @Test void concurrentIdenticalRequestsShareOneRetrievalAndRecordEveryQuery() throws Exception {
        var f = new Fixture();
        var ready = new CountDownLatch(8);
        var start = new CountDownLatch(1);
        try (var executor = Executors.newFixedThreadPool(8)) {
            var results = IntStream.range(0, 8).mapToObj(i -> executor.submit(() -> {
                ready.countDown();
                if (!start.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("fixture start timeout");
                return f.query("concurrent");
            })).toList();
            assertTrue(ready.await(5, TimeUnit.SECONDS));
            start.countDown();
            for (var result : results) assertNotNull(result.get(5, TimeUnit.SECONDS));
        } finally { start.countDown(); }
        verify(f.store, times(1)).search(any(), anyInt());
        verify(f.embedder, times(1)).embedAll(List.of("concurrent"));
        assertEquals(8, f.audit.list(10).size());
    }
}
