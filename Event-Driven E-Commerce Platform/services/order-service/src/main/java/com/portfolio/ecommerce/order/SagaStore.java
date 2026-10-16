package com.portfolio.ecommerce.order;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import java.util.function.Function;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.stereotype.Component;

@Component
public class SagaStore {
  public static class Order {
    public String orderId, customerId, createdAt, scenario = "success", status = "CREATED";
    public String payment = "NOT_CHARGED", shipment = "NOT_CREATED", reason, lastError;
    public boolean published;
    public long amountCents, chargedCents = 0;
    public List<OrderItem> items = new ArrayList<>();
    public List<String> history = new ArrayList<>(List.of("CREATED"));
  }
  public static class State {
    public Map<String, List<OrderItem>> carts = new LinkedHashMap<>();
    public Map<String, Order> orders = new LinkedHashMap<>();
    public Map<String, String> checkoutKeys = new LinkedHashMap<>();
    public Map<String, Map<String, String>> notifications = new LinkedHashMap<>();
  }
  private final JdbcTemplate jdbc;
  private final ObjectMapper mapper;
  private final TransactionTemplate transaction;
  public SagaStore(JdbcTemplate jdbc, ObjectMapper mapper) {
    this.jdbc = jdbc; this.mapper = mapper;
    transaction = new TransactionTemplate(new DataSourceTransactionManager(Objects.requireNonNull(jdbc.getDataSource())));
    jdbc.execute("CREATE TABLE IF NOT EXISTS commerce_state (id INT PRIMARY KEY, payload CLOB NOT NULL)");
    jdbc.update("INSERT INTO commerce_state(id,payload) SELECT 1,? WHERE NOT EXISTS (SELECT 1 FROM commerce_state WHERE id=1)", encode(new State()));
  }
  private String encode(State value) {
    try { return mapper.writeValueAsString(value); }
    catch (Exception ex) { throw new IllegalStateException(ex); }
  }
  public <T> T access(boolean write, Function<State, T> action) {
    return transaction.execute(status -> {
      State state;
      try { state = mapper.readValue(jdbc.queryForObject("SELECT payload FROM commerce_state WHERE id=1" + (write ? " FOR UPDATE" : ""), String.class), State.class); }
      catch (com.fasterxml.jackson.core.JsonProcessingException ex) { throw new IllegalStateException(ex); }
      T result = action.apply(state);
      if (write) jdbc.update("UPDATE commerce_state SET payload=? WHERE id=1", encode(state));
      return result;
    });
  }
}
