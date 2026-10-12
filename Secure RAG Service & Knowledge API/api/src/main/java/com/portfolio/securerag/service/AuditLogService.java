package com.portfolio.securerag.service;

import com.portfolio.securerag.config.AuditProperties;
import com.portfolio.securerag.model.AuditEvent;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class AuditLogService {

    private static final Logger logger = LoggerFactory.getLogger(AuditLogService.class);

    private final Deque<AuditEvent> events = new ArrayDeque<>();
    private final int maxEvents;

    public AuditLogService(AuditProperties auditProperties) {
        this.maxEvents = auditProperties.getMaxEvents();
        if (maxEvents < 1) throw new IllegalArgumentException("Audit max-events must be positive");
    }

    public void record(String actor, String action, String resource, String status, String details) {
        AuditEvent event = new AuditEvent(Instant.now(), actor, action, resource, status, details);
        synchronized (events) {
            if (events.size() >= maxEvents) {
                events.removeFirst();
            }
            events.addLast(event);
        }
        logger.info("AUDIT actor={} action={} resource={} status={} details={}", actor, action, resource, status, details);
    }

    public List<AuditEvent> list(int limit) {
        if (limit < 0) throw new IllegalArgumentException("Limit cannot be negative");
        List<AuditEvent> snapshot;
        synchronized (events) {
            snapshot = new ArrayList<>(events);
        }
        int fromIndex = Math.max(snapshot.size() - limit, 0);
        return snapshot.subList(fromIndex, snapshot.size());
    }
}
