package com.portfolio.ecommerce.order;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import org.springframework.stereotype.Component;
import java.util.List;

@Component
public class CommerceMetrics {
  public CommerceMetrics(MeterRegistry registry, SagaStore store) {
    for (String state : List.of("CREATED", "RESERVED", "PAID", "DELIVERED", "COMPENSATING", "COMPENSATED")) {
      registry.gauge("commerce_orders", Tags.of("status", state), store,
          s -> s.access(false, data -> (double) data.orders.values().stream().filter(o -> o.status.equals(state)).count()));
    }
    registry.gauge("commerce_demo_charged_cents", store,
        s -> s.access(false, data -> (double) data.orders.values().stream().mapToLong(o -> o.chargedCents).sum()));
  }
}
