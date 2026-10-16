package com.portfolio.ecommerce.order;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.HttpClientErrorException;

@Component
public class InventoryPort {
  public record Reservation(String orderId, String status, String reason) {}
  private final RestClient client;
  public InventoryPort(@Value("${app.inventory-url:http://localhost:8082}") String url) {
    var factory = new SimpleClientHttpRequestFactory();
    factory.setConnectTimeout(2000);
    factory.setReadTimeout(3000);
    client = RestClient.builder().baseUrl(url).requestFactory(factory).build();
  }
  public Reservation get(String id) {
    try { return client.get().uri("/api/inventory/reservations/{id}", id).retrieve().body(Reservation.class); }
    catch (HttpClientErrorException.NotFound ex) { return null; }
  }
  public void release(String id) {
    client.post().uri("/api/inventory/reservations/{id}/release", id).retrieve().toBodilessEntity();
  }
}
