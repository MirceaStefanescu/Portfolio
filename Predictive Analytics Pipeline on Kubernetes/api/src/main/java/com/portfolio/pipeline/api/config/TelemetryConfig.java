package com.portfolio.pipeline.api.config;

import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.autoconfigure.AutoConfiguredOpenTelemetrySdk;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.util.Map;

@Configuration
public class TelemetryConfig {
  @Bean(destroyMethod="close")
  OpenTelemetrySdk openTelemetry() {
    return AutoConfiguredOpenTelemetrySdk.builder()
        .addPropertiesSupplier(() -> Map.of("otel.service.name", "predictive-api",
            "otel.metrics.exporter", "none", "otel.logs.exporter", "none",
            "otel.traces.exporter", System.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") == null ? "none" : "otlp"))
        .build().getOpenTelemetrySdk();
  }
}
