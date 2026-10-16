package com.portfolio.pipeline.flink;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class EventParserTest {
  @Test
  void parseValidEvent() {
    String payload = "{\"eventType\":\"sensor.temperature\",\"value\":42.5,\"timestamp\":1714567890000}";
    Event event = EventParser.parse(payload);

    assertNotNull(event);
    assertEquals("sensor.temperature", event.eventType);
    assertEquals(42.5, event.value, 0.0001);
    assertEquals(1714567890000L, event.timestamp);
  }

  @Test
  void rejectsMissingTimestampInsteadOfSilentlyReplacingEventTime() {
    String payload = "{\"eventType\":\"sensor.temperature\",\"value\":12.0}";
    Event event = EventParser.parse(payload);

    assertNull(event);
  }

  @Test void rejectsWrongTypesBoundsAndUnexpectedFields() {
    for (String payload : new String[] {
        "{\"eventType\":\"sensor\",\"value\":\"2\",\"timestamp\":123}",
        "{\"eventType\":\"sensor\",\"timestamp\":123}",
        "{\"eventType\":\"sensor\",\"value\":1e999,\"timestamp\":123}",
        "{\"eventType\":\"sensor\",\"value\":2,\"timestamp\":0}",
        "{\"eventType\":\"sensor\",\"value\":2,\"timestamp\":123,\"unknown\":true}"
    }) assertNull(EventParser.parse(payload), payload);
  }

  @Test
  void parseMissingEventTypeReturnsNull() {
    String payload = "{\"value\":10.0,\"timestamp\":1714567890000}";

    assertNull(EventParser.parse(payload));
  }

  @Test
  void parseInvalidJsonReturnsNull() {
    assertNull(EventParser.parse("{not-json"));
  }
}
