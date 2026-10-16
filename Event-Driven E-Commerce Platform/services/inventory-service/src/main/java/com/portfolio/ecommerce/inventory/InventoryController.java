package com.portfolio.ecommerce.inventory;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/inventory")
public class InventoryController {
  @org.springframework.web.bind.annotation.PostMapping("/reservations/{orderId}/release")
  public InventoryStore.Reservation release(@PathVariable String orderId) {
    return inventoryStore.release(orderId);
  }
  private final InventoryStore inventoryStore;

  public InventoryController(InventoryStore inventoryStore) {
    this.inventoryStore = inventoryStore;
  }

  @GetMapping("/{sku}")
  public InventoryResponse getInventory(@PathVariable String sku) {
    int available = inventoryStore.getAvailable(sku);
    return new InventoryResponse(sku, available);
  }

  @GetMapping("/reservations/{orderId}")
  public InventoryStore.Reservation getReservation(@PathVariable String orderId) {
    InventoryStore.Reservation result = inventoryStore.getReservation(orderId);
    if (result == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Reservation not found");
    return result;
  }
}
