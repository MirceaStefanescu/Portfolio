package com.example.realtimechat.config;

import com.example.realtimechat.controller.UserController;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.MapPropertySource;
import org.springframework.messaging.Message;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.AbstractMessageChannel;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.mock.web.MockServletContext;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.authorization.AuthorizationManager;
import org.springframework.security.core.authority.AuthorityUtils;
import org.springframework.security.messaging.web.csrf.XorCsrfChannelInterceptor;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.registration.InMemoryClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.HttpSessionCsrfTokenRepository;
import org.springframework.security.web.csrf.InvalidCsrfTokenException;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.webAppContextSetup;

class ChatSecurityTest {
  private AnnotationConfigWebApplicationContext context;
  private MockMvc mvc;

  private void start(boolean demo) {
    context = new AnnotationConfigWebApplicationContext();
    context.setServletContext(new MockServletContext());
    context.getEnvironment().getPropertySources().addFirst(new MapPropertySource("test", Map.of(
        "app.demo-auth", demo, "app.frontend-base-url", "http://localhost:4201",
        "app.cors-allowed-origins", "http://localhost:4201")));
    context.register(SecurityConfig.class, WebSocketConfig.class, WebSocketSecurityConfig.class,
        UserController.class, TestConfig.class);
    context.refresh();
    mvc = webAppContextSetup(context).apply(springSecurity()).build();
  }

  @AfterEach
  void close() {
    if (context != null) context.close();
  }

  @ParameterizedTest
  @ValueSource(booleans = {true, false})
  void sessionMutationsRequireTheSessionsCsrfToken(boolean demo) throws Exception {
    start(demo);
    MvcResult result = mvc.perform(get("/api/csrf")).andExpect(status().isOk())
        .andExpect(jsonPath("$.headerName").value("X-CSRF-TOKEN"))
        .andExpect(jsonPath("$.token").isNotEmpty()).andReturn();
    MockHttpSession session = (MockHttpSession) result.getRequest().getSession(false);
    CsrfToken token = (CsrfToken) result.getRequest().getAttribute(CsrfToken.class.getName());
    assertThat(session).isNotNull();
    mvc.perform(post("/api/rooms").session(session).with(user("alice")))
        .andExpect(status().isForbidden());
    mvc.perform(post("/api/rooms").session(session).with(user("alice"))
        .header(token.getHeaderName(), "invalid")).andExpect(status().isForbidden());
    mvc.perform(post("/api/rooms").session(session).with(user("alice"))
        .header(token.getHeaderName(), token.getToken())).andExpect(status().isOk());
    mvc.perform(post("/api/rooms").session(new MockHttpSession()).with(user("alice"))
        .header(token.getHeaderName(), token.getToken())).andExpect(status().isForbidden());
  }

  @ParameterizedTest
  @ValueSource(booleans = {true, false})
  void onlyConfiguredOriginsCanReadTokensOrUseSockJs(boolean demo) throws Exception {
    start(demo);
    mvc.perform(options("/api/rooms").header("Origin", "http://localhost:4201")
        .header("Access-Control-Request-Method", "POST")
        .header("Access-Control-Request-Headers", "X-CSRF-TOKEN,Content-Type"))
        .andExpect(status().isOk())
        .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:4201"));
    mvc.perform(get("/api/csrf").header("Origin", "https://untrusted.example"))
        .andExpect(status().isForbidden());
    mvc.perform(get("/ws/info").with(user("alice")).header("Origin", "https://untrusted.example"))
        .andExpect(status().isForbidden());
    mvc.perform(get("/ws/info").with(user("alice")).header("Origin", "http://localhost:4201"))
        .andExpect(status().isOk());
    mvc.perform(get("/ws/info")).andExpect(demo ? status().isOk() : status().is3xxRedirection());
  }

