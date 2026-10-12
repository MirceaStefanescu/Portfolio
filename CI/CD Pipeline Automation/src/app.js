const path = require("path");
const express = require("express");
const promClient = require("prom-client");
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

  app.use(express.json());
  app.use(express.static(path.join(__dirname, "..", "public")));

  app.use((req, res, next) => {
    res.on("finish", () => {
      const route = req.route?.path || req.path || "unknown";
      httpRequestsTotal.inc({
        method: req.method,
        route,
        status: String(res.statusCode)
      });
    });
    next();
  });

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
