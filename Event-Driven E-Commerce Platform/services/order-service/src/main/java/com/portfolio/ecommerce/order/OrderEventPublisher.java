package com.portfolio.ecommerce.order;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
public class OrderEventPublisher {
  private static final Logger logger = LoggerFactory.getLogger(OrderEventPublisher.class);

  private final KafkaTemplate<String, String> kafkaTemplate;
  private final ObjectMapper objectMapper;
  private final String orderCreatedTopic;

  public OrderEventPublisher(
      KafkaTemplate<String, String> kafkaTemplate,
      ObjectMapper objectMapper,
      @Value("${app.topics.order-created}") String orderCreatedTopic) {
    this.kafkaTemplate = kafkaTemplate;
    this.objectMapper = objectMapper;
    this.orderCreatedTopic = orderCreatedTopic;
  }

  public void publish(OrderCreatedEvent event) {
    try {
      String payload = objectMapper.copy().disable(com.fasterxml.jackson.databind.SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
          .writeValueAsString(event);
      OrderContract.validate(payload);
      kafkaTemplate.send(orderCreatedTopic, event.orderId(), payload).get(10, TimeUnit.SECONDS);
      logger.info("Published order.created event orderId={}", event.orderId());
    } catch (JsonProcessingException ex) {
      throw new IllegalStateException("Failed to serialize order event", ex);
    } catch (InterruptedException ex) {
      Thread.currentThread().interrupt();
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Order publication interrupted", ex);
    } catch (ExecutionException | TimeoutException | org.apache.kafka.common.KafkaException ex) {
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Order publication was not confirmed", ex);
    }
  }
}
