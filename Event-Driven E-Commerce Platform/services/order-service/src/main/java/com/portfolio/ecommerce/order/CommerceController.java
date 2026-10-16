package com.portfolio.ecommerce.order;

import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class CommerceController {
  private final CommerceService commerce;
  public record Cart(List<OrderItem> items) {}
  public record Checkout(String scenario) {}
  public CommerceController(CommerceService commerce) { this.commerce = commerce; }
  @GetMapping("/catalog") public List<CommerceService.Product> catalog() { return CommerceService.CATALOG; }
  @GetMapping("/carts/{customer}") public List<OrderItem> cart(@PathVariable String customer) { return commerce.cart(customer); }
  @PutMapping("/carts/{customer}") public List<OrderItem> cart(@PathVariable String customer, @RequestBody Cart cart) { return commerce.setCart(customer, cart.items()); }
  @PostMapping("/carts/{customer}/checkout")
  @ResponseStatus(org.springframework.http.HttpStatus.ACCEPTED)
  public SagaStore.Order checkout(@PathVariable String customer, @RequestHeader("Idempotency-Key") String key, @RequestBody Checkout body) {
    return commerce.checkout(customer, key, body.scenario() == null ? "success" : body.scenario());
  }
  @GetMapping("/orders/{id}") public SagaStore.Order order(@PathVariable String id) { return commerce.get(id); }
  @PostMapping("/orders/{id}/cancel")
  @ResponseStatus(org.springframework.http.HttpStatus.ACCEPTED)
  public SagaStore.Order cancel(@PathVariable String id) { return commerce.cancel(id); }
  @GetMapping("/notifications/{customer}") public List<Map<String, String>> notifications(@PathVariable String customer) { return commerce.notifications(customer); }
}
