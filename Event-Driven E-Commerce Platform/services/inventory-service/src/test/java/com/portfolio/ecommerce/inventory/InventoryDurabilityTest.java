package com.portfolio.ecommerce.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import static org.junit.jupiter.api.Assertions.*;

class InventoryDurabilityTest {
  private OrderCreatedEvent event(String id, int qty) {
    return new OrderCreatedEvent(id, "alice", List.of(new OrderItem("SKU-123", qty)), Instant.now());
  }
  private InventoryStore database(String url) {
    return new InventoryStore(new JdbcTemplate(new DriverManagerDataSource(url, "sa", "")), new ObjectMapper().findAndRegisterModules());
  }
  @Test void reserveAndCompensationSurviveRestart(@TempDir Path directory) {
    String url = "jdbc:h2:file:" + directory.resolve("inventory").toString().replace('\\', '/');
    var first = database(url); first.reserve(event("durable", 4));
    var second = database(url); assertEquals(116, second.getAvailable("SKU-123"));
    second.reserve(event("durable", 4)); second.release("durable"); second.release("durable");
    var third = database(url); assertEquals(120, third.getAvailable("SKU-123"));
    third.reserve(event("durable", 4)); assertEquals(120, third.getAvailable("SKU-123"));
  }
  @Test void releaseBeforeDeliveryCreatesTombstone() {
    var store = new InventoryStore(); store.release("late");
    assertEquals("RELEASED", store.reserve(event("late", 5)).status()); assertEquals(120, store.getAvailable("SKU-123"));
  }
  @Test void conflictingDuplicateCannotConsumeDifferentStock() {
    var store = new InventoryStore(); store.reserve(event("same", 5));
    assertThrows(IllegalArgumentException.class, () -> store.reserve(event("same", 8)));
    assertEquals(115, store.getAvailable("SKU-123"));
  }
  @Test void concurrentDatabaseClientsCannotOversell() throws Exception {
    String url = "jdbc:h2:mem:" + UUID.randomUUID() + ";DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000";
    var first = database(url); var second = database(url);
    try (var pool = Executors.newFixedThreadPool(8)) {
      List<Callable<InventoryStore.Reservation>> calls = new ArrayList<>();
      for (int i = 0; i < 40; i++) {
        final int n = i;
        calls.add(() -> (n % 2 == 0 ? first : second).reserve(event("parallel-" + n, 5)));
      }
      long accepted = 0;
      for (var future : pool.invokeAll(calls)) if (future.get().status().equals("RESERVED")) accepted++;
      assertEquals(24, accepted); assertEquals(0, first.getAvailable("SKU-123"));
    }
  }
}
