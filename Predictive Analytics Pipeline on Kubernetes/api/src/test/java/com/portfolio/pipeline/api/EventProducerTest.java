package com.portfolio.pipeline.api;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.pipeline.api.model.EventRequest;
import com.portfolio.pipeline.api.service.EventProducer;
import com.portfolio.pipeline.api.controller.AnalyticsController;
import java.time.Instant;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.web.server.ResponseStatusException;

class EventProducerTest {
  @SuppressWarnings("unchecked")
  KafkaTemplate<String,String> kafka = mock(KafkaTemplate.class);
  ObjectMapper mapper = new ObjectMapper();
  EventProducer producer = new EventProducer(kafka, mapper, "events");

  @Test void onlyAcknowledgesTheRequestAfterBrokerAcceptance() throws Exception {
    CompletableFuture<SendResult<String,String>> ack = new CompletableFuture<>();
    when(kafka.send(eq("events"),eq("purchase"),anyString())).thenReturn(ack);
    var controller = new AnalyticsController(producer, null, null);
    var response = controller.publishEvent(new EventRequest("purchase", 12.5, Instant.ofEpochMilli(1000)));
    assertFalse(response.isDone());
    ArgumentCaptor<String> json = ArgumentCaptor.forClass(String.class);
    verify(kafka).send(eq("events"),eq("purchase"),json.capture());
    assertEquals(1000, mapper.readTree(json.getValue()).get("timestamp").asLong());
    assertEquals(12.5, mapper.readTree(json.getValue()).get("value").asDouble());
    ack.complete(null);
    assertEquals(202, response.join().getStatusCode().value());
  }
  @Test void propagatesAsynchronousBrokerFailure() {
    when(kafka.send(anyString(),anyString(),anyString()))
      .thenReturn(CompletableFuture.failedFuture(new IllegalStateException("offline")));
    var error = assertThrows(CompletionException.class,
      () -> producer.publish(new EventRequest("purchase", 1.0, null)).join());
    var status = assertInstanceOf(ResponseStatusException.class, error.getCause());
    assertEquals(503, status.getStatusCode().value());
  }
  @Test void rejectsInvalidValuesBeforeSending() {
    assertThrows(IllegalArgumentException.class, () -> producer.publish(new EventRequest(" ",1.0,null)));
    assertThrows(IllegalArgumentException.class, () -> producer.publish(new EventRequest("purchase",Double.NaN,null)));
    assertThrows(IllegalArgumentException.class, () -> producer.publish(new EventRequest("purchase",Double.POSITIVE_INFINITY,null)));
    verifyNoInteractions(kafka);
  }
}
