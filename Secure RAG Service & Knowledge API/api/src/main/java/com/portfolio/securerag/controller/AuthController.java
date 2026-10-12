package com.portfolio.securerag.controller;

import com.portfolio.securerag.config.SecurityProperties;
import com.portfolio.securerag.model.TokenRequest;
import com.portfolio.securerag.model.TokenResponse;
import com.portfolio.securerag.security.JwtService;
import com.portfolio.securerag.service.AuditLogService;
import jakarta.validation.Valid;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final JwtService jwtService;
    private final SecurityProperties securityProperties;
    private final AuditLogService auditLogService;

    public AuthController(JwtService jwtService,
                          SecurityProperties securityProperties,
                          AuditLogService auditLogService) {
        this.jwtService = jwtService;
        if (securityProperties.getDevApiKey() == null || securityProperties.getDevApiKey().length() < 32) {
            throw new IllegalArgumentException("Configure DEV_API_KEY with at least 32 random characters.");
        }
        this.securityProperties = securityProperties;
        this.auditLogService = auditLogService;
    }

    @PostMapping("/token")
    public ResponseEntity<TokenResponse> token(@RequestHeader("X-Dev-Key") String devKey,
                                               @Valid @RequestBody TokenRequest request) {
        if (devKey == null || !java.security.MessageDigest.isEqual(
                securityProperties.getDevApiKey().getBytes(java.nio.charset.StandardCharsets.UTF_8),
                devKey.getBytes(java.nio.charset.StandardCharsets.UTF_8))) {
            auditLogService.record("anonymous", "TOKEN", request.username(), "DENIED", "invalid dev key");
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid dev key");
        }

        List<String> roles = request.roles();
        if (roles == null || roles.isEmpty()) {
            roles = List.of("USER");
        } else {
            roles = roles.stream()
                    .map(role -> role == null ? "" : role.trim().toUpperCase(Locale.ROOT))
                    .filter(role -> !role.isBlank())
                    .toList();
            if (roles.isEmpty()) {
                roles = List.of("USER");
            }
        }

        String token = jwtService.generateToken(request.username(), roles);
        Instant expiresAt = Instant.now().plusSeconds(securityProperties.getJwt().getTtlSeconds());
        auditLogService.record(request.username(), "TOKEN", "self", "OK", "roles=" + roles);

        return ResponseEntity.ok(new TokenResponse(token, expiresAt, request.username(), roles));
    }
}
