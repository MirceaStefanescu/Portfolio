const { test } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const express = require("express");
const { installAccess } = require("../src/auth");

test("login and callback share a bounded per-client authentication budget", async t => {
  const app = express();
  installAccess(app, {mode: "oidc", issuer: "http://127.0.0.1:1", publicUrl: "http://127.0.0.1:2",
    clientId: "fixture", clientSecret: "fixture-client-secret", localHttp: true,
    secret: "fixture-session-secret-of-more-than-32-bytes"});
  const server = app.listen(0, "127.0.0.1"); await once(server, "listening");
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = "http://127.0.0.1:" + server.address().port;
  for (let i = 0; i < 60; i++) {
    const response = await fetch(base + "/auth/callback");
    assert.equal(response.status, 401); await response.arrayBuffer();
  }
  for (const path of ["/auth/callback", "/auth/login"]) {
    const response = await fetch(base + path, {redirect: "manual"});
    assert.equal(response.status, 429);
    assert.ok(Number(response.headers.get("retry-after")) > 0);
    assert.match((await response.json()).error, /Too many sign-in attempts/);
  }
});
