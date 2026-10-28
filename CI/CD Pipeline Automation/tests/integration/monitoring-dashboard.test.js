const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { performance } = require("node:perf_hooks");
const request = require("supertest");
const { createApp } = require("../../src/app");

test("the uptime dashboard query uses the exported process start gauge", async () => {
  const dashboard = JSON.parse(fs.readFileSync(path.join(__dirname,
    "../../monitoring/grafana/dashboards/app-dashboard.json"), "utf8"));
  const panel = dashboard.panels.find(item => item.id === 2);
  assert.ok(panel, "the uptime panel exists");
  const expression = panel.targets[0].expr;
  // This checks the dashboard/exporter contract, not a PromQL engine.
  const selectors = expression.match(/process_[a-zA-Z0-9_:]+/g) || [];
  assert.equal(selectors.length, 1, "uptime uses one process metric");

  const app = createApp();
  const metrics = await request(app).get("/metrics").expect(200);
  const line = metrics.text.split("\n").find(item => item.startsWith(`${selectors[0]} `));
  assert.ok(line, `dashboard metric ${selectors[0]} is absent from /metrics`);
  assert.equal(selectors[0], "process_start_time_seconds", "the input is a start timestamp");
  assert.match(metrics.text, /^# TYPE process_start_time_seconds gauge$/m);
  assert.match(expression, /^time\(\)\s*-\s*process_start_time_seconds\{job="cicd-demo"\}$/,
    "calculate elapsed seconds and select the app scrape job");

  const start = Number(line.slice(selectors[0].length + 1));
  assert.ok(Number.isFinite(start) && start > 0, "the exporter provides a finite Unix timestamp");

  const expectedStartTime = performance.timeOrigin / 1000;
  assert.ok(Math.abs(start - expectedStartTime) <= 1,
    "the start gauge agrees with performance.timeOrigin within exporter integer-second rounding");

  const uptimeBefore = process.uptime();
  const health = await request(app).get("/health").expect(200);
  const uptimeAfter = process.uptime();
  assert.ok(Number.isInteger(health.body.uptimeSeconds), "health uptime is an integer");

  assert.ok(
    health.body.uptimeSeconds >= Math.floor(uptimeBefore) &&
    health.body.uptimeSeconds <= Math.floor(uptimeAfter),
    "the health integer uptime is bracketed by process.uptime() samples around the request"
  );
});
