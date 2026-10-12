const { test } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const { createApp } = require("../src/server");

async function api(t, options) {
  const server = createApp(options).listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())));
  return (origin, method = "GET") => fetch("http://127.0.0.1:" + server.address().port + "/api/health", {
    method,
    headers: {
      ...(origin === undefined ? {} : { Origin: origin }),
      ...(method === "OPTIONS" ? { "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type" } : {})
    }
  });
}

test("default CORS allows the documented local frontend and no unrelated origin", async (t) => {
  const request = await api(t);
  const allowed = await request("http://localhost:5173");
  assert.equal(allowed.status, 200);
  assert.equal(allowed.headers.get("access-control-allow-origin"), "http://localhost:5173");
  assert.match(allowed.headers.get("vary"), /Origin/);
  for (const origin of ["https://untrusted.example", "http://localhost:5173.evil.example", "null", undefined]) {
    assert.equal((await request(origin)).headers.get("access-control-allow-origin"), null);
  }
});

test("configured origin is matched exactly for responses and preflight", async (t) => {
  const request = await api(t, { corsOrigin: "https://frontend.example" });
  for (const method of ["GET", "OPTIONS"]) {
    const allowed = await request("https://frontend.example", method);
    assert.equal(allowed.headers.get("access-control-allow-origin"), "https://frontend.example");
    assert.equal(allowed.headers.get("access-control-allow-credentials"), null);
    for (const origin of ["http://localhost:5173", "https://frontend.example.evil", "https://untrusted.example", "null"]) {
      assert.equal((await request(origin, method)).headers.get("access-control-allow-origin"), null);
    }
  }
});

test("unsafe or ambiguous CORS configuration fails before the server starts", () => {
  for (const corsOrigin of ["*", "null", "", " https://frontend.example", "https://*.example", "https://frontend.example/",
    "https://user:password@frontend.example", "https://frontend.example/path", "https://frontend.example?q=1",
    "https://frontend.example#fragment", "file:///tmp/demo", true, null, ["https://frontend.example"]]) {
    assert.throws(() => createApp({ corsOrigin }), /CORS_ORIGIN must be one exact HTTP/);
  }
});
