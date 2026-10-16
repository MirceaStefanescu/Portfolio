package com.example.realtimechat.service;

import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import com.example.realtimechat.model.ChatEvent;
import com.example.realtimechat.model.ChatEventType;
import com.example.realtimechat.model.ChatMessage;
import com.example.realtimechat.model.ChatMessageResponse;
import com.example.realtimechat.model.ChatRoom;
import com.example.realtimechat.model.ChatRoomRequest;
import com.example.realtimechat.model.ChatRoomResponse;
import com.example.realtimechat.repository.ChatMessageRepository;
import com.example.realtimechat.repository.ChatRoomRepository;

@Service
public class ChatService {
  private final ChatRoomRepository chatRoomRepository;
  private final ChatMessageRepository chatMessageRepository;
  private final KafkaTemplate<String, ChatEvent> kafkaTemplate;
  private final String topic;
  private final java.util.Set<UUID> publishing = java.util.concurrent.ConcurrentHashMap.newKeySet();

  public ChatService(
      ChatRoomRepository chatRoomRepository,
      ChatMessageRepository chatMessageRepository,
      KafkaTemplate<String, ChatEvent> kafkaTemplate,
      @Value("${app.kafka-topic}") String topic
  ) {
    this.chatRoomRepository = chatRoomRepository;
    this.chatMessageRepository = chatMessageRepository;
    this.kafkaTemplate = kafkaTemplate;
    this.topic = topic;
  }

  public List<ChatRoomResponse> listRooms() {
    return chatRoomRepository.findAll().stream()
        .sorted(Comparator.comparing(ChatRoom::getCreatedAt))
        .map(room -> new ChatRoomResponse(room.getId(), room.getName(), room.getCreatedAt()))
        .collect(Collectors.toList());
  }

  public ChatRoomResponse createRoom(ChatRoomRequest request) {
    String name = request.name() == null ? "" : request.name().trim();
    if (!StringUtils.hasText(name)) {
      throw new IllegalArgumentException("Room name is required");
    }

    ChatRoom room = chatRoomRepository.findByName(name)
        .orElseGet(() -> chatRoomRepository.save(new ChatRoom(name)));
    return new ChatRoomResponse(room.getId(), room.getName(), room.getCreatedAt());
  }

  public UUID handleInboundMessage(UUID roomId, String sender, String content) {
    return handleInboundMessage(roomId, sender, content, null);
  }

  public UUID handleInboundMessage(UUID roomId, String sender, String content, String requestId) {
    if (!StringUtils.hasText(content)) {
      throw new IllegalArgumentException("Message content is required");
    }

    String resolvedSender = StringUtils.hasText(sender) ? sender.trim() : "anonymous";
    if (resolvedSender.length() > 120 || content.length() > 4000) {
      throw new IllegalArgumentException("Sender or message exceeds the allowed length");
    }
    if (requestId != null && !requestId.matches("[A-Za-z0-9-]{1,64}")) {
      throw new IllegalArgumentException("Invalid message request ID");
    }
    if (requestId != null) {
      var existing = chatMessageRepository.findBySenderAndClientRequestId(resolvedSender, requestId);
      if (existing.isPresent()) return duplicate(existing.get(), roomId, content);
    }
    ChatRoom room = chatRoomRepository.findById(roomId)
        .orElseThrow(() -> new IllegalArgumentException("Room not found"));

    ChatMessage pending = new ChatMessage(room, resolvedSender, content.trim());
    pending.setClientRequestId(requestId);
    ChatMessage message;
    try { message = chatMessageRepository.save(pending); }
    catch (org.springframework.dao.DataIntegrityViolationException exception) {
      if (requestId == null) throw exception;
      var existing = chatMessageRepository.findBySenderAndClientRequestId(resolvedSender, requestId);
      if (existing.isEmpty()) throw exception;
      return duplicate(existing.get(), roomId, content);
    }
    publish(message);
    return message.getId();
  }

  private UUID duplicate(ChatMessage message, UUID roomId, String content) {
    if (!message.getRoom().getId().equals(roomId) || !message.getContent().equals(content.trim())) {
      throw new IllegalArgumentException("Request ID was already used for a different message");
    }
    return message.getId();
  }

  private void publish(ChatMessage message) {
    if (!publishing.add(message.getId())) return;
    ChatRoom room = message.getRoom();

    ChatEvent event = new ChatEvent(
        message.getId(),
        room.getId(),
        room.getName(),
        message.getSender(),
        message.getContent(),
        message.getCreatedAt(),
        ChatEventType.MESSAGE
    );

    try {
      kafkaTemplate.send(topic, room.getId().toString(), event).whenComplete((result, error) -> {
        try {
          if (error == null) chatMessageRepository.markPublished(message.getId());
        } finally { publishing.remove(message.getId()); }
      });
    } catch (org.springframework.kafka.KafkaException | org.apache.kafka.common.KafkaException exception) {
      publishing.remove(message.getId());
      org.slf4j.LoggerFactory.getLogger(ChatService.class).warn("Message saved for broker recovery: {}", message.getId());
    }
  }

  public void retryPendingMessages() {
    for (ChatMessage message : chatMessageRepository.findTop50ByPublishedFalseOrderByCreatedAtAsc()) publish(message);
  }

  public List<ChatMessageResponse> getRecentMessages(UUID roomId, int limit) {
    return getRecentMessages(roomId, limit, "");
  }

  public List<ChatMessageResponse> getRecentMessages(UUID roomId, int limit, String query) {
    if (!chatRoomRepository.existsById(roomId)) {
      throw new IllegalArgumentException("Room not found");
    }

    int size = Math.min(Math.max(limit, 1), 100);
    if (query.length() > 200) throw new IllegalArgumentException("Search query exceeds 200 characters");
    var page = query.isBlank()
        ? chatMessageRepository.findByRoom_IdOrderByCreatedAtDesc(roomId, PageRequest.of(0, size))
        : chatMessageRepository.findByRoom_IdAndContentContainingIgnoreCaseOrderByCreatedAtDesc(roomId, query.trim(), PageRequest.of(0, size));
    List<ChatMessage> messages = page.getContent();

    return messages.stream()
        .sorted(Comparator.comparing(ChatMessage::getCreatedAt))
        .map(this::toResponse)
        .collect(Collectors.toList());
  }

  private ChatMessageResponse toResponse(ChatMessage message) {
    ChatRoom room = message.getRoom();
    return new ChatMessageResponse(
        message.getId(),
        room.getId(),
        room.getName(),
        message.getSender(),
        message.getContent(),
        message.getCreatedAt()
    );
  }
}
