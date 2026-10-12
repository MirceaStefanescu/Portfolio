package com.example.realtimechat.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.Message;
import org.springframework.messaging.simp.SimpMessageType;
import org.springframework.security.authorization.AuthenticatedAuthorizationManager;
import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.authorization.AuthorizationManager;
import org.springframework.security.config.annotation.web.socket.EnableWebSocketSecurity;
import org.springframework.security.messaging.access.intercept.MessageMatcherDelegatingAuthorizationManager;
import org.springframework.security.messaging.access.intercept.MessageAuthorizationContext;

@Configuration
@EnableWebSocketSecurity
public class WebSocketSecurityConfig {
  @Bean
  public AuthorizationManager<Message<?>> messageAuthorizationManager(
      MessageMatcherDelegatingAuthorizationManager.Builder messages,
      @Value("${app.demo-auth:false}") boolean demoAuthEnabled) {
    AuthorizationManager<MessageAuthorizationContext<?>> access = demoAuthEnabled
        ? (authentication, message) -> new AuthorizationDecision(true)
        : AuthenticatedAuthorizationManager.authenticated();
    return messages
        .nullDestMatcher().access(access)
        .simpSubscribeDestMatchers("/topic/rooms/*").access(access)
        .simpTypeMatchers(SimpMessageType.SUBSCRIBE).denyAll()
        .simpDestMatchers("/app/rooms/*/send").access(access)
        .anyMessage().denyAll()
        .build();
  }
}
