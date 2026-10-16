package com.example.realtimechat.controller;

import java.security.Principal;
import java.util.UUID;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.messaging.simp.annotation.SendToUser;
import org.springframework.stereotype.Controller;
import com.example.realtimechat.model.ChatMessageRequest;
import com.example.realtimechat.service.ChatService;
import com.example.realtimechat.service.RoomPresence;

@Controller
public class ChatWebSocketController {
  private final ChatService chatService;
  private final RoomPresence presence;
  public record Receipt(String requestId, boolean accepted, UUID messageId, String error) {}
  public record Activity(String sender, boolean typing, boolean leave) {}

  public ChatWebSocketController(ChatService chatService, RoomPresence presence) {
    this.chatService = chatService;
    this.presence = presence;
  }

  @MessageMapping("/rooms/{roomId}/send")
  @SendToUser(value = "/queue/receipts", broadcast = false)
  public Receipt sendMessage(
      @DestinationVariable UUID roomId,
      @Payload ChatMessageRequest request,
      Principal principal,
      @Header("simpSessionId") String session
  ) {
    String sender = principal != null ? principal.getName() : request.sender();
    try {
      presence.rateLimit(principal != null ? principal.getName() : session, "messages", 60);
      UUID id = chatService.handleInboundMessage(roomId, sender, request.content(), request.requestId());
      return new Receipt(request.requestId(), true, id, "");
    } catch (IllegalArgumentException exception) {
      return new Receipt(request.requestId(), false, null, exception.getMessage());
    } catch (org.springframework.dao.DataAccessException exception) {
      return new Receipt(request.requestId(), false, null, "Message storage or rate-limit service unavailable");
    }
  }

  @MessageMapping("/rooms/{roomId}/presence")
  public void activity(@DestinationVariable UUID roomId, @Payload Activity request, Principal principal,
                       @Header("simpSessionId") String session) {
    presence.update(roomId, session, principal != null ? principal.getName() : request.sender(), request.typing(), request.leave());
  }
}
