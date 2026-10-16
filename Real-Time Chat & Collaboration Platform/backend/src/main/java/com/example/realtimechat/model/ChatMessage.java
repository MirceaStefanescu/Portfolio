package com.example.realtimechat.model;

import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.UuidGenerator;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

@Entity
@Table(name = "chat_messages")
public class ChatMessage {
  @Id
  @UuidGenerator
  private UUID id;

  @ManyToOne(fetch = FetchType.LAZY, optional = false)
  @JoinColumn(name = "room_id", nullable = false)
  private ChatRoom room;

  @Column(nullable = false, length = 120)
  private String sender;

  @Column(nullable = false, columnDefinition = "text")
  private String content;

  @Column(name = "created_at", nullable = false)
  private Instant createdAt;

  @Column(nullable = false)
  private boolean published;

  @Column(name = "client_request_id", length = 64)
  private String clientRequestId;

  protected ChatMessage() {
  }

  public ChatMessage(ChatRoom room, String sender, String content) {
    this.room = room;
    this.sender = sender;
    this.content = content;
  }

  @PrePersist
  void onCreate() {
    if (createdAt == null) {
      createdAt = Instant.now();
    }
  }

  public UUID getId() {
    return id;
  }

  public ChatRoom getRoom() {
    return room;
  }

  public String getSender() {
    return sender;
  }

  public String getContent() {
    return content;
  }

  public Instant getCreatedAt() {
    return createdAt;
  }

  public String getClientRequestId() { return clientRequestId; }
  public void setClientRequestId(String value) { this.clientRequestId = value; }
}
