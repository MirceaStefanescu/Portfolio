package com.portfolio.ecommerce.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class InventoryEventConsumerTest {
  private final InventoryStore store = new InventoryStore();
  private final InventoryEventConsumer consumer = new InventoryEventConsumer(
      new ObjectMapper().findAndRegisterModules(), store);

  private String event(String id, String items) {
    return "{\"orderId\":\"" + id + "\",\"customerId\":\"test\",\"items\":" + items
        + ",\"createdAt\":\"2026-10-16T00:00:00Z\"}";
  }

  @Test void duplicateDeliveryDoesNotReserveTwice() {
    String payload = event("duplicate", "[{\"sku\":\"SKU-123\",\"quantity\":2}]");
    consumer.handleOrderCreated(payload);
    consumer.handleOrderCreated(payload);
    assertEquals(118, store.getAvailable("SKU-123"));
  }

  @Test void shortageDoesNotPartiallyReserveOtherItems() {
    consumer.handleOrderCreated(event("shortage",
        "[{\"sku\":\"SKU-123\",\"quantity\":2},{\"sku\":\"SKU-456\",\"quantity\":81}]"));
    assertEquals(120, store.getAvailable("SKU-123"));
    assertEquals(80, store.getAvailable("SKU-456"));
  }

  @Test void repeatedSkuQuantitiesAreCheckedTogether() {
    consumer.handleOrderCreated(event("repeated-sku",
        "[{\"sku\":\"SKU-123\",\"quantity\":70},{\"sku\":\"SKU-123\",\"quantity\":70}]"));
    assertEquals(120, store.getAvailable("SKU-123"));
  }

  @Test void invalidQuantityCannotIncreaseStock() {
    assertThrows(IllegalArgumentException.class, () -> consumer.handleOrderCreated(event("invalid",
        "[{\"sku\":\"SKU-123\",\"quantity\":-4}]")));
    assertEquals(120, store.getAvailable("SKU-123"));
  }

  @Test void malformedPayloadIsNotAcknowledgedAsProcessed() {
    assertThrows(IllegalArgumentException.class, () -> consumer.handleOrderCreated("not JSON"));
  }

  @Test void validOrderReservesAllItems() {
    consumer.handleOrderCreated(event("valid",
        "[{\"sku\":\"SKU-123\",\"quantity\":2},{\"sku\":\"SKU-456\",\"quantity\":3}]"));
    assertEquals(118, store.getAvailable("SKU-123"));
    assertEquals(77, store.getAvailable("SKU-456"));
  }
}
