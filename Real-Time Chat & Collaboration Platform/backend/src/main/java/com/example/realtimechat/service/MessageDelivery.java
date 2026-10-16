package com.example.realtimechat.service;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@EnableScheduling
@ConditionalOnProperty(name = "app.publisher-enabled", havingValue = "true", matchIfMissing = true)
public class MessageDelivery {
  private final ChatService chat;
  public MessageDelivery(ChatService chat) { this.chat = chat; }
  @Scheduled(fixedDelay = 2000)
  public void deliver() { chat.retryPendingMessages(); }
}
