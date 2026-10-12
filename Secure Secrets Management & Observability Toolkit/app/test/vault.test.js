const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const { once } = require("node:events");
const { fetchVaultSecret } = require("../src/vault");

function credentials(t, present = true) {
  for (const [name, value] of Object.entries({
    VAULT_APPROLE_ROLE_ID: "test-role",
    VAULT_APPROLE_SECRET_ID: "test-secret"
  })) {
    const previous = process.env[name];
    if (present) process.env[name] = value;
    else delete process.env[name];
    t.after(() => {
      if (previous === undefined) delete process.env[name];
      else process.env[name] = previous;
    });
  }
}

async function endpoint(t, handler) {
  const server = http.createServer(handler);
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  }));
  return "http://127.0.0.1:" + server.address().port;
}

test("AppRole login authenticates the subsequent KV v2 read", async (t) => {
  credentials(t);
  const requests = [];
  const addr = await endpoint(t, async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;
    requests.push({ method: req.method, path: req.url, body, token: req.headers["x-vault-token"] });
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(req.url === "/v1/auth/approle/login"
      ? { auth: { client_token: "test-session" } }
      : { data: { data: { application: "demo" } } }));
  });
  assert.deepEqual(await fetchVaultSecret({ addr, secretPath: "secret/data/app" }), { application: "demo" });
  assert.equal(requests.length, 2);
  assert.equal(requests[0].method, "POST");
  assert.equal(requests[0].path, "/v1/auth/approle/login");
  assert.deepEqual(JSON.parse(requests[0].body), { role_id: "test-role", secret_id: "test-secret" });
  assert.equal(requests[1].method, "GET");
  assert.equal(requests[1].path, "/v1/secret/data/app");
  assert.equal(requests[1].token, "test-session");
});

test("failed AppRole authentication does not attempt a secret read", async (t) => {
  credentials(t);
  const requests = [];
  const addr = await endpoint(t, (req, res) => {
    requests.push(req.url);
    res.writeHead(403, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ errors: ["permission denied"] }));
  });
  await assert.rejects(fetchVaultSecret({ addr, secretPath: "secret/data/app" }));
  assert.deepEqual(requests, ["/v1/auth/approle/login"]);
});

test("missing credentials fail before contacting Vault", async (t) => {
  credentials(t, false);
  let contacted = false;
  const addr = await endpoint(t, (_req, res) => {
    contacted = true;
    res.end("{}");
  });
  await assert.rejects(fetchVaultSecret({ addr, secretPath: "secret/data/app" }), /Missing Vault AppRole credentials/);
  assert.equal(contacted, false);
});
