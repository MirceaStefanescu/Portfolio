package com.portfolio.securerag.service;

public interface EmbeddingService {

    float[] embed(String text);

    default java.util.List<float[]> embedAll(java.util.List<String> texts) {
        return texts.stream().map(this::embed).toList();
    }
}
