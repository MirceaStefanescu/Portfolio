package com.portfolio.ecommerce.inventory;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class OrderContractTest {
  private final String valid = "{\"orderId\":\"one\",\"customerId\":\"alice\",\"items\":[{\"sku\":\"SKU-123\",\"quantity\":1}],\"createdAt\":\"2026-10-16T00:00:00Z\"}";
  @Test void acceptsProducerContract() { assertDoesNotThrow(() -> OrderContract.validate(valid)); }
  @Test void rejectsBreakingTypesAndExtraFields() {
    assertThrows(IllegalArgumentException.class, () -> OrderContract.validate(valid.replace("\"quantity\":1", "\"quantity\":\"1\"")));
    assertThrows(IllegalArgumentException.class, () -> OrderContract.validate(valid.replace("\"quantity\":1", "\"quantity\":-1")));
    assertThrows(IllegalArgumentException.class, () -> OrderContract.validate(valid.replace("2026-10-16T00:00:00Z", "not-a-date")));
    assertThrows(IllegalArgumentException.class, () -> OrderContract.validate(valid.replace("\"orderId\"", "\"unknown\":true,\"orderId\"")));
  }
}
