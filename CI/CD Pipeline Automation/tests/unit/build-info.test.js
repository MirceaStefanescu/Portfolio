const { describe, it, beforeEach, after } = require("node:test");
const assert = require("node:assert/strict");
const { getBuildInfo } = require("../../src/lib/build-info");

describe("getBuildInfo", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  after(() => {
    process.env = originalEnv;
  });

  it("uses defaults when env vars are missing", () => {
    delete process.env.ENVIRONMENT;
    delete process.env.RELEASE_COLOR;
    delete process.env.BUILD_ID;
    delete process.env.GIT_SHA;

    const info = getBuildInfo();

    assert.equal(info.environment, "dev");
    assert.equal(info.releaseColor, "blue");
    assert.equal(info.buildId, "local");
    assert.equal(info.gitSha, "dev");
    assert.match(info.startedAt, /^\d{4}-\d{2}-\d{2}T/);
  });

  it("reads values from environment", () => {
    process.env.ENVIRONMENT = "staging";
    process.env.RELEASE_COLOR = "green";
    process.env.BUILD_ID = "42";
    process.env.GIT_SHA = "abc123";

    const info = getBuildInfo();

    assert.equal(info.environment, "staging");
    assert.equal(info.releaseColor, "green");
    assert.equal(info.buildId, "42");
    assert.equal(info.gitSha, "abc123");
  });
});
