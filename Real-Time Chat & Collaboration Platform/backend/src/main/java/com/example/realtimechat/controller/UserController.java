package com.example.realtimechat.controller;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
public class UserController {
  private final boolean demoAuthEnabled;
  private final String demoUser;

  public UserController(
      @Value("${app.demo-auth:false}") boolean demoAuthEnabled,
      @Value("${app.demo-user:demo}") String demoUser
  ) {
    this.demoAuthEnabled = demoAuthEnabled;
    this.demoUser = demoUser;
  }

  @GetMapping("/csrf")
  public CsrfToken csrf(CsrfToken token) {
    return token;
  }

  @GetMapping("/me")
  public UserProfile me(Authentication authentication) {
    if (authentication instanceof OAuth2AuthenticationToken oauthToken) {
      Map<String, Object> attributes = oauthToken.getPrincipal().getAttributes();
      String name = attributeAsString(attributes, "name");
      String login = attributeAsString(attributes, "login");
      String email = attributeAsString(attributes, "email");

      return new UserProfile(
          name != null ? name : login,
          login,
          email
      );
    }

    if (demoAuthEnabled) {
      return new UserProfile(
          demoUser,
          demoUser,
          demoUser + "@example.local"
      );
    }

    throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Not authenticated");
  }

  private String attributeAsString(Map<String, Object> attributes, String key) {
    Object value = attributes.get(key);
    return value == null ? null : value.toString();
  }

  public record UserProfile(String displayName, String username, String email) {
  }
}
