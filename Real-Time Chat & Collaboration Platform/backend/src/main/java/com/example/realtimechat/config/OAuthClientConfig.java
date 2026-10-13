package com.example.realtimechat.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.oauth2.client.CommonOAuth2Provider;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.registration.InMemoryClientRegistrationRepository;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "app.demo-auth", havingValue = "false", matchIfMissing = true)
public class OAuthClientConfig {
  @Bean
  ClientRegistrationRepository clientRegistrationRepository(
      @Value("${GITHUB_CLIENT_ID:}") String clientId,
      @Value("${GITHUB_CLIENT_SECRET:}") String clientSecret
  ) {
    if (clientId.isBlank() || clientSecret.isBlank()) {
      throw new IllegalStateException("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET are required unless DEMO_AUTH=true");
    }
    var github = CommonOAuth2Provider.GITHUB.getBuilder("github")
        .clientId(clientId)
        .clientSecret(clientSecret)
        .scope("read:user", "user:email")
        .build();
    return new InMemoryClientRegistrationRepository(github);
  }
}
