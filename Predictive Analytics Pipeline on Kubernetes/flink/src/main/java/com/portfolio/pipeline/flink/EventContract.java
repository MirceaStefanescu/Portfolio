package com.portfolio.pipeline.flink;

import com.networknt.schema.*;
import com.networknt.schema.dialect.Dialects;
import java.nio.charset.StandardCharsets;

/** This resource is identical at producer and consumer; no remote schema loading. */
public final class EventContract {
  private static final Schema SCHEMA = SchemaRegistry.withDialect(Dialects.getDraft7())
      .getSchema(text(), InputFormat.JSON);
  private EventContract() {}
  public static String text() {
    try (var input = EventContract.class.getResourceAsStream("/event.schema.json")) {
      if (input == null) throw new IllegalStateException("Missing event contract");
      return new String(input.readAllBytes(), StandardCharsets.UTF_8);
    } catch (java.io.IOException ex) { throw new IllegalStateException(ex); }
  }
  public static void validate(String payload) {
    try {
      var errors = SCHEMA.validate(payload, InputFormat.JSON);
      if (!errors.isEmpty()) throw new IllegalArgumentException("Invalid event contract: " + errors.get(0).getMessage());
    } catch (java.io.UncheckedIOException ex) { throw new IllegalArgumentException("Invalid event JSON", ex); }
  }
}
