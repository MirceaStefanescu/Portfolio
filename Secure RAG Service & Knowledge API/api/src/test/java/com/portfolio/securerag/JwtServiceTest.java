package com.portfolio.securerag;

import com.portfolio.securerag.config.SecurityProperties;
import com.portfolio.securerag.security.JwtService;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;
import javax.crypto.SecretKey;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtServiceTest {
    private final SecurityProperties properties = properties();
    private final JwtService service = new JwtService(properties);
    private final SecretKey signingKey = Keys.hmacShaKeyFor(
            properties.getJwt().getSecret().getBytes(StandardCharsets.UTF_8));

    @Test
    void expiredSignedTokenIsRejected() {
        String token = Jwts.builder().subject("alice")
                .issuer(properties.getJwt().getIssuer())
                .expiration(Date.from(Instant.EPOCH))
                .signWith(signingKey, Jwts.SIG.HS256).compact();
        assertThrows(ExpiredJwtException.class, () -> service.parseToken(token));
    }

    @Test
    void tokenSignedByAnotherKeyIsRejected() {
        String token = Jwts.builder().subject("alice")
                .issuer(properties.getJwt().getIssuer())
                .signWith(Jwts.SIG.HS256.key().build()).compact();
        assertThrows(JwtException.class, () -> service.parseToken(token));
    }

    @Test
    void unsignedClaimsCannotBeAcceptedAsAuthenticated() {
        String token = Jwts.builder().subject("alice")
                .issuer(properties.getJwt().getIssuer()).compact();
        assertThrows(JwtException.class, () -> service.parseToken(token));
    }

    private static SecurityProperties properties() {
        SecurityProperties properties = new SecurityProperties();
        properties.getJwt().setSecret(UUID.randomUUID().toString());
        return properties;
    }
}
