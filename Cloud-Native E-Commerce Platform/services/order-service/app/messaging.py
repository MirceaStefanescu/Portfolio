import json
import logging
import os
import sqlite3
import threading
from collections.abc import Callable
from typing import Any

import pika
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

LOGGER = logging.getLogger(__name__)


def kafka_enabled() -> bool:
    return os.getenv("KAFKA_ENABLED", "true").lower() == "true"


def rabbitmq_enabled() -> bool:
    return os.getenv("RABBITMQ_ENABLED", "true").lower() == "true"


def build_producer() -> KafkaProducer | None:
    if not kafka_enabled():
        LOGGER.info("Kafka disabled via KAFKA_ENABLED=false")
        return None

    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    return KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        retries=3,
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


def send_payment_request(message: dict[str, Any]) -> None:
    if not rabbitmq_enabled():
        return

    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    queue = os.getenv("PAYMENT_QUEUE", "payment.requests")

    connection = None
    try:
        params = pika.URLParameters(url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    except (
        pika.exceptions.AMQPError,
        OSError,
    ) as exc:  # pragma: no cover - broker integration
        LOGGER.warning("Failed to publish RabbitMQ message: %s", exc)
    finally:
        if connection is not None and connection.is_open:
            connection.close()


def start_payment_event_consumer(
    on_event: Callable[[dict[str, Any]], None],
    stop_event: threading.Event,
) -> threading.Thread | None:
    if not kafka_enabled():
        return None

    thread = threading.Thread(
        target=_consumer_loop,
        args=(on_event, stop_event),
        daemon=True,
    )
    thread.start()
    return thread


def _consumer_loop(
    on_event: Callable[[dict[str, Any]], None], stop_event: threading.Event
) -> None:
    topic = os.getenv("KAFKA_TOPIC_PAYMENTS", "payments")
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    group_id = os.getenv("KAFKA_GROUP_ID", "order-service")

    while not stop_event.is_set():
        consumer = None
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap,
                group_id=group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
            )
            while not stop_event.is_set():
                batches = consumer.poll(timeout_ms=1000)
                for messages in batches.values():
                    for message in messages:
                        try:
                            event = json.loads(message.value.decode("utf-8"))
                            on_event(event)
                        except (ValueError, TypeError) as exc:
                            LOGGER.warning("Invalid payment event: %s", exc)
                if batches:
                    consumer.commit()
        except (KafkaError, OSError, sqlite3.Error) as exc:
            LOGGER.warning("Kafka consumer error: %s", exc)
        finally:
            if consumer is not None:
                consumer.close(autocommit=False)
        stop_event.wait(5)
