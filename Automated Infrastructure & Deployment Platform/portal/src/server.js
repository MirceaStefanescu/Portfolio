const express = require("express");
const path = require("path");
const { config } = require("./config");
const { log, logError, requestLogger } = require("./logger");
const { loadTemplates, renderTemplate } = require("./templates");
const { normalizeInput } = require("./validation");

const app = express();
const publicDir = path.join(__dirname, "..", "public");
const templates = loadTemplates();

const metrics = {
  pipeline: 0,
  terraform: 0,
  helm: 0,
  services: 0
};

app.use(express.json({ limit: "1mb" }));
app.use(requestLogger);
app.use(express.static(publicDir));

app.get("/api/health", (req, res) => {
  res.json({ status: "ok" });
});

app.get(
  "/api/services",
  wrapAsync(async (req, res) => {
  metrics.services += 1;

  const serviceChecks = [
    {
      id: "jenkins",
      name: "Jenkins",
      url: config.jenkinsUrl,
      path: "/login"
    },
    {
      id: "vault",
      name: "Vault",
      url: config.vaultAddr,
      path: "/v1/sys/health"
    },
    {
      id: "prometheus",
      name: "Prometheus",
      url: config.prometheusUrl,
      path: "/-/ready"
    },
    {
      id: "grafana",
      name: "Grafana",
      url: config.grafanaUrl,
      path: "/api/health"
    }
  ];

  const results = await Promise.all(
    serviceChecks.map(async (service) => {
      if (!service.url) {
        return {
          id: service.id,
          name: service.name,
          status: "unconfigured"
        };
      }

      const url = `${service.url}${service.path}`;
      try {
        const response = await fetchWithTimeout(url, 2000);
        const status = response.ok ? "healthy" : "unhealthy";
        return {
          id: service.id,
          name: service.name,
          status,
          httpStatus: response.status
        };
      } catch (error) {
        log("warn", "service.unreachable", {
          requestId: req.requestId,
          service: service.id,
          url
        });
        return {
          id: service.id,
          name: service.name,
          status: "unreachable"
        };
      }
    })
  );

  res.json({ services: results, requestId: req.requestId });
  })
);

app.post("/api/pipeline", (req, res) => {
  const input = normalizeInput(req.body);
  if (!input.valid) {
    log("warn", "pipeline.invalid", {
      requestId: req.requestId,
      error: input.error
    });
    res.status(400).json({ error: input.error, requestId: req.requestId });
    return;
  }

  const provider = input.provider;
  const template = provider === "jenkins" ? templates.jenkins : templates.github;
  metrics.pipeline += 1;

  const content = renderTemplate(template, {
    appName: input.appName,
    environment: input.environment,
    vaultAddr: config.vaultAddr,
    imageRepo: input.appName,
    imageTag: "latest"
  });

  log("info", "pipeline.generated", {
    requestId: req.requestId,
    actionId: req.requestId,
    provider,
    appName: input.appName,
    environment: input.environment
  });

  res.json({
    filename: provider === "jenkins" ? "Jenkinsfile" : "ci.yml",
    content,
    requestId: req.requestId
  });
});

app.post("/api/terraform", (req, res) => {
  const input = normalizeInput(req.body);
  if (!input.valid) {
    log("warn", "terraform.invalid", {
      requestId: req.requestId,
      error: input.error
    });
    res.status(400).json({ error: input.error, requestId: req.requestId });
    return;
  }

  metrics.terraform += 1;

  const content = renderTemplate(templates.terraform, {
    environment: input.environment,
    appCount: input.appCount
  });

  log("info", "terraform.generated", {
    requestId: req.requestId,
    actionId: req.requestId,
    environment: input.environment,
    appCount: input.appCount
  });

  res.json({
    filename: `main-${input.environment}.tf`,
    content,
    requestId: req.requestId
  });
});

app.post("/api/helm", (req, res) => {
  const input = normalizeInput(req.body);
  if (!input.valid) {
    log("warn", "helm.invalid", {
      requestId: req.requestId,
      error: input.error
    });
    res.status(400).json({ error: input.error, requestId: req.requestId });
    return;
  }

  metrics.helm += 1;

  const content = renderTemplate(templates.helm, {
    appName: input.appName,
    environment: input.environment,
    imageRepo: input.appName,
    imageTag: "latest",
    vaultAddr: config.vaultAddr
  });

  log("info", "helm.generated", {
    requestId: req.requestId,
    actionId: req.requestId,
    appName: input.appName,
    environment: input.environment
  });

  res.json({
    filename: `values-${input.environment}.yaml`,
    content,
    requestId: req.requestId
  });
});

app.get("/api/metrics", (req, res) => {
  res.set("Content-Type", "text/plain; version=0.0.4");
  res.send(
    [
      "# HELP portal_requests_total Total API requests.",
      "# TYPE portal_requests_total counter",
      `portal_requests_total{endpoint=\"pipeline\"} ${metrics.pipeline}`,
      `portal_requests_total{endpoint=\"terraform\"} ${metrics.terraform}`,
      `portal_requests_total{endpoint=\"helm\"} ${metrics.helm}`,
      `portal_requests_total{endpoint=\"services\"} ${metrics.services}`
    ].join("\n") + "\n"
  );
});

app.use((req, res) => {
  res.status(404).json({ error: "Not found", requestId: req.requestId });
});

app.use((err, req, res, next) => {
  if (err.type === "entity.parse.failed" || err.type === "entity.too.large") {
    const status = err.type === "entity.too.large" ? 413 : 400;
    return res.status(status).json({ error: status === 413 ? "Request too large" : "Invalid JSON", requestId: req.requestId });
  }
  logError(err, { requestId: req.requestId, path: req.originalUrl });
  res.status(500).json({ error: "Internal server error", requestId: req.requestId });
});

if (require.main === module) {
  app.listen(config.port, () => {
    log("info", "server.ready", { port: config.port });
  });
}
module.exports = { app };

function wrapAsync(handler) {
  return (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
}

async function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}
