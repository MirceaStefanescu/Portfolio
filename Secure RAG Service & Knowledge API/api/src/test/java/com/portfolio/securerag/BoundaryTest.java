package com.portfolio.securerag;

import static org.junit.jupiter.api.Assertions.*;
import com.portfolio.securerag.config.*;
import com.portfolio.securerag.controller.AuthController;
import com.portfolio.securerag.security.JwtService;
import com.portfolio.securerag.service.*;
import com.portfolio.securerag.model.QueryRequest;
import jakarta.validation.Validation;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;

class BoundaryTest {
    @Test void chunksStopAtEndWithoutRepeatedTail() {
        assertEquals(List.of("short text"), new Chunker().chunk("short text", 800, 120));
    }
    @Test void invalidChunkSettingsFailBeforeLooping() {
        assertTimeoutPreemptively(Duration.ofSeconds(1), () -> {
            for (int[] config : new int[][]{{0, 0}, {-1, 0}, {10, -1}, {10, 10}, {10, 11}}) {
                assertThrows(IllegalArgumentException.class, () -> new Chunker().chunk("example", config[0], config[1]));
            }
        });
    }
    @Test void rejectsDefaultCredentialsAndWrongIssuer() {
        SecurityProperties p = new SecurityProperties();
        assertThrows(IllegalArgumentException.class, () -> new JwtService(p));
        p.getJwt().setSecret("test-only-not-for-deployment-0123456789abcdef");
        JwtService jwt = new JwtService(p);
        assertThrows(IllegalArgumentException.class, () -> new AuthController(jwt, p, new AuditLogService(new AuditProperties())));
        p.setDevApiKey("test-api-key-only-not-for-deployment-123456");
        new AuthController(jwt, p, new AuditLogService(new AuditProperties()));
        String token = jwt.generateToken("tester", List.of("USER"));
        assertEquals("tester", jwt.parseToken(token).getSubject());
        p.getJwt().setIssuer("another-service");
        assertThrows(io.jsonwebtoken.JwtException.class, () -> jwt.parseToken(token));
    }
    @Test void boundedAuditKeepsOnlyNewestEvents() {
        AuditProperties p = new AuditProperties();
        p.setMaxEvents(0);
        assertThrows(IllegalArgumentException.class, () -> new AuditLogService(p));
        p.setMaxEvents(2);
        AuditLogService log = new AuditLogService(p);
        for (int i=0; i<3; i++) log.record("test", "TEST", String.valueOf(i), "OK", "");
        assertEquals(2, log.list(100).size());
        assertEquals("2", log.list(1).get(0).resource());
        assertThrows(IllegalArgumentException.class, () -> log.list(-1));
    }
    @Test void limitsRetrievalRequests() {
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var validator = factory.getValidator();
            assertTrue(validator.validate(new QueryRequest("question", 100)).isEmpty());
            assertFalse(validator.validate(new QueryRequest("question", 0)).isEmpty());
            assertFalse(validator.validate(new QueryRequest("question", 101)).isEmpty());
        }
    }
}
