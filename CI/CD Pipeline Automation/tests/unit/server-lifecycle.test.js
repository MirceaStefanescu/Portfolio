const { it } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const { startServer } = require("../../src/server");

it("repeated server lifecycles release their own signal handlers", async () => {
  const before = ["SIGINT", "SIGTERM"].map((signal) => process.listenerCount(signal));
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const { server } = startServer(0, { handleSignals: true });
    await once(server, "listening");
    assert.deepEqual(["SIGINT", "SIGTERM"].map((signal) => process.listenerCount(signal)),
      before.map((count) => count + 1));
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    assert.deepEqual(["SIGINT", "SIGTERM"].map((signal) => process.listenerCount(signal)), before);
  }
});

it("library use does not register process handlers", async () => {
  const before = process.listenerCount("SIGTERM");
  const { server } = startServer(0);
  await once(server, "listening");
  assert.equal(process.listenerCount("SIGTERM"), before);
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
});
