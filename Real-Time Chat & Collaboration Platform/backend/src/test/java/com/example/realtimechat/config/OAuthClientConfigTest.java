package com.example.realtimechat.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;

class OAuthClientConfigTest {
  private final ApplicationContextRunner context = new ApplicationContextRunner()
      .withUserConfiguration(OAuthClientConfig.class);

  @Test
  void demoModeDoesNotRequireOAuthCredentials() {
    context.withPropertyValues("app.demo-auth=true").run(result -> {
      assertThat(result).hasNotFailed().doesNotHaveBean(ClientRegistrationRepository.class);
    });
  }

  @Test
  void normalModeRequiresCredentials() {
    context.run(result -> assertThat(result).hasFailed()
        .getFailure().hasRootCauseMessage(
            "GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET are required unless DEMO_AUTH=true"));
  }

  @Test
  void normalModeUsesGitHubRegistration() {
    context.withPropertyValues("GITHUB_CLIENT_ID=test-client", "GITHUB_CLIENT_SECRET=test-secret")
        .run(result -> {
          assertThat(result).hasNotFailed().hasSingleBean(ClientRegistrationRepository.class);
          var registration = result.getBean(ClientRegistrationRepository.class)
              .findByRegistrationId("github");
          assertThat(registration.getClientId()).isEqualTo("test-client");
          assertThat(registration.getProviderDetails().getAuthorizationUri())
              .isEqualTo("https://github.com/login/oauth/authorize");
        });
  }
}
