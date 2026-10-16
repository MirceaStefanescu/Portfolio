package com.portfolio.ecommerce.inventory;

import com.networknt.schema.*;
import com.networknt.schema.dialect.Dialects;
import java.nio.charset.StandardCharsets;

/** Bundled contract: validation requires no remote service or network schema loading. */
public final class OrderContract {
  private static final Schema SCHEMA = SchemaRegistry.withDialect(Dialects.getDraft7())
      .getSchema(text(), InputFormat.JSON);
  private OrderContract() {}
  public static String text() {
    try (var input = OrderContract.class.getResourceAsStream("/order-created.schema.json")) {
      if (input == null) throw new IllegalStateException("Missing order contract");
      return new String(input.readAllBytes(), StandardCharsets.UTF_8);
    } catch (java.io.IOException ex) { throw new IllegalStateException(ex); }
  }
  public static void validate(String payload) {
    try {
    var errors = SCHEMA.validate(payload, InputFormat.JSON,
        context -> context.executionConfig(config -> config.formatAssertionsEnabled(true)));
    if (!errors.isEmpty()) throw new IllegalArgumentException("Invalid order.created contract: " + errors.getFirst().getMessage());
    } catch (java.io.UncheckedIOException ex) { throw new IllegalArgumentException("Invalid order.created JSON", ex); }
  }
}
