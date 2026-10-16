package com.portfolio.securerag.service;

import com.portfolio.securerag.model.RetrievedChunk;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import org.springframework.stereotype.Component;

@Component
@org.springframework.boot.autoconfigure.condition.ConditionalOnProperty(name = "rag.provider", havingValue = "local", matchIfMissing = true)
public class MockLlmClient implements LlmClient {

    @Override
    public String generate(String question, List<RetrievedChunk> context) {
        if (context == null || context.isEmpty()) {
            return "No relevant content found. Ingest documentation and try again.";
        }

        StringBuilder answer = new StringBuilder();
        answer.append("Answer (mock LLM):\n");
        int limit = Math.min(context.size(), 2);
        for (int i = 0; i < limit; i++) {
            RetrievedChunk chunk = context.get(i);
            String snippet = chunk.text() == null ? "" : chunk.text();
            if (snippet.length() > 320) {
                snippet = snippet.substring(0, 320) + "...";
            }
            answer.append("\n").append(snippet).append("\n");
        }

        Set<String> sources = new LinkedHashSet<>();
        for (RetrievedChunk chunk : context) {
            if (chunk == null) {
                continue;
            }
            if (chunk.title() != null && !chunk.title().isBlank()) {
                sources.add(chunk.title());
            } else if (chunk.source() != null && !chunk.source().isBlank()) {
                sources.add(chunk.source());
            } else if (chunk.documentId() != null && !chunk.documentId().isBlank()) {
                sources.add(chunk.documentId());
            }
            if (sources.size() >= 3) {
                break;
            }
        }

        if (!sources.isEmpty()) {
            answer.append("\nSources:");
            for (String source : sources) {
                answer.append("\n- ").append(source);
            }
        }

        return answer.toString().trim();
    }
}
