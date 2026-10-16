package com.example.realtimechat.model;

import jakarta.validation.constraints.NotBlank;

public record ChatMessageRequest(String sender, @NotBlank String content, String requestId) {
  public ChatMessageRequest(String sender, String content) { this(sender, content, null); }
}
