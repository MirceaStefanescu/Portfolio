package com.portfolio.pipeline.flink;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

final class PredictionScorer {
  private PredictionScorer() {}

  static double score(double avgValue, long eventCount) {
    if (!Double.isFinite(avgValue) || eventCount <= 0) {
      throw new IllegalArgumentException("A finite average and positive count are required");
    }
    return Math.abs(avgValue - MODEL.get("mean").asDouble()) / MODEL.get("stddev").asDouble();
  }

  private static final JsonNode MODEL = load();
  private static JsonNode load() {
    try (var input = PredictionScorer.class.getResourceAsStream("/anomaly-model.json")) {
      if (input == null) throw new IllegalStateException("Missing trained anomaly model");
      JsonNode model = new ObjectMapper().readTree(input);
      if (!Double.isFinite(model.path("mean").asDouble(Double.NaN))
          || !Double.isFinite(model.path("stddev").asDouble(Double.NaN))
          || model.path("stddev").asDouble() <= 0) throw new IllegalStateException("Invalid model");
      return model;
    } catch (java.io.IOException ex) { throw new IllegalStateException(ex); }
  }
}
