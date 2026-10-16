package com.portfolio.securerag.service;

import com.portfolio.securerag.model.RetrievedChunk;
import java.util.*;

/** BM25 lexical ranking fused with vector ranks. It does not claim neural reranking. */
public final class HybridRanker {
    private HybridRanker() {}
    private static List<String> tokens(String value) {
        return Arrays.stream(value.toLowerCase(Locale.ROOT).split("[^\\p{L}\\p{N}]+"))
                .filter(token -> !token.isBlank()).toList();
    }
    private static String key(RetrievedChunk chunk) { return chunk.documentId() + "\u0000" + chunk.text(); }

    public static List<RetrievedChunk> rank(String question, List<RetrievedChunk> vector,
                                           List<RetrievedChunk> corpus, int limit) {
        var terms = new HashSet<>(tokens(question));
        var counts = new ArrayList<Map<String, Integer>>();
        var lengths = new ArrayList<Integer>();
        var frequency = new HashMap<String, Integer>();
        for (var chunk : corpus) {
            var words = tokens(chunk.title() + " " + chunk.text());
            var count = new HashMap<String, Integer>();
            words.forEach(word -> count.merge(word, 1, Integer::sum));
            count.keySet().forEach(word -> frequency.merge(word, 1, Integer::sum));
            counts.add(count); lengths.add(words.size());
        }
        double average = lengths.stream().mapToInt(Integer::intValue).average().orElse(1.0);
        var lexical = new ArrayList<RetrievedChunk>();
        for (int i = 0; i < corpus.size(); i++) {
            double score = 0;
            for (String term : terms) {
                int tf = counts.get(i).getOrDefault(term, 0);
                if (tf == 0) continue;
                int df = frequency.get(term);
                double idf = Math.log(1 + (corpus.size() - df + 0.5) / (df + 0.5));
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * lengths.get(i) / Math.max(1, average)));
            }
            if (score > 0) {
                var chunk = corpus.get(i);
                lexical.add(new RetrievedChunk(chunk.documentId(), chunk.title(), chunk.source(), chunk.text(), score));
            }
        }
        lexical.sort(Comparator.comparingDouble(RetrievedChunk::score).reversed().thenComparing(HybridRanker::key));
        var combined = new HashMap<String, Double>();
        var chunks = new HashMap<String, RetrievedChunk>();
        for (var ranked : List.of(vector, lexical)) {
            for (int i = 0; i < Math.min(ranked.size(), Math.max(20, limit * 4)); i++) {
                var chunk = ranked.get(i);
                chunks.put(key(chunk), chunk);
                combined.merge(key(chunk), 1.0 / (60 + i + 1), Double::sum);
            }
        }
        return combined.entrySet().stream()
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed().thenComparing(Map.Entry::getKey))
                .limit(limit).map(entry -> {
                    var chunk = chunks.get(entry.getKey());
                    return new RetrievedChunk(chunk.documentId(), chunk.title(), chunk.source(), chunk.text(), entry.getValue());
                }).toList();
    }
}
