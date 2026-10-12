package com.mircea.portofolio.ecommerce.service;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import javax.crypto.SecretKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class JwtService {
	private final String secret;
	private final String issuer;
	private final Duration ttl;

	public JwtService(
			@Value("${app.jwt.secret}") String secret,
			@Value("${app.jwt.issuer}") String issuer,
			@Value("${app.jwt.ttl-minutes}") long ttlMinutes
	) {
        if (secret == null || secret.getBytes(StandardCharsets.UTF_8).length < 32
                || secret.startsWith("change_me")) {
            throw new IllegalArgumentException("Configure JWT_SECRET with at least 32 random bytes");
        }
        if (issuer == null || issuer.isBlank() || ttlMinutes <= 0) {
            throw new IllegalArgumentException("JWT issuer and positive lifetime are required");
        }
        this.secret = secret;
		this.issuer = issuer;
		this.ttl = Duration.ofMinutes(ttlMinutes);
	}

	public JwtToken generateToken(String subject) {
		Instant now = Instant.now();
		Instant expiresAt = now.plus(ttl);
		String token = Jwts.builder()
				.subject(subject)
				.issuer(issuer)
				.issuedAt(java.util.Date.from(now))
				.expiration(java.util.Date.from(expiresAt))
				.signWith(signingKey())
				.compact();
		return new JwtToken(token, expiresAt);
	}

	public String getSubject(String token) {
		Claims claims = parseClaims(token);
		return claims.getSubject();
	}

	public boolean isTokenValid(String token) {
		try {
			parseClaims(token);
			return true;
		} catch (JwtException | IllegalArgumentException ex) {
			return false;
		}
	}

	private Claims parseClaims(String token) {
		return Jwts.parser()
				.verifyWith(signingKey())
                .requireIssuer(issuer)
				.build()
				.parseSignedClaims(token)
				.getPayload();
	}

	private SecretKey signingKey() {
		byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
		if (keyBytes.length < 32) {
			throw new IllegalStateException("JWT secret must be at least 32 bytes");
		}
		return Keys.hmacShaKeyFor(keyBytes);
	}
}
