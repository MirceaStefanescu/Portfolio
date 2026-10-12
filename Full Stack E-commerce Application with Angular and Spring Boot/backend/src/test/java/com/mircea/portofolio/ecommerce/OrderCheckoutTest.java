package com.mircea.portofolio.ecommerce;

import static org.junit.jupiter.api.Assertions.*;
import com.mircea.portofolio.ecommerce.dto.*;
import com.mircea.portofolio.ecommerce.model.*;
import com.mircea.portofolio.ecommerce.repository.*;
import com.mircea.portofolio.ecommerce.service.*;
import java.util.List;
import java.util.Collections;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import jakarta.validation.Validator;

@SpringBootTest
@ActiveProfiles("test")
@Transactional
class OrderCheckoutTest {
    @Autowired OrderService service;
    @Autowired ProductRepository products;
    @Autowired UserRepository users;
    @Autowired OrderRepository orders;
    @Autowired Validator validator;
    Product product;
    String email = "buyer@example.test";

    @BeforeEach void setup() {
        users.save(new User(email, "unused-test-hash", "Buyer"));
        product = products.findAll().getFirst();
    }
    CreateOrderRequest request(String currency) {
        return new CreateOrderRequest(List.of(new OrderItemRequest(product.getId(), 2)), currency);
    }
    @Test void createsAndConfirmsDemoOrderWithServerPrices() {
        OrderResponse created = service.createOrder(email, request("USD"));
        assertEquals(product.getPrice().multiply(java.math.BigDecimal.valueOf(2)), created.totalAmount());
        assertEquals("usd", created.currency());
        assertEquals("PENDING", created.status());
        assertEquals("PAID", service.confirmPayment(email, created.id(), created.paymentIntentId()).status());
        assertEquals("PAID", service.confirmPayment(email, created.id(), created.paymentIntentId()).status());
    }
    @Test void rejectsOtherCurrenciesAndInactiveProducts() {
        assertEquals(400, assertThrows(ResponseStatusException.class,
                () -> service.createOrder(email, request("jpy"))).getStatusCode().value());
        product.setActive(false);
        products.save(product);
        assertEquals(400, assertThrows(ResponseStatusException.class,
                () -> service.createOrder(email, request("usd"))).getStatusCode().value());
        assertEquals(0, orders.count());
    }
    @Test void protectsOrderOwnershipAndIntentIdentity() {
        OrderResponse created = service.createOrder(email, request("usd"));
        assertEquals(403, assertThrows(ResponseStatusException.class,
                () -> service.confirmPayment("other@example.test", created.id(), created.paymentIntentId())).getStatusCode().value());
        assertEquals(400, assertThrows(ResponseStatusException.class,
                () -> service.confirmPayment(email, created.id(), "pi_other")).getStatusCode().value());
        assertEquals(OrderStatus.PENDING, orders.findById(created.id()).orElseThrow().getStatus());
    }
    @Test void nullItemsAreValidationErrors() {
        assertFalse(validator.validate(new CreateOrderRequest(Collections.singletonList(null), "usd")).isEmpty());
    }
}
