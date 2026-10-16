const { randomUUID } = require("crypto");
const { config } = require("./config");

const levels = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3
};

const activeLevel =
  Object.prototype.hasOwnProperty.call(levels, config.logLevel)
    ? levels[config.logLevel]
    : levels.info;

function log(level, message, context = {}) {
  if (levels[level] > activeLevel) {
    return;
  }

  const entry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    ...context
  };

  console.log(JSON.stringify(entry));
}

function requestLogger(req, res, next) {
  const requestId = req.header("x-request-id") || randomUUID();
  const start = process.hrtime.bigint();

  req.requestId = requestId;
  res.setHeader("x-request-id", requestId);

  log("info", "request.start", {
    requestId,
    method: req.method,
    path: req.path
  });

  res.on("finish", () => {
    const durationMs = Number(process.hrtime.bigint() - start) / 1e6;
    log("info", "request.end", {
      requestId,
      method: req.method,
      path: req.path,
      status: res.statusCode,
      durationMs: Math.round(durationMs)
    });
  });

  next();
}

function logError(error, context = {}) {
  log("error", error.message || "error", {
    ...context,
    stack: error.stack
  });
}

module.exports = {
  log,
  logError,
  requestLogger
};
