const MAX_APP_COUNT = 50;

function normalizeInput(body = {}) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { valid: false, error: "Request must be a JSON object." };
  }
  if (body.appCount !== undefined && !Number.isInteger(Number(body.appCount))) {
    return { valid: false, error: "App count must be an integer." };
  }
  const rawAppName = String(body.appName || "").trim().toLowerCase();
  const rawEnvironment = String(body.environment || "").trim().toLowerCase();
  const provider = String(body.provider || "github").trim().toLowerCase();
  const appCount = Number.isFinite(Number(body.appCount))
    ? Math.max(0, Math.min(MAX_APP_COUNT, Number(body.appCount)))
    : 1;

  if (!isSafeName(rawAppName)) {
    return { valid: false, error: "App name must be lowercase letters, numbers, or hyphens." };
  }

  if (!isSafeName(rawEnvironment)) {
    return {
      valid: false,
      error: "Environment must be lowercase letters, numbers, or hyphens."
    };
  }

  if (provider !== "jenkins" && provider !== "github") {
    return { valid: false, error: "Provider must be jenkins or github." };
  }

  return {
    valid: true,
    appName: rawAppName,
    environment: rawEnvironment,
    provider,
    appCount
  };
}

function isSafeName(value) {
  return typeof value === "string" && value.length <= 63 && /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(value);
}

module.exports = {
  normalizeInput,
  isSafeName
};
