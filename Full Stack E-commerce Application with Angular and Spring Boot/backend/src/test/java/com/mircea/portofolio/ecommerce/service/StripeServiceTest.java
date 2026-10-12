package com.mircea.portofolio.ecommerce.service;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

class StripeServiceTest {
    @Test void missingKeyFailsClosed() {
        StripeService service = new StripeService("", false);
        assertEquals(503, assertThrows(ResponseStatusException.class,
                () -> service.createPaymentIntent(100, "usd", 1L)).getStatusCode().value());
        assertEquals(503, assertThrows(ResponseStatusException.class,
                () -> service.retrievePaymentIntent("pi_real")).getStatusCode().value());
    }
    @Test void demoRequiresExplicitModeAndOnlyConfirmsDemoIds() throws Exception {
        StripeService service = new StripeService("", true);
        StripePaymentIntent intent = service.createPaymentIntent(100, "usd", 1L);
        assertEquals("requires_payment_method", intent.status());
        assertEquals("succeeded", service.retrievePaymentIntent(intent.id()).status());
        assertEquals(400, assertThrows(ResponseStatusException.class,
                () -> service.retrievePaymentIntent("pi_real")).getStatusCode().value());
    }
}
