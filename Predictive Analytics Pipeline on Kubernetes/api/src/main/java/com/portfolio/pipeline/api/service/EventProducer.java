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
import org.springframework.beans.factory.annotation.Autowired;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.StatusCode;

@Service
public class EventProducer {
  private final KafkaTemplate<String, String> kafkaTemplate;
  private final ObjectMapper objectMapper;
  private final String topic;
  private OpenTelemetry telemetry = OpenTelemetry.noop();

  @Autowired
  public void setTelemetry(OpenTelemetry telemetry) { this.telemetry = telemetry; }

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

    if (request.value() == null) throw new IllegalArgumentException("value is required");
    double value = request.value();
    if (!Double.isFinite(value)) {
      throw new IllegalArgumentException("value must be finite");
    }
    Instant timestamp = request.timestamp() == null ? Instant.now() : request.timestamp();

    Map<String, Object> payload = new HashMap<>();
    payload.put("eventType", request.eventType());
    payload.put("value", value);
    payload.put("timestamp", timestamp.toEpochMilli());

    String json;
    try {
      json = objectMapper.writeValueAsString(payload);
    } catch (com.fasterxml.jackson.core.JsonProcessingException ex) {
      throw new IllegalArgumentException("Event cannot be encoded", ex);
    }
    EventContract.validate(json);
    var span = telemetry.getTracer("predictive-ingestion").spanBuilder("events.publish")
        .setSpanKind(SpanKind.PRODUCER).setAttribute("messaging.destination.name", topic)
        .setAttribute("event.type", request.eventType()).startSpan();
    try {
      return kafkaTemplate.send(topic, request.eventType(), json)
          .whenComplete((result, error) -> {
            if (error != null) { span.recordException(error); span.setStatus(StatusCode.ERROR); }
            else span.setStatus(StatusCode.OK);
            span.end();
          })
          .<Void>thenApply(result -> null)
          .exceptionally(error -> {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Event broker unavailable", error);
          });
    } catch (Exception e) {
      span.recordException(e); span.setStatus(StatusCode.ERROR); span.end();
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Event could not be published", e);
    }
  }
}
