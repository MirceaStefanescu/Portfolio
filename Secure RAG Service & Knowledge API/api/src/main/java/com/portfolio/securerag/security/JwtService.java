package com.portfolio.securerag.security;

import com.portfolio.securerag.config.SecurityProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class JwtService {

    private final SecurityProperties securityProperties;
    private final Key signingKey;

    public JwtService(SecurityProperties securityProperties) {
        this.securityProperties = securityProperties;
        this.signingKey = buildKey(securityProperties.getJwt().getSecret());
    }

    public String generateToken(String username, List<String> roles) {
        Instant now = Instant.now();
        Instant expiry = now.plusSeconds(securityProperties.getJwt().getTtlSeconds());

        return Jwts.builder()
                .setSubject(username)
                .setIssuer(securityProperties.getJwt().getIssuer())
                .setIssuedAt(Date.from(now))
                .setExpiration(Date.from(expiry))
                .claim("roles", roles)
                .signWith(signingKey, SignatureAlgorithm.HS256)
                .compact();
    }

    public Claims parseToken(String token) {
        return Jwts.parserBuilder()
                .requireIssuer(securityProperties.getJwt().getIssuer())
                .setSigningKey(signingKey)
                .build()
                .parseClaimsJws(token)
                .getBody();
    }

    private Key buildKey(String secret) {
        if (secret == null || secret.startsWith("dev-secret")) {
            throw new IllegalArgumentException("Configure a random JWT_SECRET.");
        }
        if (securityProperties.getJwt().getTtlSeconds() <= 0) {
            throw new IllegalArgumentException("JWT lifetime must be positive.");
        }
        byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
        if (keyBytes.length < 32) {
            throw new IllegalArgumentException("JWT secret must be at least 32 bytes.");
        }
        return Keys.hmacShaKeyFor(keyBytes);
    }
}
