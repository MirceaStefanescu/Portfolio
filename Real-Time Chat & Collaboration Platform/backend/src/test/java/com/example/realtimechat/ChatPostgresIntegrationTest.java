package com.example.realtimechat;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.realtimechat.model.ChatRoomRequest;
import com.example.realtimechat.service.ChatService;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
    "app.demo-auth=true",
    "spring.kafka.listener.auto-startup=false",
    "spring.kafka.admin.auto-create=false"
})
@EnabledIfEnvironmentVariable(named = "CHAT_TEST_DB_URL", matches = ".+")
class ChatPostgresIntegrationTest {
  @DynamicPropertySource
  static void database(DynamicPropertyRegistry registry) {
    registry.add("spring.datasource.url", () -> System.getenv("CHAT_TEST_DB_URL"));
    registry.add("spring.datasource.username", () -> System.getenv("CHAT_TEST_DB_USER"));
    registry.add("spring.datasource.password", () -> System.getenv("CHAT_TEST_DB_PASSWORD"));
  }

  @Autowired Flyway flyway;
  @Autowired ChatService chatService;
  @Autowired TestRestTemplate http;

  @Test
  void migratesPostgresAndServesPersistedRooms() {
    assertThat(flyway.info().current().getVersion().getVersion()).isEqualTo("1");
    assertThat(flyway.validateWithResult().validationSuccessful).isTrue();
    var room = chatService.createRoom(new ChatRoomRequest("postgres-integration"));
    var response = http.getForEntity("/api/rooms", String.class);
    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
    assertThat(response.getBody()).contains(room.id().toString(), "postgres-integration");
    var health = http.getForEntity("/actuator/health", String.class);
    assertThat(health.getStatusCode()).isEqualTo(HttpStatus.OK);
    assertThat(health.getBody()).contains("UP");
  }
}
