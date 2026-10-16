package com.portfolio.ecommerce.order;

import java.util.Map;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/** Register the exact bundled contract; incompatible evolution fails startup. */
@Component
@ConditionalOnProperty(name="app.schema-registration-enabled", havingValue="true")
public class SchemaRegistration implements ApplicationRunner {
  private final RestClient client;
  public SchemaRegistration(@Value("${app.schema-registry-url}") String url) {
    var factory = new SimpleClientHttpRequestFactory();
    factory.setConnectTimeout(3000); factory.setReadTimeout(5000);
    client = RestClient.builder().baseUrl(url).requestFactory(factory).build();
  }
  public void run(ApplicationArguments arguments) {
    client.put().uri("/config/order.created-value").body(Map.of("compatibility", "BACKWARD")).retrieve().toBodilessEntity();
    client.post().uri("/subjects/order.created-value/versions")
        .body(Map.of("schemaType", "JSON", "schema", OrderContract.text())).retrieve().toBodilessEntity();
  }
}
