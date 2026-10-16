package com.example.realtimechat.service;

import com.example.realtimechat.repository.ChatRoomRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;
import java.util.*;
import org.springframework.context.event.EventListener;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.socket.messaging.SessionDisconnectEvent;

@Service
public class RoomPresence {
  public record Member(String sessionId, String name, long expiresAt, long typingUntil) {}
  private static final DefaultRedisScript<Long> LIMIT = new DefaultRedisScript<>(
      "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n", Long.class);
  private final StringRedisTemplate redis;
  private final SimpMessagingTemplate messages;
  private final ChatRoomRepository rooms;
  private final ObjectMapper mapper;
  public RoomPresence(StringRedisTemplate redis, SimpMessagingTemplate messages, ChatRoomRepository rooms, ObjectMapper mapper) {
    this.redis = redis; this.messages = messages; this.rooms = rooms; this.mapper = mapper;
  }

  public void rateLimit(String identity, String operation, int maximum) {
    Long count = redis.execute(LIMIT, List.of("chat:rate:" + operation + ":" + identity));
    if (count == null || count > maximum) throw new IllegalArgumentException("Rate limit exceeded; retry in a minute");
  }

  public void update(UUID room, String session, String name, boolean typing, boolean leave) {
    if (!rooms.existsById(room)) throw new IllegalArgumentException("Room not found");
    if (name == null || name.isBlank() || name.length() > 120) throw new IllegalArgumentException("Invalid display name");
    rateLimit(session, "presence", 120);
    String previous = redis.opsForValue().get("chat:session:" + session);
    if (previous != null && !previous.equals(room.toString())) remove(UUID.fromString(previous), session);
    if (leave) {
      remove(room, session);
      if (room.toString().equals(previous)) redis.delete("chat:session:" + session);
    } else {
      long now = System.currentTimeMillis();
      try {
        redis.opsForHash().put("chat:presence:" + room, session,
            mapper.writeValueAsString(new Member(session, name, now + 45000, typing ? now + 3000 : 0)));
      } catch (com.fasterxml.jackson.core.JsonProcessingException exception) {
        throw new IllegalStateException("Presence encoding failed", exception);
      }
      redis.expire("chat:presence:" + room, Duration.ofSeconds(90));
      redis.opsForValue().set("chat:session:" + session, room.toString(), Duration.ofSeconds(90));
      broadcast(room);
    }
  }

  private void remove(UUID room, String session) {
    redis.opsForHash().delete("chat:presence:" + room, session);
    broadcast(room);
  }

  private void broadcast(UUID room) {
    redis.convertAndSend("chat:presence:events", room.toString());
  }

  public void deliverSnapshot(UUID room) {
    long now = System.currentTimeMillis();
    var members = new ArrayList<Member>();
    for (var entry : redis.opsForHash().entries("chat:presence:" + room).entrySet()) {
      try {
        Member member = mapper.readValue(entry.getValue().toString(), Member.class);
        if (member.expiresAt() > now) members.add(member);
        else redis.opsForHash().delete("chat:presence:" + room, entry.getKey());
      } catch (com.fasterxml.jackson.core.JsonProcessingException exception) {
        throw new IllegalStateException("Invalid stored presence", exception);
      }
    }
    members.sort(Comparator.comparing(Member::name).thenComparing(Member::sessionId));
    messages.convertAndSend("/topic/rooms/" + room + "/presence", Map.of("members", members, "serverTime", now));
  }

  @org.springframework.context.annotation.Bean
  @org.springframework.boot.autoconfigure.condition.ConditionalOnProperty(name = "app.presence-enabled", havingValue = "true", matchIfMissing = true)
  org.springframework.data.redis.listener.RedisMessageListenerContainer presenceEvents(
      org.springframework.data.redis.connection.RedisConnectionFactory connection) {
    var container = new org.springframework.data.redis.listener.RedisMessageListenerContainer();
    container.setConnectionFactory(connection);
    container.addMessageListener((message, pattern) -> deliverSnapshot(UUID.fromString(
        new String(message.getBody(), java.nio.charset.StandardCharsets.UTF_8))),
        new org.springframework.data.redis.listener.ChannelTopic("chat:presence:events"));
    return container;
  }

  @EventListener
  public void disconnected(SessionDisconnectEvent event) {
    String room = redis.opsForValue().getAndDelete("chat:session:" + event.getSessionId());
    if (room != null) remove(UUID.fromString(room), event.getSessionId());
  }
}
