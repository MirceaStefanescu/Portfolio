import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import messaging


@pytest.mark.parametrize(
    "body,handler_error,requeue,accepted",
    [
        (b'{"order_id": "one"}', None, None, True),
        (b"not-json", None, False, False),
        (b"[]", None, False, False),
        (b'{"order_id": "one"}', ValueError("invalid"), False, False),
        (b'{"order_id": "one"}', sqlite3.OperationalError("busy"), True, False),
    ],
)
def test_consumer_acknowledgement_and_cleanup(
    monkeypatch, body, handler_error, requeue, accepted
):
    stop = threading.Event()
    channel = Mock()
    connection = Mock(is_open=True)
    connection.channel.return_value = channel
    callback = None

    def subscribe(**kwargs):
        nonlocal callback
        callback = kwargs["on_message_callback"]

    def process(**kwargs):
        stop.set()
        callback(channel, SimpleNamespace(delivery_tag=7), None, body)

    channel.basic_consume.side_effect = subscribe
    connection.process_data_events.side_effect = process
    monkeypatch.setattr(messaging.pika, "BlockingConnection", lambda _: connection)
    handler = Mock(side_effect=handler_error)
    messaging._rabbit_loop(handler, stop)
    connection.close.assert_called_once()
    if accepted:
        channel.basic_ack.assert_called_once_with(delivery_tag=7)
        channel.basic_nack.assert_not_called()
    else:
        channel.basic_ack.assert_not_called()
        channel.basic_nack.assert_called_once_with(delivery_tag=7, requeue=requeue)
