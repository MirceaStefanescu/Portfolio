import time
from unittest.mock import Mock

import jwt
import pytest
import redis
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "fixture-only-key-not-for-deployment-0123456789")
    limiter = Mock()
    limiter.eval.return_value = [1, 60]
    monkeypatch.setattr(main.redis.Redis, "from_url", Mock(return_value=limiter))
    return TestClient(main.app), limiter


def token(subject="alice", roles=None, **overrides):
    return jwt.encode(
        {
            "sub": subject,
            "roles": roles or ["customer"],
            "iss": "portfolio",
            "aud": "commerce",
            "exp": int(time.time()) + 300,
            **overrides,
        },
        "fixture-only-key-not-for-deployment-0123456789",
        algorithm="HS256",
    )


def test_missing_expired_and_wrong_audience_tokens_fail(client):
    api, _ = client
    for value in [
        "",
        "Bearer invalid",
        "Bearer " + token(exp=0),
        "Bearer " + token(aud="other"),
    ]:
        assert api.get("/products", headers={"Authorization": value}).status_code == 401


def test_role_and_customer_isolation(client, monkeypatch):
    api, _ = client
    headers = {"Authorization": "Bearer " + token()}
    assert api.post("/products", headers=headers, json={}).status_code == 403
    owner = Mock(status_code=200)
    owner.json.return_value = {"customer_id": "bob"}
    monkeypatch.setattr(main.requests, "get", Mock(return_value=owner))
    assert api.get("/orders/123", headers=headers).status_code == 403
    response = Mock(
        status_code=201, content=b"{}", headers={"Content-Type": "application/json"}
    )
    send = Mock(return_value=response)
    monkeypatch.setattr(main.requests, "request", send)
    assert (
        api.post(
            "/orders", json={"customer_id": "bob", "items": []}, headers=headers
        ).status_code
        == 201
    )
    assert send.call_args.kwargs["json"]["customer_id"] == "alice"
    response.status_code = 200
    response.json.return_value = [{"customer_id": "alice"}, {"customer_id": "bob"}]
    assert api.get("/orders", headers=headers).json() == [{"customer_id": "alice"}]


def test_rate_limit_and_store_failure_are_enforced(client):
    api, limiter = client
    headers = {"Authorization": "Bearer " + token()}
    limiter.eval.return_value = [61, 15]
    response = api.get("/products", headers=headers)
    assert response.status_code == 429 and response.headers["Retry-After"] == "15"
    limiter.eval.side_effect = redis.ConnectionError("offline")
    assert api.get("/products", headers=headers).status_code == 503


def test_unknown_routes_and_invalid_json_do_not_reach_upstream(client, monkeypatch):
    api, _ = client
    send = Mock()
    monkeypatch.setattr(main.requests, "request", send)
    headers = {"Authorization": "Bearer " + token(roles=["admin"])}
    assert api.post("/unknown", headers=headers, json={}).status_code == 404
    assert api.post("/orders", headers=headers, content="not json").status_code == 400
    send.assert_not_called()
