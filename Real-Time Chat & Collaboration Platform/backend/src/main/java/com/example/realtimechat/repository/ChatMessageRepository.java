package com.example.realtimechat.repository;

import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import com.example.realtimechat.model.ChatMessage;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, UUID> {
  @EntityGraph(attributePaths = "room")
  Page<ChatMessage> findByRoom_IdOrderByCreatedAtDesc(UUID roomId, Pageable pageable);

  @EntityGraph(attributePaths = "room")
  Page<ChatMessage> findByRoom_IdAndContentContainingIgnoreCaseOrderByCreatedAtDesc(UUID roomId, String query, Pageable pageable);

  @EntityGraph(attributePaths = "room")
  java.util.Optional<ChatMessage> findBySenderAndClientRequestId(String sender, String requestId);

  @EntityGraph(attributePaths = "room")
  java.util.List<ChatMessage> findTop50ByPublishedFalseOrderByCreatedAtAsc();

  @org.springframework.transaction.annotation.Transactional
  @org.springframework.data.jpa.repository.Modifying
  @org.springframework.data.jpa.repository.Query("update ChatMessage m set m.published = true where m.id = :id")
  int markPublished(@org.springframework.data.repository.query.Param("id") UUID id);
}
