package com.portfolio.pipeline.api;

import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.pipeline.api.model.EventRequest;
import com.portfolio.pipeline.api.service.EventContract;
import com.portfolio.pipeline.api.service.EventProducer;
import com.portfolio.pipeline.api.service.PredictionQueryService;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.testcontainers.kafka.ConfluentKafkaContainer;
import org.testcontainers.postgresql.PostgreSQLContainer;

/** Runs with mvn verify. Missing Docker is a failure, not a silent skip. */
class PipelineContainersIT {
  @Test void acknowledgedEventsReachKafkaAndQueriesUseRealPostgres() throws Exception {
    try (var kafka = new ConfluentKafkaContainer("confluentinc/cp-kafka:7.9.10");
         var postgres = new PostgreSQLContainer("postgres:15")) {
      kafka.start(); postgres.start();
      String topic = "events-" + UUID.randomUUID();
      var factory = new DefaultKafkaProducerFactory<String, String>(Map.of(
          ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers(),
          ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class,
          ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class));
      var template = new KafkaTemplate<>(factory);
      try (var consumer = new KafkaConsumer<String, String>(Map.of(
               ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers(),
               ConsumerConfig.GROUP_ID_CONFIG, UUID.randomUUID().toString(),
               ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest",
               ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class,
               ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class))) {
        var producer = new EventProducer(template, new ObjectMapper(), topic);
        producer.publish(new EventRequest("sensor.temperature", 20.5, Instant.ofEpochMilli(1234)))
            .get(15, TimeUnit.SECONDS);
        consumer.subscribe(List.of(topic));
        String value = null;
        long deadline = System.nanoTime() + Duration.ofSeconds(15).toNanos();
        while (value == null && System.nanoTime() < deadline) {
          for (var record : consumer.poll(Duration.ofMillis(250))) value = record.value();
        }
        assertNotNull(value); EventContract.validate(value);
        assertEquals(20.5, new ObjectMapper().readTree(value).get("value").asDouble());
        assertThrows(IllegalArgumentException.class,
            () -> producer.publish(new EventRequest("sensor.temperature", null, null)));
      } finally { template.destroy(); factory.destroy(); }
      var data = new DriverManagerDataSource(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword());
      new ResourceDatabasePopulator(new ClassPathResource("schema.sql")).execute(data);
      var jdbc = new JdbcTemplate(data);
      jdbc.update("INSERT INTO predictions (event_type, window_start, window_end, event_count, avg_value, prediction_score) VALUES (?, ?, ?, ?, ?, ?)",
          "sensor.temperature", java.sql.Timestamp.from(Instant.EPOCH),
          java.sql.Timestamp.from(Instant.ofEpochSecond(30)), 4, 20.5, 0.4);
      var query = new PredictionQueryService(jdbc);
      assertEquals(1, query.fetchPredictions("sensor.temperature", 200).size());
      assertEquals(0, query.fetchPredictions("' OR 1=1 --", 200).size());
      assertEquals(4, query.fetchPredictions(null, 1).getFirst().eventCount());
    }
  }
}
