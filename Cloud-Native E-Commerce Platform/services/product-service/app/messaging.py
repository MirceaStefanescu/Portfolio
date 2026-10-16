import json
import logging
import os
from typing import Any

from kafka import KafkaProducer
from kafka.errors import KafkaError

LOGGER = logging.getLogger(__name__)


def kafka_enabled() -> bool:
    return os.getenv("KAFKA_ENABLED", "true").lower() == "true"


def build_producer() -> KafkaProducer | None:
    if not kafka_enabled():
        LOGGER.info("Kafka disabled via KAFKA_ENABLED=false")
        return None

    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    return KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        retries=3,
        api_version=(3, 0, 0),
        max_block_ms=5000,
    )


def publish_event(
    producer: KafkaProducer | None,
    topic: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    if producer is None:
        return

    event = {"event_type": event_type, "payload": payload}
    try:
        producer.send(topic, event).get(timeout=5)
    except KafkaError as exc:  # pragma: no cover - broker integration
        LOGGER.warning("Failed to publish Kafka event: %s", exc)
