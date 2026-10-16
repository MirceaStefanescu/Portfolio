package com.portfolio.ecommerce.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

@Service
public class InventoryEventConsumer {
  private static final Logger logger = LoggerFactory.getLogger(InventoryEventConsumer.class);

  private final ObjectMapper objectMapper;
  private final InventoryStore inventoryStore;

  public InventoryEventConsumer(ObjectMapper objectMapper, InventoryStore inventoryStore) {
    this.objectMapper = objectMapper;
    this.inventoryStore = inventoryStore;
  }

  @KafkaListener(topics = "${app.topics.order-created}")
  public void handleOrderCreated(String payload) {
    OrderContract.validate(payload);
    OrderCreatedEvent event;
    try {
      event = objectMapper.readValue(payload, OrderCreatedEvent.class);
    } catch (com.fasterxml.jackson.core.JsonProcessingException ex) {
      throw new IllegalArgumentException("Invalid order.created event", ex);
    }
    InventoryStore.Reservation result = inventoryStore.reserve(event);
    logger.info("Inventory orderId={} status={}", result.orderId(), result.status());
  }
}
