import json
import logging
import os
import sqlite3
import threading
from collections.abc import Callable
from typing import Any

import pika
import psycopg
from kafka import KafkaProducer
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
    except KafkaError as exc:
        LOGGER.warning("Failed to publish Kafka event: %s", exc)
        raise


def start_payment_request_consumer(
    on_message: Callable[[dict[str, Any]], None],
    stop_event: threading.Event,
) -> threading.Thread | None:
    if not rabbitmq_enabled():
        return None

    thread = threading.Thread(
        target=_rabbit_loop,
        args=(on_message, stop_event),
        daemon=True,
    )
    thread.start()
    return thread


def _rabbit_loop(
    on_message: Callable[[dict[str, Any]], None], stop_event: threading.Event
) -> None:
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    queue = os.getenv("PAYMENT_QUEUE", "payment.requests")

    while not stop_event.is_set():
        connection = None
        try:
            params = pika.URLParameters(url)
            params.socket_timeout = 5
            params.stack_timeout = 7
            params.blocked_connection_timeout = 5
            params.connection_attempts = 1
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)
            channel.basic_qos(prefetch_count=1)

            def callback(ch, method, properties, body):
                try:
                    payload = json.loads(body.decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise TypeError("Payment request must be an object")
                    on_message(payload)
                except (ValueError, TypeError) as exc:
                    LOGGER.warning("Invalid payment request: %s", exc)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except (sqlite3.Error, psycopg.Error, KafkaError):
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    raise
                else:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=queue, on_message_callback=callback)
            while not stop_event.is_set():
                connection.process_data_events(time_limit=1)
        except (
            pika.exceptions.AMQPError,
            OSError,
            sqlite3.Error,
            psycopg.Error,
            KafkaError,
        ) as exc:
            LOGGER.warning("RabbitMQ consumer error: %s", exc)
        finally:
            if connection is not None and connection.is_open:
                connection.close()
        stop_event.wait(5)
