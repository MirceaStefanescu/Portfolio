const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const request = require("supertest");
const { createApp } = require("../../src/app");

describe("app integration", () => {
  it("returns health status", async () => {
    const app = createApp();
    const response = await request(app).get("/health");

    assert.equal(response.status, 200);
    assert.equal(response.body.status, "ok");
    assert.notEqual(response.body.build, undefined);
  });

  it("returns pipeline info", async () => {
    const app = createApp();
    const response = await request(app).get("/api/info");

    assert.equal(response.status, 200);
    assert.ok(response.body.pipeline.stages.includes("docker-build"));
  });
});


describe("HTTP observability", () => {
  it("exports duration buckets, counts, and bounded unknown-route labels", async () => {
    const app = createApp();
    await request(app).get("/api/info").expect(200);
    await request(app).get("/missing/arbitrary-id").expect(404);
    const metrics = await request(app).get("/metrics").expect(200);
    assert.match(metrics.text, /http_server_requests_seconds_bucket/);
    assert.match(metrics.text, /http_server_requests_seconds_count\{method="GET",route="\/api\/info",status="200"\} 1/);
    assert.match(metrics.text, /route="unmatched",status="404"/);
    assert.ok(!metrics.text.includes("arbitrary-id"));
  });
});
