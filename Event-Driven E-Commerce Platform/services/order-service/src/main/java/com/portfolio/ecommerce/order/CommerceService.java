package com.portfolio.ecommerce.order;

import java.time.Instant;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
public class CommerceService {
  public record Product(String sku, String name, int priceCents, String currency) {}
  public static final List<Product> CATALOG = List.of(new Product("SKU-123", "Demo keyboard", 4900, "USD"),
      new Product("SKU-456", "Demo mouse", 2900, "USD"), new Product("SKU-789", "Demo monitor", 19900, "USD"));
  private final SagaStore store;
  private final InventoryPort inventory;
  private final OrderEventPublisher publisher;
  public CommerceService(SagaStore store, InventoryPort inventory, OrderEventPublisher publisher) {
    this.store = store; this.inventory = inventory; this.publisher = publisher;
  }
  static ResponseStatusException error(HttpStatus status, String message) { return new ResponseStatusException(status, message); }
  static void customer(String id) {
    if (id == null || !id.matches("[A-Za-z0-9_-]{1,64}")) throw error(HttpStatus.BAD_REQUEST, "Use a synthetic customer id");
  }
  public List<OrderItem> cart(String id) { customer(id); return store.access(false, s -> s.carts.getOrDefault(id, List.of())); }
  public List<OrderItem> setCart(String id, List<OrderItem> items) {
    customer(id);
    if (items == null || items.size() > 100) throw error(HttpStatus.BAD_REQUEST, "At most 100 items");
    Map<String, Integer> totals = new TreeMap<>();
    for (var item : items) {
      if (item == null || CATALOG.stream().noneMatch(p -> p.sku().equals(item.sku())) || item.quantity() < 1 || item.quantity() > 1000)
        throw error(HttpStatus.BAD_REQUEST, "Unknown SKU or quantity outside 1..1000");
      totals.merge(item.sku(), item.quantity(), Integer::sum);
      if (totals.get(item.sku()) > 1000) throw error(HttpStatus.BAD_REQUEST, "Maximum 1000 units per SKU");
    }
    var normalized = totals.entrySet().stream().map(e -> new OrderItem(e.getKey(), e.getValue())).toList();
    return store.access(true, s -> { s.carts.put(id, normalized); return normalized; });
  }
  public SagaStore.Order checkout(String id, String key, String scenario) {
    customer(id);
    if (key == null || !key.matches("[A-Za-z0-9_-]{1,100}")) throw error(HttpStatus.BAD_REQUEST, "Idempotency-Key required");
    if (!Set.of("success", "payment_declined", "shipping_failed").contains(scenario))
      throw error(HttpStatus.BAD_REQUEST, "Unknown demo scenario");
    return store.access(true, s -> {
      String fullKey = id + ":" + key;
      var cart = s.carts.getOrDefault(id, List.of());
      if (s.checkoutKeys.containsKey(fullKey)) {
        var previous = s.orders.get(s.checkoutKeys.get(fullKey));
        if (!previous.scenario.equals(scenario) || (!cart.isEmpty() && !previous.items.equals(cart)))
          throw error(HttpStatus.CONFLICT, "Idempotency key reused with a different checkout");
        return previous;
      }
      if (cart.isEmpty()) throw error(HttpStatus.BAD_REQUEST, "Cart is empty");
      SagaStore.Order order = new SagaStore.Order();
      order.orderId = UUID.randomUUID().toString(); order.customerId = id;
      order.createdAt = Instant.now().toString(); order.items = new ArrayList<>(cart); order.scenario = scenario;
      order.amountCents = cart.stream().mapToLong(i -> (long) CATALOG.stream().filter(p -> p.sku().equals(i.sku())).findFirst().orElseThrow().priceCents() * i.quantity()).sum();
      s.orders.put(order.orderId, order); s.checkoutKeys.put(fullKey, order.orderId); s.carts.remove(id);
      return order; // Persisted outbox: Kafka outages do not lose an accepted checkout.
    });
  }
  public SagaStore.Order get(String id) {
    return store.access(false, s -> {
      var result = s.orders.get(id);
      if (result == null) throw error(HttpStatus.NOT_FOUND, "Order not found");
      return result;
    });
  }
  public List<Map<String, String>> notifications(String id) {
    customer(id);
    return store.access(false, s -> s.notifications.values().stream().filter(n -> id.equals(n.get("customerId"))).toList());
  }
  public void accept(OrderCreatedEvent event) {
    store.access(true, s -> {
      var previous = s.orders.get(event.orderId());
      if (previous != null) {
        if (!previous.customerId.equals(event.customerId()) || !previous.items.equals(event.items()))
          throw new IllegalArgumentException("Order id reused with different content");
        return null;
      }
      var order = new SagaStore.Order();
      order.orderId = event.orderId(); order.customerId = event.customerId();
      order.items = event.items(); order.createdAt = event.createdAt().toString(); order.published = true;
      order.amountCents = order.items.stream().mapToLong(i -> CATALOG.stream().filter(p -> p.sku().equals(i.sku()))
          .mapToLong(p -> (long) p.priceCents() * i.quantity()).findFirst().orElse(0)).sum();
      s.orders.put(order.orderId, order);
      return null;
    });
  }
  private void step(SagaStore.Order o, String status) {
    if (!o.status.equals(status)) o.history.add(status);
    o.status = status;
  }
  private void notify(SagaStore.State s, SagaStore.Order o) {
    s.notifications.put(o.orderId, Map.of("orderId", o.orderId, "customerId", o.customerId,
        "channel", "LOCAL_INBOX", "message", "Order " + o.status, "createdAt", Instant.now().toString()));
  }
  private void requestCompensation(SagaStore.Order o, String reason) {
    o.reason = reason;
    step(o, "COMPENSATING");
    o.lastError = null;
  }
  private void finishCompensation(String id) {
    if (!get(id).status.equals("COMPENSATING")) return;
    inventory.release(id); // Outside SQL transactions; retry is safe after a crash.
    store.access(true, s -> {
      var o = s.orders.get(id);
      if (!o.status.equals("COMPENSATING")) return null;
      if (o.payment.equals("PAID")) o.payment = "REFUNDED";
      o.lastError = null;
      step(o, "COMPENSATED"); notify(s, o); return null;
    });
  }
  public SagaStore.Order cancel(String id) {
    return store.access(true, s -> {
      var o = s.orders.get(id);
      if (o == null) throw error(HttpStatus.NOT_FOUND, "Order not found");
      if (!Set.of("COMPENSATED", "COMPENSATING").contains(o.status))
        requestCompensation(o, "Customer cancelled demo order");
      return o;
    });
  }
  public void tick() {
    var ids = store.access(false, s -> s.orders.values().stream()
        .filter(o -> !Set.of("DELIVERED", "COMPENSATED").contains(o.status)).map(o -> o.orderId).limit(20).toList());
    for (String id : ids) {
      try {
        var snapshot = get(id);
        if (snapshot.status.equals("COMPENSATING")) { finishCompensation(id); continue; }
        if (Set.of("DELIVERED", "COMPENSATED").contains(snapshot.status)) continue;
        if (!snapshot.published) {
          publisher.publish(new OrderCreatedEvent(snapshot.orderId, snapshot.customerId, snapshot.items, Instant.parse(snapshot.createdAt)));
          store.access(true, s -> {
            var o = s.orders.get(id);
            if (!o.published) { o.published = true; o.history.add("PUBLISHED"); }
            return null;
          });
        }
        var reservation = inventory.get(id);
        if (reservation == null) continue;
        store.access(true, s -> {
          var o = s.orders.get(id);
          // Cancellation may have arrived while Kafka or inventory was unavailable.
          if (Set.of("DELIVERED", "COMPENSATED", "COMPENSATING").contains(o.status)) return null;
          o.lastError = null;
          if (!reservation.status().equals("RESERVED")) {
            o.reason = "Inventory " + reservation.status();
            step(o, "COMPENSATED"); notify(s, o); return null;
          }
          step(o, "RESERVED");
          if (o.scenario.equals("payment_declined")) {
            o.payment = "DECLINED"; requestCompensation(o, "Demo payment declined"); return null;
          }
          o.payment = "PAID"; step(o, "PAID"); // Simulated only: chargedCents remains zero.
          if (o.scenario.equals("shipping_failed")) {
            o.shipment = "FAILED"; requestCompensation(o, "Demo shipping failed"); return null;
          }
          o.shipment = "DELIVERED"; step(o, "DELIVERED"); notify(s, o); return null;
        });
        finishCompensation(id);
      } catch (RuntimeException ex) {
        store.access(true, s -> {
          var o = s.orders.get(id);
          if (!Set.of("DELIVERED", "COMPENSATED").contains(o.status)) o.lastError = ex.getClass().getSimpleName();
          return null;
        });
      }
    }
  }
}
