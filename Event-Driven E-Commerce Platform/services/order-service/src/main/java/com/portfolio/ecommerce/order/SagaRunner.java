package com.portfolio.ecommerce.order;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@Configuration
@EnableScheduling
@ConditionalOnProperty(name="app.saga-enabled", havingValue="true", matchIfMissing=true)
public class SagaRunner {
  private final CommerceService commerce;
  private final ObjectMapper mapper;
  public SagaRunner(CommerceService commerce, ObjectMapper mapper) { this.commerce = commerce; this.mapper = mapper; }
  @Scheduled(fixedDelayString="${app.saga-interval-ms:1000}") public void tick() { commerce.tick(); }
  @KafkaListener(topics="${app.topics.order-created}", groupId="order-saga")
  public void accept(String payload) throws com.fasterxml.jackson.core.JsonProcessingException {
    OrderContract.validate(payload);
    commerce.accept(mapper.readValue(payload, OrderCreatedEvent.class));
  }
}
