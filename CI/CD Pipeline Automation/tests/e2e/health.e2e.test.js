const { describe, it, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { startServer } = require("../../src/server");

describe("e2e", () => {
  let server;
  let baseUrl;

  before(() => {
    const started = startServer(0);
    server = started.server;
    const { port } = server.address();
    baseUrl = `http://127.0.0.1:${port}`;
  });

  after(() => new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  }));

  it("serves the homepage", async () => {
    const response = await fetch(`${baseUrl}/`);

    assert.equal(response.status, 200);
    const body = await response.text();
    assert.ok(body.includes("CI/CD Pipeline Automation"));
  });

  it("exposes metrics", async () => {
    const response = await fetch(`${baseUrl}/metrics`);

    assert.equal(response.status, 200);
    const body = await response.text();
    assert.ok(body.includes("http_requests_total"));
  });
});
