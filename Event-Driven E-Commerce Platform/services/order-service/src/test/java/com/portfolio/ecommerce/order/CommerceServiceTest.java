package com.portfolio.ecommerce.order;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class CommerceServiceTest {
  private final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
  private final InventoryPort inventory = mock(InventoryPort.class);
  private final OrderEventPublisher publisher = mock(OrderEventPublisher.class);
  private SagaStore database(String url) { return new SagaStore(new JdbcTemplate(new DriverManagerDataSource(url, "sa", "")), mapper); }
  private final SagaStore store = database("jdbc:h2:mem:" + UUID.randomUUID() + ";DB_CLOSE_DELAY=-1");
  private final CommerceService service = new CommerceService(store, inventory, publisher);
  private SagaStore.Order checkout(String scenario) {
    service.setCart("alice", List.of(new OrderItem("SKU-123", 2)));
    var o = service.checkout("alice", "same-key", scenario);
    when(inventory.get(o.orderId)).thenReturn(new InventoryPort.Reservation(o.orderId, "RESERVED", null));
    return o;
  }
  @Test void completeWorkflowUsesServerPricesAndOneNotification() {
    var o = checkout("success"); service.tick(); service.tick();
    var completed = service.get(o.orderId);
    assertEquals("DELIVERED", completed.status); assertEquals("PAID", completed.payment);
    assertEquals(9800, completed.amountCents); assertEquals(0, completed.chargedCents);
    assertEquals(1, service.notifications("alice").size()); assertTrue(service.notifications("bob").isEmpty());
    verify(publisher, times(1)).publish(any()); verify(inventory, never()).release(any());
  }
  @Test void paymentDeclineReleasesWithoutCharging() {
    var o = checkout("payment_declined"); service.tick();
    assertEquals("COMPENSATED", service.get(o.orderId).status);
    assertEquals("DECLINED", service.get(o.orderId).payment); verify(inventory).release(o.orderId);
  }
  @Test void shippingFailureRefundsAndCompensates() {
    var o = checkout("shipping_failed"); service.tick();
    assertEquals("REFUNDED", service.get(o.orderId).payment);
    assertEquals("FAILED", service.get(o.orderId).shipment);
    assertEquals("COMPENSATED", service.get(o.orderId).status);
  }
  @Test void failedCompensationIsVisibleAndResumed() {
    var o = checkout("shipping_failed");
    doThrow(new IllegalStateException("inventory down")).doNothing().when(inventory).release(o.orderId);
    service.tick(); assertEquals("COMPENSATING", service.get(o.orderId).status);
    assertNotNull(service.get(o.orderId).lastError); assertTrue(service.notifications("alice").isEmpty());
    service.tick(); assertEquals("COMPENSATED", service.get(o.orderId).status);
    assertNull(service.get(o.orderId).lastError); assertEquals("REFUNDED", service.get(o.orderId).payment);
  }
  @Test void brokerOutageKeepsOutboxAndRecovers() {
    var o = checkout("success");
    doThrow(new IllegalStateException("broker down")).doNothing().when(publisher).publish(any());
    service.tick(); assertFalse(service.get(o.orderId).published);
    assertEquals("CREATED", service.get(o.orderId).status);
    service.tick(); assertEquals("DELIVERED", service.get(o.orderId).status);
  }
  @Test void insufficientStockDoesNotPay() {
    var o = checkout("success");
    when(inventory.get(o.orderId)).thenReturn(new InventoryPort.Reservation(o.orderId, "REJECTED", "stock"));
    service.tick(); assertEquals("NOT_CHARGED", service.get(o.orderId).payment);
    assertEquals("COMPENSATED", service.get(o.orderId).status);
  }
  @Test void idempotencyRejectsConflictsAndDuplicateCancellationDoesNotRefundTwice() {
    var o = checkout("success");
    assertEquals(o.orderId, service.checkout("alice", "same-key", "success").orderId);
    assertEquals(409, assertThrows(ResponseStatusException.class,
        () -> service.checkout("alice", "same-key", "payment_declined")).getStatusCode().value());
    service.tick(); service.cancel(o.orderId); service.cancel(o.orderId); service.tick();
    assertEquals("REFUNDED", service.get(o.orderId).payment); verify(inventory, times(1)).release(o.orderId);
  }
  @Test void cancelBeforePublicationPreventsLaterTick() {
    var o = checkout("success"); service.cancel(o.orderId); service.tick();
    verify(publisher, never()).publish(any()); verify(inventory).release(o.orderId);
    assertEquals("COMPENSATED", service.get(o.orderId).status);
  }
  @Test void invalidCartDoesNotMutateAndIsIsolated() {
    service.setCart("alice", List.of(new OrderItem("SKU-123", 2)));
    assertThrows(ResponseStatusException.class, () -> service.setCart("alice", List.of(new OrderItem("unknown", 1))));
    assertEquals(2, service.cart("alice").getFirst().quantity()); assertTrue(service.cart("bob").isEmpty());
    assertThrows(ResponseStatusException.class, () -> service.checkout("bob", "key", "success"));
  }
  @Test void restartRetainsOutboxAndCheckoutKey(@TempDir Path directory) {
    String url = "jdbc:h2:file:" + directory.resolve("orders").toString().replace('\\', '/');
    var first = new CommerceService(database(url), inventory, publisher);
    first.setCart("alice", List.of(new OrderItem("SKU-456", 1)));
    var o = first.checkout("alice", "restart", "success");
    var second = new CommerceService(database(url), inventory, publisher);
    assertEquals(o.orderId, second.checkout("alice", "restart", "success").orderId);
    when(inventory.get(o.orderId)).thenReturn(new InventoryPort.Reservation(o.orderId, "RESERVED", null));
    second.tick(); assertEquals("DELIVERED", second.get(o.orderId).status);
  }
  @Test void duplicateEventsRejectChangedContents() {
    var event = new OrderCreatedEvent("external", "alice", List.of(new OrderItem("SKU-123", 1)), java.time.Instant.now());
    service.accept(event); service.accept(event);
    assertThrows(IllegalArgumentException.class, () -> service.accept(
        new OrderCreatedEvent("external", "bob", event.items(), event.createdAt())));
    assertEquals("alice", service.get("external").customerId);
  }
  @Test void blockedPublisherDoesNotHoldDatabaseLockAndCancellationWins() throws Exception {
    var o = checkout("success");
    var entered = new java.util.concurrent.CountDownLatch(1);
    var release = new java.util.concurrent.CountDownLatch(1);
    doAnswer(call -> {
      entered.countDown();
      if (!release.await(10, java.util.concurrent.TimeUnit.SECONDS)) throw new IllegalStateException("Test did not release publisher");
      return null;
    }).when(publisher).publish(any());
    try (var pool = java.util.concurrent.Executors.newSingleThreadExecutor()) {
      var task = pool.submit(service::tick);
      assertTrue(entered.await(3, java.util.concurrent.TimeUnit.SECONDS));
      try {
        assertTimeoutPreemptively(java.time.Duration.ofSeconds(1), () -> {
          assertEquals("CREATED", service.get(o.orderId).status);
          service.setCart("bob", List.of(new OrderItem("SKU-456", 1)));
          assertEquals("CREATED", service.checkout("bob", "during-outage", "success").status);
          assertEquals("COMPENSATING", service.cancel(o.orderId).status);
        });
      } finally { release.countDown(); }
      task.get(3, java.util.concurrent.TimeUnit.SECONDS);
      assertEquals("COMPENSATED", service.get(o.orderId).status);
      assertEquals("NOT_CHARGED", service.get(o.orderId).payment);
    }
  }
}
