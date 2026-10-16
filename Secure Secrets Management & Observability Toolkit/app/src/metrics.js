const client = require("prom-client");

client.collectDefaultMetrics();

const httpRequestsTotal = new client.Counter({
  name: "http_requests_total",
  help: "Total HTTP requests",
  labelNames: ["method", "route", "status_code"]
});

const httpRequestDuration = new client.Histogram({
  name: "http_request_duration_seconds",
  help: "HTTP request duration in seconds",
  labelNames: ["method", "route", "status_code"]
});

const vaultSecretFetchTotal = new client.Counter({
  name: "vault_secret_fetch_total",
  help: "Total Vault secret fetches"
});

const vaultSecretFetchFailures = new client.Counter({
  name: "vault_secret_fetch_failures_total",
  help: "Total Vault secret fetch failures"
});

const vaultSecretLastFetch = new client.Gauge({
  name: "vault_secret_last_fetch_timestamp",
  help: "Unix timestamp of the last successful Vault secret fetch"
});

const vaultSecretRefreshOk = new client.Gauge({
  name: "vault_secret_refresh_ok",
  help: "Whether the most recent Vault fetch succeeded"
});
const vaultSecretRotatedAt = new client.Gauge({
  name: "vault_secret_rotated_timestamp",
  help: "Unix timestamp of the last secret rotation, zero if invalid"
});

module.exports = {
  register: client.register,
  httpRequestsTotal,
  httpRequestDuration,
  vaultSecretFetchTotal,
  vaultSecretFetchFailures,
  vaultSecretLastFetch,
  vaultSecretRefreshOk,
  vaultSecretRotatedAt
};
