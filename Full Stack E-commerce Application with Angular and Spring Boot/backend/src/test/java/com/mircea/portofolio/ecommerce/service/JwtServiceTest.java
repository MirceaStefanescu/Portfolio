package com.mircea.portofolio.ecommerce.service;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class JwtServiceTest {
    private final String key = "test-only-not-for-deployment-0123456789abcdef";
    @Test void validatesIssuerAndSignature() {
        JwtService service = new JwtService(key, "shop", 60);
        String token = service.generateToken("buyer@example.test").token();
        assertTrue(service.isTokenValid(token));
        assertEquals("buyer@example.test", service.getSubject(token));
        assertFalse(new JwtService(key, "other-app", 60).isTokenValid(token));
        assertFalse(new JwtService(key + "different", "shop", 60).isTokenValid(token));
    }
    @Test void rejectsUnsafeConfiguration() {
        for (String secret : new String[]{"", "short", "change_me_to_a_long_random_string_at_least_32_bytes"}) {
            assertThrows(IllegalArgumentException.class, () -> new JwtService(secret, "shop", 60));
        }
        assertThrows(IllegalArgumentException.class, () -> new JwtService(key, "shop", 0));
    }
}
