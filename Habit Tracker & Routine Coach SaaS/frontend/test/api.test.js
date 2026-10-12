import { test } from "node:test";
import assert from "node:assert/strict";
import { fetchJson } from "../src/api.js";

test("successful deletion does not try to parse an empty JSON body", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 204 }));
  assert.equal(await fetchJson("/api/habits/one", { method: "DELETE" }), null);
  assert.deepEqual(fetchMock.mock.calls[0].arguments, ["/api/habits/one", { method: "DELETE" }]);
});

test("ordinary responses return parsed JSON", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ name: "Read" }));
  assert.deepEqual(await fetchJson("/api/habits"), { name: "Read" });
});

test("server errors preserve useful messages and handle non-JSON responses", async (t) => {
  const stub = t.mock.method(globalThis, "fetch", async () => Response.json({ error: "Invalid date" }, { status: 400 }));
  await assert.rejects(fetchJson("/api/habits"), /Invalid date/);
  stub.mock.mockImplementation(async () => new Response("Service unavailable", { status: 503 }));
  await assert.rejects(fetchJson("/api/habits"), /Request failed/);
});
