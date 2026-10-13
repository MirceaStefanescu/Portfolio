import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import messaging


@pytest.mark.parametrize(
    "body,error,commit",
    [
        (
            b'{"event_type":"payment.authorized","payload":{"order_id":"one"}}',
            None,
            True,
        ),
        (b"not-json", None, True),
        (b"{}", sqlite3.OperationalError("busy"), False),
    ],
)
def test_kafka_commit_follows_processing_and_consumer_always_closes(
    monkeypatch, body, error, commit
):
    stop = threading.Event()
    consumer = Mock()

    def poll(**kwargs):
        stop.set()
        return {"partition": [SimpleNamespace(value=body)]}

    consumer.poll.side_effect = poll
    constructor = Mock(return_value=consumer)
    monkeypatch.setattr(messaging, "KafkaConsumer", constructor)
    messaging._consumer_loop(Mock(side_effect=error), stop)
    assert constructor.call_args.kwargs["enable_auto_commit"] is False
    consumer.close.assert_called_once_with(autocommit=False)
    assert consumer.commit.call_count == int(commit)


def test_failed_rabbit_publication_closes_connection(monkeypatch):
    monkeypatch.setenv("RABBITMQ_ENABLED", "true")
    connection = Mock(is_open=True)
    connection.channel.return_value.basic_publish.side_effect = (
        messaging.pika.exceptions.AMQPConnectionError()
    )
    monkeypatch.setattr(messaging.pika, "BlockingConnection", lambda _: connection)
    with pytest.raises(messaging.pika.exceptions.AMQPConnectionError):
        messaging.send_payment_request({"order_id": "one"})
    connection.close.assert_called_once()


def test_rabbit_publication_requires_broker_confirmation(monkeypatch):
    monkeypatch.setenv("RABBITMQ_ENABLED", "true")
    connection = Mock(is_open=True)
    channel = connection.channel.return_value
    monkeypatch.setattr(messaging.pika, "BlockingConnection", lambda _: connection)
    messaging.send_payment_request({"order_id": "one"})
    channel.confirm_delivery.assert_called_once()
    assert channel.basic_publish.call_args.kwargs["mandatory"] is True
    connection.close.assert_called_once()


def test_kafka_publication_failure_is_not_hidden():
    from kafka.errors import KafkaError

    producer = Mock()
    producer.send.return_value.get.side_effect = KafkaError("offline")
    with pytest.raises(KafkaError):
        messaging.publish_event(producer, "orders", "order.created", {"id": "one"})
