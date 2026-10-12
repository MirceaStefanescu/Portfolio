package com.mircea.portofolio.ecommerce.config;

import com.mircea.portofolio.ecommerce.security.JwtAuthenticationFilter;
import com.mircea.portofolio.ecommerce.service.JwtService;
import jakarta.servlet.http.Cookie;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.mock.web.MockServletContext;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.core.authority.AuthorityUtils;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.context.SecurityContextImpl;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.webAppContextSetup;

class BearerAuthenticationTest {
  private AnnotationConfigWebApplicationContext context;
  private MockMvc mvc;
  private String token;

  @BeforeEach
  void start() {
    context = new AnnotationConfigWebApplicationContext();
    context.setServletContext(new MockServletContext());
    context.register(SecurityConfig.class, JwtAuthenticationFilter.class, TestConfig.class);
    context.refresh();
    mvc = webAppContextSetup(context).apply(springSecurity()).build();
    token = context.getBean(JwtService.class).generateToken("alice").token();
  }

  @AfterEach
  void close() {
    if (context != null) context.close();
    SecurityContextHolder.clearContext();
  }

  @Test
  void validBearerAuthenticatesWithoutCreatingACookieOrSession() throws Exception {
    var result = mvc.perform(post("/api/security-probe").header("Authorization", "Bearer " + token))
        .andExpect(status().isOk()).andExpect(content().string("alice"))
        .andExpect(header().doesNotExist("Set-Cookie")).andReturn();
    assertThat(result.getRequest().getSession(false)).isNull();
    mvc.perform(post("/api/security-probe")).andExpect(status().isForbidden());
  }

  @Test
  void cookiesParametersAndBasicCredentialsCannotAuthenticate() throws Exception {
    mvc.perform(post("/api/security-probe").cookie(new Cookie("access_token", token),
        new Cookie("Authorization", "Bearer " + token), new Cookie("JSESSIONID", "ignored")))
        .andExpect(status().isForbidden());
    mvc.perform(post("/api/security-probe").param("access_token", token))
        .andExpect(status().isForbidden());
    mvc.perform(post("/api/security-probe").header("Authorization", "Basic YWxpY2U6dGVzdA=="))
        .andExpect(status().isForbidden());
  }

  @Test
  void storedSessionAuthenticationIsIgnored() throws Exception {
    var authentication = new UsernamePasswordAuthenticationToken("alice", "unused",
        AuthorityUtils.createAuthorityList("ROLE_USER"));
    MockHttpSession session = new MockHttpSession();
    session.setAttribute(HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY,
        new SecurityContextImpl(authentication));
    mvc.perform(post("/api/security-probe").session(session)).andExpect(status().isForbidden());
  }

  @Test
  void invalidBearerCannotAuthenticate() throws Exception {
    mvc.perform(post("/api/security-probe").header("Authorization", "Bearer invalid"))
        .andExpect(status().is4xxClientError());
  }

  @Configuration
  @EnableWebMvc
  @EnableWebSecurity
  static class TestConfig {
    @Bean Probe probe() { return new Probe(); }
    @Bean JwtService jwt() { return new JwtService(UUID.randomUUID().toString(), "test", 5); }
  }

  @RestController
  static class Probe {
    @PostMapping("/api/security-probe")
    String identity(java.security.Principal principal) { return principal.getName(); }

    @PostMapping("/api/failure-probe")
    String failure() { throw new IllegalStateException("application failure"); }
  }
}
