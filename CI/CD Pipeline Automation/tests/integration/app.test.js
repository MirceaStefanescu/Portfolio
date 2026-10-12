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
