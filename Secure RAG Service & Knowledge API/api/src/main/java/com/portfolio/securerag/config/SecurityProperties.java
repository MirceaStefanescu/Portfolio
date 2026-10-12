package com.portfolio.securerag.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "security")
public class SecurityProperties {

    private String devApiKey = "";
    private final Jwt jwt = new Jwt();

    public String getDevApiKey() {
        return devApiKey;
    }

    public void setDevApiKey(String devApiKey) {
        this.devApiKey = devApiKey;
    }

    public Jwt getJwt() {
        return jwt;
    }

    public static class Jwt {
        private String secret = "";
        private String issuer = "secure-rag";
        private long ttlSeconds = 3600;

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public String getIssuer() {
            return issuer;
        }

        public void setIssuer(String issuer) {
            this.issuer = issuer;
        }

        public long getTtlSeconds() {
            return ttlSeconds;
        }

        public void setTtlSeconds(long ttlSeconds) {
            this.ttlSeconds = ttlSeconds;
        }
    }
}
