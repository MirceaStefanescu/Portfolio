const MAX_APP_COUNT = 50;

function normalizeInput(body = {}) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { valid: false, error: "Request must be a JSON object." };
  }
  for (const field of ["appName", "environment", "provider"]) {
    if ((field !== "provider" || body[field] !== undefined) && typeof body[field] !== "string") {
      return { valid: false, error: `${field} must be a string.` };
    }
  }
  const count = body.appCount === undefined ? 1 : body.appCount;
  if ((typeof count !== "number" && typeof count !== "string") ||
      (typeof count === "string" && count.trim() === "") || !Number.isInteger(Number(count))) {
    return { valid: false, error: "App count must be an integer." };
  }
  const rawAppName = body.appName.trim().toLowerCase();
  const rawEnvironment = body.environment.trim().toLowerCase();
  const provider = (body.provider === undefined ? "github" : body.provider).trim().toLowerCase();
  const appCount = Math.max(0, Math.min(MAX_APP_COUNT, Number(count)));

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
