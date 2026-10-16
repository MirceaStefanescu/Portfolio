package com.portfolio.ecommerce.order;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class OrderEventPublisherTest {
  @SuppressWarnings("unchecked")
  private final KafkaTemplate<String, String> template = mock(KafkaTemplate.class);
  private final OrderEventPublisher publisher = new OrderEventPublisher(template,
      new ObjectMapper().findAndRegisterModules(), "order.created");
  private final OrderCreatedEvent event = new OrderCreatedEvent("one", "test",
      List.of(new OrderItem("SKU-123", 2)), Instant.now());

  @Test void successfulAcknowledgementCompletesPublication() {
    when(template.send(anyString(), anyString(), anyString())).thenReturn(CompletableFuture.completedFuture(null));
    assertDoesNotThrow(() -> publisher.publish(event));
    verify(template).send(eq("order.created"), eq("one"), contains("SKU-123"));
  }

  @Test void failedAcknowledgementIsUnavailableInsteadOfCreated() {
    when(template.send(anyString(), anyString(), anyString()))
        .thenReturn(CompletableFuture.failedFuture(new IllegalStateException("broker unavailable")));
    assertEquals(503, assertThrows(ResponseStatusException.class,
        () -> publisher.publish(event)).getStatusCode().value());
  }

  @Test void synchronousBrokerFailureIsUnavailable() {
    when(template.send(anyString(), anyString(), anyString()))
        .thenThrow(new org.apache.kafka.common.errors.TimeoutException("metadata unavailable"));
    assertEquals(503, assertThrows(ResponseStatusException.class,
        () -> publisher.publish(event)).getStatusCode().value());
  }
}
