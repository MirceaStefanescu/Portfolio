package com.example.realtimechat.controller;

import java.util.List;
import java.util.UUID;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.example.realtimechat.model.ChatMessageResponse;
import com.example.realtimechat.model.ChatRoomRequest;
import com.example.realtimechat.model.ChatRoomResponse;
import com.example.realtimechat.service.ChatService;

@RestController
@RequestMapping("/api/rooms")
public class ChatRoomController {
  private final ChatService chatService;

  public ChatRoomController(ChatService chatService) {
    this.chatService = chatService;
  }

  @GetMapping
  public List<ChatRoomResponse> listRooms() {
    return chatService.listRooms();
  }

  @PostMapping
  public ResponseEntity<ChatRoomResponse> createRoom(@Valid @RequestBody ChatRoomRequest request) {
    return ResponseEntity.ok(chatService.createRoom(request));
  }

  @GetMapping("/{roomId}/messages")
  public List<ChatMessageResponse> getRecentMessages(
      @PathVariable UUID roomId,
      @RequestParam(defaultValue = "50") int limit,
      @RequestParam(defaultValue = "") String query
  ) {
    return chatService.getRecentMessages(roomId, limit, query);
  }
}