  @ParameterizedTest
  @ValueSource(booleans = {true, false})
  void registeredStompInterceptorRequiresTheMaskedSessionToken(boolean demo) throws Exception {
    start(demo);
    MvcResult result = mvc.perform(get("/api/csrf")).andExpect(status().isOk()).andReturn();
    CsrfToken masked = (CsrfToken) result.getRequest().getAttribute(CsrfToken.class.getName());
    CsrfToken stored = new HttpSessionCsrfTokenRepository().loadToken(result.getRequest());
    AbstractMessageChannel channel = context.getBean("clientInboundChannel", AbstractMessageChannel.class);
    XorCsrfChannelInterceptor csrf = channel.getInterceptors().stream()
        .filter(XorCsrfChannelInterceptor.class::isInstance)
        .map(XorCsrfChannelInterceptor.class::cast).findFirst().orElseThrow();
    assertThatThrownBy(() -> csrf.preSend(connect(stored, null), channel))
        .isInstanceOf(InvalidCsrfTokenException.class);
    assertThatThrownBy(() -> csrf.preSend(connect(stored, "invalid"), channel))
        .isInstanceOf(InvalidCsrfTokenException.class);
    Message<?> valid = connect(stored, masked.getToken());
    assertThat(csrf.preSend(valid, channel)).isSameAs(valid);
    MvcResult other = mvc.perform(get("/api/csrf")).andReturn();
    CsrfToken otherStored = new HttpSessionCsrfTokenRepository().loadToken(other.getRequest());
    assertThatThrownBy(() -> csrf.preSend(connect(otherStored, masked.getToken()), channel))
        .isInstanceOf(InvalidCsrfTokenException.class);
  }

  @ParameterizedTest
  @ValueSource(booleans = {true, false})
  @SuppressWarnings("unchecked")
  void messageRulesDenyBrokerInjectionAndRequireProductionAuthentication(boolean demo) {
    start(demo);
    AuthorizationManager<Message<?>> rules =
        (AuthorizationManager<Message<?>>) context.getBean("messageAuthorizationManager");
    var authenticated = new UsernamePasswordAuthenticationToken("alice", "unused",
        AuthorityUtils.createAuthorityList("ROLE_USER"));
    var anonymous = new AnonymousAuthenticationToken("test", "anonymous",
        AuthorityUtils.createAuthorityList("ROLE_ANONYMOUS"));
    for (Message<?> allowed : List.of(message(StompCommand.SUBSCRIBE, "/topic/rooms/room"),
        message(StompCommand.SEND, "/app/rooms/room/send"))) {
      assertThat(rules.authorize(() -> authenticated, allowed).isGranted()).isTrue();
      assertThat(rules.authorize(() -> anonymous, allowed).isGranted()).isEqualTo(demo);
    }
    for (Message<?> denied : List.of(message(StompCommand.SEND, "/topic/rooms/room"),
        message(StompCommand.SUBSCRIBE, "/topic/admin"),
        message(StompCommand.SUBSCRIBE, "/app/rooms/room/send"),
        message(StompCommand.SEND, "/app/unknown"))) {
      assertThat(rules.authorize(() -> authenticated, denied).isGranted()).isFalse();
    }
  }

  private static Message<byte[]> connect(CsrfToken stored, String token) {
    StompHeaderAccessor headers = StompHeaderAccessor.create(StompCommand.CONNECT);
    headers.setSessionAttributes(new HashMap<>(Map.of(CsrfToken.class.getName(), stored)));
    if (token != null) headers.setNativeHeader(stored.getHeaderName(), token);
    return MessageBuilder.createMessage(new byte[0], headers.getMessageHeaders());
  }

  private static Message<byte[]> message(StompCommand command, String destination) {
    StompHeaderAccessor headers = StompHeaderAccessor.create(command);
    headers.setDestination(destination);
    return MessageBuilder.createMessage(new byte[0], headers.getMessageHeaders());
  }

  @Configuration
  @EnableWebMvc
  static class TestConfig {
    @Bean Rooms rooms() { return new Rooms(); }
    @Bean ClientRegistrationRepository clients() {
      return new InMemoryClientRegistrationRepository(ClientRegistration.withRegistrationId("github")
          .clientId("test").clientSecret("test").authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
          .redirectUri("{baseUrl}/login/oauth2/code/{registrationId}")
          .authorizationUri("https://example.invalid/authorize").tokenUri("https://example.invalid/token")
          .userInfoUri("https://example.invalid/user").userNameAttributeName("id").clientName("test").build());
    }
  }

  @RestController
  static class Rooms {
    @PostMapping("/api/rooms") String create() { return "created"; }
  }
}
