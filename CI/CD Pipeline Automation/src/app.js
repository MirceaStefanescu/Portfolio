const path = require("path");
const express = require("express");
const promClient = require("@prometheus-io/client");
const { getBuildInfo } = require("./lib/build-info");

function createApp() {
  const app = express();
  const register = new promClient.Registry();

  promClient.collectDefaultMetrics({ register });

  const httpRequestsTotal = new promClient.Counter({
    name: "http_requests_total",
    help: "Total number of HTTP requests",
    labelNames: ["method", "route", "status"],
    registers: [register]
  });

  const httpDuration = new promClient.Histogram({
    name: "http_server_requests_seconds",
    help: "HTTP request duration in seconds",
    labelNames: ["method", "route", "status"],
    buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
    registers: [register]
  });

  app.use((req, res, next) => {
    const endTimer = httpDuration.startTimer();
    res.on("finish", () => {
      const route = req.route?.path || "unmatched";
      endTimer({ method: req.method, route, status: String(res.statusCode) });
      httpRequestsTotal.inc({
        method: req.method,
        route,
        status: String(res.statusCode)
      });
    });
    next();
  });

  app.use(express.json());
  app.use(express.static(path.join(__dirname, "..", "public")));

  app.get("/health", (_req, res) => {
    res.json({
      status: "ok",
      uptimeSeconds: Math.floor(process.uptime()),
      build: getBuildInfo()
    });
  });

  app.get("/api/info", (_req, res) => {
    res.json({
      build: getBuildInfo(),
      pipeline: {
        stages: [
          "checkout",
          "lint",
          "unit-tests",
          "integration-tests",
          "e2e-tests",
          "docker-build",
          "terraform-apply",
          "ansible-config",
          "deploy"
        ],
        deployMode: process.env.DEPLOY_MODE || "blue-green"
      }
    });
  });

  app.get("/api/status", (_req, res) => {
    res.json({
      environment: process.env.ENVIRONMENT || "dev",
      releaseColor: process.env.RELEASE_COLOR || "blue",
      buildId: process.env.BUILD_ID || "local"
    });
  });

  app.get("/metrics", async (_req, res) => {
    res.set("Content-Type", register.contentType);
    res.send(await register.metrics());
  });

  return app;
}

module.exports = { createApp };
