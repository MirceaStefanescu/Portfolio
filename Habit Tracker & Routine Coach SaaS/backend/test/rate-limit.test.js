const { test } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const { createApp } = require("../src/server");

test("API and frontend requests are bounded while health remains available", async t => {
  const server = createApp().listen(0, "127.0.0.1"); await once(server, "listening");
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = "http://127.0.0.1:" + server.address().port;
  for (let i = 0; i < 240; i++) {
    const response = await fetch(base + "/api/plans");
    assert.equal(response.status, 200); await response.arrayBuffer();
  }
  for (const path of ["/api/plans", "/some-client-route"]) {
    const response = await fetch(base + path);
    assert.equal(response.status, 429);
    assert.ok(Number(response.headers.get("retry-after")) > 0);
    assert.match((await response.json()).error, /Too many requests/);
  }
  const health = await fetch(base + "/api/health");
  assert.equal(health.status, 200); assert.equal((await health.json()).status, "ok");
});
