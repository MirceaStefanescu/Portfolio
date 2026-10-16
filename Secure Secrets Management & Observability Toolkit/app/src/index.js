const express = require("express");
const logger = require("./logger");
const metrics = require("./metrics");
const { fetchVaultSecret } = require("./vault");
const { maskSecret } = require("./utils");
const { SecretState } = require("./secretState");

const app = express();
app.use(express.json());

const port = Number(process.env.APP_PORT || 8080);
const vaultAddr = process.env.VAULT_ADDR || "http://vault:8200";
const secretPath = process.env.VAULT_SECRET_PATH || "secret/data/app";
const roleIdFile = process.env.VAULT_ROLE_ID_FILE;
const secretIdFile = process.env.VAULT_SECRET_ID_FILE;

const refreshIntervalMs = Number(process.env.SECRET_REFRESH_INTERVAL_MS || 60000);

const state = new SecretState(refreshIntervalMs * 2);
let pendingRefresh = null;
const notifications = [];

app.use((req, res, next) => {
  const routeLabel = ["/", "/health", "/secret", "/metrics", "/alerts"].includes(req.path) ? req.path : "unmatched";
  const endTimer = metrics.httpRequestDuration.startTimer({
    method: req.method,
    route: routeLabel
  });

  res.on("finish", () => {
    metrics.httpRequestsTotal.inc({
      method: req.method,
      route: routeLabel,
      status_code: res.statusCode
    });
    endTimer({ status_code: res.statusCode });
  });

  next();
});

async function refreshSecret() {
  try {
    const secret = await fetchVaultSecret({
      addr: vaultAddr,
      secretPath,
      roleIdFile,
      secretIdFile
    });

    state.success(secret);

    metrics.vaultSecretFetchTotal.inc();
    metrics.vaultSecretLastFetch.set(Math.floor(state.lastFetchMs / 1000));
    metrics.vaultSecretRefreshOk.set(1);
    const rotated = Date.parse(secret.rotated_at);
    metrics.vaultSecretRotatedAt.set(Number.isFinite(rotated) ? Math.floor(rotated / 1000) : 0);

    logger.info({
      event: "vault_secret_fetch",
      success: true,
      keys: Object.keys(secret || {})
    });
  } catch (error) {
    state.failure();
    metrics.vaultSecretRefreshOk.set(0);
    metrics.vaultSecretFetchFailures.inc();
    logger.error({
      event: "vault_secret_fetch",
      success: false,
      error: error.message
    });
  }
}

async function ensureSecretFresh() {
  if (!state.secret || Date.now() - state.lastFetchMs > refreshIntervalMs) {
    await scheduleRefresh();
  }
  return state.usable() ? state.secret : null;
}

function scheduleRefresh() {
  if (!pendingRefresh) pendingRefresh = refreshSecret().finally(() => { pendingRefresh = null; });
  return pendingRefresh;
}

app.get("/", (req, res) => {
  res.json({
    service: "secure-secrets-toolkit",
    status: "ok"
  });
});

app.get("/health", async (req, res) => {
  const secret = await ensureSecretFresh();
  res.status(state.healthy() ? 200 : 503).json({
    status: state.healthy() ? "ok" : "degraded",
    vault: state.healthy() ? "ok" : (secret ? "cached" : "unavailable"),
    last_secret_fetch: state.lastFetchMs ? new Date(state.lastFetchMs).toISOString() : null
  });
});

app.get("/secret", async (req, res) => {
  const secret = await ensureSecretFresh();

  if (!secret) {
    return res.status(503).json({
      status: "unavailable",
      message: "Vault secret not available"
    });
  }

  return res.json({
    db_password_masked: maskSecret(secret.db_password || ""),
    rotated_at: secret.rotated_at || null,
    fetched_at: state.lastFetchMs ? new Date(state.lastFetchMs).toISOString() : null
  });
});

// Local Grafana contact point: records status only, never secret values or external messages.
app.post("/alerts", (req, res) => {
  if (!Array.isArray(req.body.alerts) || req.body.alerts.length > 100) return res.sendStatus(400);
  for (const alert of req.body.alerts) {
    if (!["firing", "resolved"].includes(alert.status) || typeof alert.labels?.alertname !== "string") return res.sendStatus(400);
  }
  for (const alert of req.body.alerts) {
    const entry = { name: alert.labels.alertname.slice(0, 128), status: alert.status, receivedAt: new Date().toISOString() };
    notifications.push(entry);
    logger.info({ event: "rotation_alert", ...entry });
  }
  notifications.splice(0, Math.max(0, notifications.length - 100));
  res.json({ accepted: req.body.alerts.length });
});
app.get("/alerts", (_req, res) => res.json(notifications));

app.get("/metrics", async (req, res) => {
  res.set("Content-Type", metrics.register.contentType);
  res.end(await metrics.register.metrics());
});

app.listen(port, () => {
  logger.info({
    event: "app_started",
    port,
    vault_addr: vaultAddr,
    secret_path: secretPath
  });

  scheduleRefresh();
  if (refreshIntervalMs > 0) {
    setInterval(scheduleRefresh, refreshIntervalMs).unref();
  }
});
