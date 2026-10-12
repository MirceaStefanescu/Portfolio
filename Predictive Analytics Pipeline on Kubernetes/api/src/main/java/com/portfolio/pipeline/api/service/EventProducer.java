package com.portfolio.pipeline.api.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.pipeline.api.model.EventRequest;
import java.time.Instant;
import java.util.concurrent.CompletableFuture;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import java.util.HashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class EventProducer {
  private final KafkaTemplate<String, String> kafkaTemplate;
  private final ObjectMapper objectMapper;
  private final String topic;

  public EventProducer(
      KafkaTemplate<String, String> kafkaTemplate,
      ObjectMapper objectMapper,
      @Value("${app.kafka.topic}") String topic
  ) {
    this.kafkaTemplate = kafkaTemplate;
    this.objectMapper = objectMapper;
    this.topic = topic;
  }

  public CompletableFuture<Void> publish(EventRequest request) {
    if (request.eventType() == null || request.eventType().isBlank()) {
      throw new IllegalArgumentException("eventType is required");
    }

    double value = request.value() == null ? 0.0 : request.value();
    if (!Double.isFinite(value)) {
      throw new IllegalArgumentException("value must be finite");
    }
    Instant timestamp = request.timestamp() == null ? Instant.now() : request.timestamp();

    Map<String, Object> payload = new HashMap<>();
    payload.put("eventType", request.eventType());
    payload.put("value", value);
    payload.put("timestamp", timestamp.toEpochMilli());

    try {
      String json = objectMapper.writeValueAsString(payload);
      return kafkaTemplate.send(topic, request.eventType(), json)
          .<Void>thenApply(result -> null)
          .exceptionally(error -> {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Event broker unavailable", error);
          });
    } catch (Exception e) {
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Event could not be published", e);
    }
  }
}
