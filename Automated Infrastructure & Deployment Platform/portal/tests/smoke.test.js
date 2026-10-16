const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { once } = require("node:events");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { setTimeout: delay } = require("node:timers/promises");

async function getAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

async function waitForHealthy(url, attempts = 25, intervalMs = 200) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch (error) {
      // Retry until attempts are exhausted.
    }
    await delay(intervalMs);
  }
  throw new Error(`Health check did not succeed for ${url}`);
}

async function shutdown(processHandle) {
  if (!processHandle || processHandle.killed) {
    return;
  }
  processHandle.kill("SIGTERM");
  await Promise.race([once(processHandle, "exit"), delay(2000)]);
}

const hasExpress = fs.existsSync(path.join(__dirname, "..", "node_modules", "express"));

test(
  "portal smoke: generate pipeline template",
  { timeout: 15000, skip: hasExpress ? false : "express not installed" },
  async () => {
  const port = await getAvailablePort();
  const serverPath = path.join(__dirname, "..", "src", "server.js");
  const env = { ...process.env, PORT: String(port), PORTAL_AUTH_MODE: "demo" };

  const child = spawn(process.execPath, [serverPath], {
    env,
    stdio: ["ignore", "pipe", "pipe"]
  });

  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (data) => stdout.push(data));
  child.stderr.on("data", (data) => stderr.push(data));

  try {
    const baseUrl = `http://localhost:${port}`;
    await waitForHealthy(`${baseUrl}/api/health`);

    const response = await fetch(`${baseUrl}/api/pipeline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        appName: "orders-api",
        environment: "dev",
        provider: "github",
        appCount: 2
      })
    });

    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.filename, "ci.yml");
    assert.ok(body.requestId);
    assert.match(body.content, /orders-api-deploy/);
    assert.match(body.content, /ENVIRONMENT: dev/);
  } catch (error) {
    const output = Buffer.concat(stdout).toString("utf8");
    const errOutput = Buffer.concat(stderr).toString("utf8");
    error.message = `${error.message}\nstdout:\n${output}\nstderr:\n${errOutput}`;
    throw error;
  } finally {
    await shutdown(child);
  }
  }
);
