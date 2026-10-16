"""Local Slack/PagerDuty protocol receiver. Stores synthetic alerts, sends nothing."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Inbox:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.Lock()
        self.failures = {}
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, kind TEXT, event_key TEXT, action TEXT, summary TEXT, received REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS failed_attempts (kind TEXT PRIMARY KEY, count INTEGER NOT NULL)")
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()
    def receive(self, kind, payload):
        if kind == "slack":
            summary = payload.get("text")
            if not summary:
                attachments = payload.get("attachments", [])
                if not isinstance(attachments, list) or any(not isinstance(item, dict) for item in attachments):
                    raise ValueError("Invalid Slack attachments")
                texts = [item.get("text", "") for item in attachments]
                if any(not isinstance(text, str) for text in texts):
                    raise ValueError("Invalid Slack attachment text")
                summary = "\n".join(texts)
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("Slack text is required")
            action = "resolved" if "STATUS=resolved" in summary else "firing"
            key = hashlib.sha256(summary.encode()).hexdigest()
        elif kind == "pagerduty":
            if payload.get("routing_key") != "local-demo-route":
                raise ValueError("Only the synthetic demo routing key is accepted")
            action = payload.get("event_action")
            key = payload.get("dedup_key")
            if action not in {"trigger", "resolve", "acknowledge"} or not isinstance(key, str) or not key:
                raise ValueError("PagerDuty event_action and dedup_key are required")
            details = payload.get("payload", {})
            summary = details.get("summary", action)
            if action == "trigger" and (not details.get("source") or details.get("severity") not in {"critical", "error", "warning", "info"}):
                raise ValueError("PagerDuty trigger payload is incomplete")
            if not isinstance(summary, str):
                raise ValueError("Invalid summary")
        else:
            raise ValueError("Unsupported receiver")
        if len(summary) > 20000 or len(key) > 1024:
            raise ValueError("Event fields are too long")
        digest = hashlib.sha256(json.dumps([kind, payload], sort_keys=True).encode()).hexdigest()
        with self.lock, self.connect() as db:
            if self.failures.get(kind, 0):
                self.failures[kind] -= 1
                db.execute("INSERT INTO failed_attempts(kind,count) VALUES (?,1) ON CONFLICT(kind) DO UPDATE SET count=count+1", (kind,))
                return None
            db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)", (digest, kind, key, action, summary, time.time()))
        return key
    def snapshot(self):
        with self.lock, self.connect() as db:
            rows = db.execute("SELECT kind,event_key,action,summary,received FROM events ORDER BY received DESC LIMIT 200").fetchall()
            return {"events": [dict(zip(("kind", "key", "action", "summary", "received"), row)) for row in rows],
                    "failedAttempts": dict(db.execute("SELECT kind,count FROM failed_attempts"))}


def handler(inbox):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def respond(self, code, content, mime="application/json"):
            data = json.dumps(content).encode() if mime == "application/json" else content.encode()
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if self.path == "/health":
                return self.respond(200, {"status": "ok", "mode": "local-demo"})
            if self.path == "/events":
                return self.respond(200, inbox.snapshot())
            if self.path == "/":
                return self.respond(200, PAGE, "text/html; charset=utf-8")
            self.respond(404, {"error": "Not found"})
        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 262144:
                    return self.respond(413, {"error": "Body must be 1..262144 bytes"})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                if self.path == "/fail-next":
                    kind, count = payload.get("kind"), payload.get("count")
                    if kind not in {"slack", "pagerduty"} or type(count) is not int or not 0 <= count <= 3:
                        raise ValueError("Use a known receiver and count 0..3")
                    with inbox.lock:
                        inbox.failures[kind] = count
                    return self.respond(200, {"configured": count, "kind": kind})
                routes = {"/slack": "slack", "/pagerduty": "pagerduty"}
                if self.path not in routes:
                    return self.respond(404, {"error": "Not found"})
                kind = routes[self.path]
                key = inbox.receive(kind, payload)
                if key is None:
                    return self.respond(503, {"error": "Controlled local delivery failure"})
                if kind == "slack":
                    return self.respond(200, "ok", "text/plain")
                return self.respond(202, {"status": "success", "message": "Event processed", "dedup_key": key})
            except (ValueError, UnicodeDecodeError):
                self.respond(400, {"error": "Invalid demonstration event"})
    return Handler


PAGE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Local paging inbox</title><style>body{font:16px system-ui;max-width:1000px;margin:3rem auto;padding:1rem;background:#f3f6fa;color:#18283a}article{background:white;padding:1rem;margin:1rem 0;border-radius:8px;white-space:pre-wrap}button{font:inherit;padding:.5rem}</style>
<h1>Local paging inbox</h1><p>Real Alertmanager Slack and PagerDuty payloads, received locally. No external messages or accounts.</p>
<button onclick="refresh()">Refresh</button><p id="status" role="status"></p><div id="events"></div><script>
async function refresh(){try{const r=await fetch('/events');if(!r.ok)throw Error('Inbox unavailable');const d=await r.json();document.getElementById('status').textContent='Controlled failed deliveries: '+JSON.stringify(d.failedAttempts);const box=document.getElementById('events');box.replaceChildren();for(const e of d.events){const a=document.createElement('article');a.textContent=e.kind+' · '+e.action+' · '+new Date(e.received*1000).toLocaleString()+'\\n'+e.summary;box.append(a);}}catch(e){document.getElementById('status').textContent=e.message;}}refresh();setInterval(refresh,3000);
</script></html>"""


if __name__ == "__main__":
    path = Path(os.environ.get("INBOX_DB", "/data/inbox.sqlite"))
    path.parent.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8088"))), handler(Inbox(path))).serve_forever()
