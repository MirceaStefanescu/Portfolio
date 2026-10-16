"""JWT gateway with Redis-backed limits and ownership checks; services stay internal."""

import hashlib
import json
import os
import re

import jwt
import redis
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

app = FastAPI(title="Commerce Gateway")
LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


def identity(authorization: str):
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret.encode()) < 32:
        raise HTTPException(503, "Gateway signing key is not configured")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    try:
        return jwt.decode(
            authorization[7:],
            secret,
            algorithms=["HS256"],
            issuer=os.getenv("JWT_ISSUER", "portfolio"),
            audience=os.getenv("JWT_AUDIENCE", "commerce"),
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.InvalidTokenError as error:
        raise HTTPException(401, "Invalid or expired token") from error


def rate_limit(subject: str):
    client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
        socket_timeout=2,
        socket_connect_timeout=2,
    )
    key = "gateway:rate:" + hashlib.sha256(subject.encode()).hexdigest()
    try:
        count, ttl = client.eval(LIMIT_SCRIPT, 1, key, 60)
    except redis.RedisError as error:
        raise HTTPException(503, "Rate-limit store unavailable") from error
    finally:
        client.close()
    if count > int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")):
        raise HTTPException(
            429, "Rate limit exceeded", headers={"Retry-After": str(max(1, ttl))}
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.api_route(
    "/{resource}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
)
@app.api_route("/{resource}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(resource: str, request: Request, path: str = ""):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1024 * 1024:
            raise HTTPException(413, "Request too large")
    return await run_in_threadpool(
        forward,
        resource,
        path,
        request.method,
        request.headers.get("Authorization", ""),
        bytes(body),
        list(request.query_params.multi_items()),
    )


def forward(resource, path, method, authorization, body, query):
    if resource not in ("products", "orders", "payments") or (
        path and not re.fullmatch(r"[A-Za-z0-9_/-]+", path)
    ):
        raise HTTPException(404, "Unknown resource")
    claims = identity(authorization)
    subject = claims["sub"]
    roles = claims.get("roles", [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise HTTPException(401, "Invalid roles")
    admin = "admin" in roles
    if (
        resource == "payments" or (resource == "products" and method != "GET")
    ) and not admin:
        raise HTTPException(403, "Administrator role required")
    rate_limit(subject)
    base = os.getenv(
        resource.upper() + "_URL", "http://" + resource.rstrip("s") + "-service:8000"
    )
    url = base + "/" + resource + ("/" + path if path else "")
    payload = None
    if body:
        try:
            payload = json.loads(body)
        except ValueError as error:
            raise HTTPException(400, "Invalid JSON") from error
    if resource == "orders" and method == "POST" and not path and not admin:
        if not isinstance(payload, dict):
            raise HTTPException(400, "Order object required")
        payload["customer_id"] = subject
    try:
        if resource == "orders" and path and not admin:
            owner = requests.get(base + "/orders/" + path.split("/")[0], timeout=5)
            if owner.status_code == 404:
                raise HTTPException(404, "Order not found")
            owner.raise_for_status()
            if owner.json()["customer_id"] != subject:
                raise HTTPException(403, "Order belongs to another customer")
        upstream = requests.request(
            method, url, params=query, json=payload, timeout=15, allow_redirects=False
        )
    except requests.RequestException as error:
        raise HTTPException(502, "Upstream service unavailable") from error
    if (
        resource == "orders"
        and method == "GET"
        and not path
        and not admin
        and upstream.status_code == 200
    ):
        return [item for item in upstream.json() if item["customer_id"] == subject]
    return Response(
        upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("Content-Type", "application/json"),
    )
