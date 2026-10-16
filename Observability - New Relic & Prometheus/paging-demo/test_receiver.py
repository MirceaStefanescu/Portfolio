import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from receiver import Inbox, handler, ThreadingHTTPServer


class InboxTests(unittest.TestCase):
    def test_real_http_protocols_retry_dedup_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inbox.sqlite"
            inbox = Inbox(path)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler(inbox))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def post(route, data):
                request = urllib.request.Request("http://127.0.0.1:" + str(server.server_port) + route,
                    data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
                try:
                    response = urllib.request.urlopen(request)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    return response.status, response.read()
            try:
                payload = {"routing_key": "local-demo-route", "event_action": "trigger", "dedup_key": "incident-1",
                           "payload": {"summary": "Service down", "source": "demo-a", "severity": "critical"}}
                self.assertEqual(post("/fail-next", {"kind": "pagerduty", "count": 1})[0], 200)
                self.assertEqual(post("/pagerduty", payload)[0], 503)
                self.assertEqual(post("/pagerduty", payload)[0], 202)
                self.assertEqual(post("/pagerduty", payload)[0], 202)
                self.assertEqual(post("/slack", {"text": "", "channel": "#local-demo",
                    "attachments": [{"title": "ServiceDown", "text": "STATUS=firing ALERT=ServiceDown"}]})[0], 200)
                self.assertEqual(len(inbox.snapshot()["events"]), 2)
                self.assertEqual(inbox.snapshot()["failedAttempts"], {"pagerduty": 1})
                payload["event_action"] = "resolve"
                self.assertEqual(post("/pagerduty", payload)[0], 202)
                restored = Inbox(path)
                self.assertEqual(len(restored.snapshot()["events"]), 3)
                self.assertEqual(post("/pagerduty", {"routing_key": "real-key"})[0], 400)
                self.assertEqual(post("/slack", {"text": 5})[0], 400)
                self.assertEqual(post("/slack", {"text": "x" * 262144})[0], 413)
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
