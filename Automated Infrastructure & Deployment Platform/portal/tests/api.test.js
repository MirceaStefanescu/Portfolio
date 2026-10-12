const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const { app } = require("../src/server");
let server, base;
before(async () => {
  server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  base = "http://127.0.0.1:" + server.address().port;
});
after(() => new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())));
test("metrics use valid Prometheus lines and labels", async () => {
  const response = await fetch(base + "/api/metrics");
  const body = await response.text();
  assert.match(response.headers.get("content-type"), /text\/plain/);
  assert.match(body, /^portal_requests_total\{endpoint="pipeline"\} \d+$/m);
  assert.equal(body.split("\n").filter(Boolean).length, 6);
  assert.ok(body.endsWith("\n"));
  assert.ok(!body.includes("\\"));
});
test("invalid JSON is a client error", async () => {
  const response = await fetch(base + "/api/pipeline", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: "{" });
  assert.equal(response.status, 400);
});
test("template API rejects fractional counts and invalid DNS names", async () => {
  for (const extra of [{ appCount: 1.5 }, { appName: "-invalid" }, { environment: "x".repeat(64) }]) {
    const response = await fetch(base + "/api/terraform", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ appName: "shop", environment: "dev", ...extra }) });
    assert.equal(response.status, 400);
  }
});
