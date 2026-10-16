package com.portfolio.ecommerce.inventory;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import java.util.function.Function;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.stereotype.Component;

@Component
public class InventoryStore {
  private final JdbcTemplate jdbc;
  private final ObjectMapper mapper;
  private final TransactionTemplate transaction;
  public record Reservation(String orderId, String status, String reason) {}
  public static class State {
    public Map<String, Integer> stock = new HashMap<>();
    public Map<String, Reservation> reservations = new HashMap<>();
    public Map<String, Map<String, Integer>> quantities = new HashMap<>();
  }

  /** Each direct test gets an isolated real database; Spring uses its configured datasource. */
  public InventoryStore() {
    this(new JdbcTemplate(new DriverManagerDataSource("jdbc:h2:mem:" + UUID.randomUUID() + ";DB_CLOSE_DELAY=-1", "sa", "")),
        new ObjectMapper().findAndRegisterModules());
  }

  @Autowired
  public InventoryStore(JdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc;
    this.mapper = mapper;
    this.transaction = new TransactionTemplate(new DataSourceTransactionManager(Objects.requireNonNull(jdbc.getDataSource())));
    jdbc.execute("CREATE TABLE IF NOT EXISTS inventory_state (id INT PRIMARY KEY, payload CLOB NOT NULL)");
    State initial = new State();
    initial.stock.putAll(Map.of("SKU-123", 120, "SKU-456", 80, "SKU-789", 45));
    jdbc.update("INSERT INTO inventory_state(id,payload) SELECT 1,? WHERE NOT EXISTS (SELECT 1 FROM inventory_state WHERE id=1)", encode(initial));
  }

  private String encode(State value) {
    try { return mapper.writeValueAsString(value); }
    catch (Exception ex) { throw new IllegalStateException(ex); }
  }
  private <T> T access(boolean write, Function<State, T> action) {
    return transaction.execute(status -> {
      State state;
      try {
        state = mapper.readValue(jdbc.queryForObject("SELECT payload FROM inventory_state WHERE id=1" + (write ? " FOR UPDATE" : ""), String.class), State.class);
      } catch (com.fasterxml.jackson.core.JsonProcessingException ex) { throw new IllegalStateException(ex); }
      T result = action.apply(state);
      if (write) jdbc.update("UPDATE inventory_state SET payload=? WHERE id=1", encode(state));
      return result;
    });
  }

  public int getAvailable(String sku) { return access(false, s -> s.stock.getOrDefault(sku, 0)); }
  public Reservation getReservation(String id) { return access(false, s -> s.reservations.get(id)); }

  public Reservation reserve(OrderCreatedEvent event) {
    if (event == null || event.orderId() == null || event.orderId().isBlank()
        || event.items() == null || event.items().isEmpty()) throw new IllegalArgumentException("Order and items are required");
    Map<String, Integer> quantities = new TreeMap<>();
    for (OrderItem item : event.items()) {
      if (item == null || item.sku() == null || item.sku().isBlank() || item.quantity() <= 0)
        throw new IllegalArgumentException("SKU and positive quantity are required");
      try { quantities.merge(item.sku(), item.quantity(), Math::addExact); }
      catch (ArithmeticException ex) { throw new IllegalArgumentException("Quantity exceeds range", ex); }
    }
    return access(true, s -> {
      Reservation previous = s.reservations.get(event.orderId());
      if (previous != null) {
        var recorded = s.quantities.get(event.orderId());
        if (recorded != null && !recorded.equals(quantities)) throw new IllegalArgumentException("Order id reused with different items");
        return previous;
      }
      boolean available = quantities.entrySet().stream().allMatch(i -> s.stock.getOrDefault(i.getKey(), 0) >= i.getValue());
      if (available) quantities.forEach((sku, qty) -> s.stock.put(sku, s.stock.get(sku) - qty));
      Reservation result = new Reservation(event.orderId(), available ? "RESERVED" : "REJECTED", available ? null : "Insufficient stock");
      s.reservations.put(event.orderId(), result);
      s.quantities.put(event.orderId(), quantities);
      return result;
    });
  }

  /** A tombstone also prevents a delayed Kafka event from reserving after cancellation. */
  public Reservation release(String id) {
    if (id == null || id.isBlank()) throw new IllegalArgumentException("Order id required");
    return access(true, s -> {
      Reservation previous = s.reservations.get(id);
      if (previous != null && previous.status().equals("RESERVED"))
        s.quantities.get(id).forEach((sku, qty) -> s.stock.put(sku, Math.addExact(s.stock.get(sku), qty)));
      Reservation result = new Reservation(id, "RELEASED", "Saga compensation");
      s.reservations.put(id, result);
      return result;
    });
  }
}
