const { test } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const { createApp } = require("../src/server");

async function api(t) {
  const server = createApp().listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())));
  const base = "http://127.0.0.1:" + server.address().port;
  const login = await fetch(base + "/api/auth/demo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identity: "alice" }) });
  const { token } = await login.json();
  return (path, method = "GET", body) => fetch(base + path, {
    method, headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
}

test("habit validation rejects bad data without changing existing values", async (t) => {
  const request = await api(t);
  for (const body of [{ name: " " }, { name: 5 }, { name: "Read", schedule: "unknown" }, { name: "Read", goal: {} }]) {
    assert.equal((await request("/api/habits", "POST", body)).status, 400);
  }
  const created = await request("/api/habits", "POST", { name: " Read ", schedule: "weekly", goal: "book" });
  assert.equal(created.status, 201);
  const habit = await created.json();
  assert.equal(habit.name, "Read");
  assert.equal((await request("/api/habits/" + habit.id, "PATCH", { name: null, goal: "changed" })).status, 400);
  const all = await (await request("/api/habits")).json();
  assert.equal(all.find((item) => item.id === habit.id).goal, "book");
});

test("checkins validate real dates and are idempotent per habit and day", async (t) => {
  const request = await api(t);
  const habit = (await (await request("/api/habits")).json())[0];
  const path = "/api/habits/" + habit.id + "/checkins";
  for (const date of ["2026-02-30", "2026-2-01", "", null, 7, {}]) {
    assert.equal((await request(path, "POST", { date })).status, 400);
  }
  const first = await request(path, "POST", { date: "2024-02-29" });
  assert.equal(first.status, 201);
  const saved = await first.json();
  const repeated = await request(path, "POST", { date: "2024-02-29" });
  assert.equal(repeated.status, 200);
  assert.equal((await repeated.json()).id, saved.id);
  assert.equal((await (await request("/api/checkins")).json()).length, 1);
});

test("deleting a habit removes its checkins and returns an empty response", async (t) => {
  const request = await api(t);
  const habit = (await (await request("/api/habits")).json())[0];
  assert.equal((await request("/api/habits/" + habit.id + "/checkins", "POST", {})).status, 201);
  assert.equal((await (await request("/api/checkins")).json()).length, 1);
  const deleted = await request("/api/habits/" + habit.id, "DELETE");
  assert.equal(deleted.status, 204);
  assert.equal(await deleted.text(), "");
  assert.deepEqual(await (await request("/api/checkins")).json(), []);
  assert.equal((await request("/api/habits/" + habit.id, "DELETE")).status, 404);
});

test("summary counts UTC checkins once", async (t) => {
  const request = await api(t);
  const habit = (await (await request("/api/habits")).json())[0];
  const path = "/api/habits/" + habit.id + "/checkins";
  assert.equal((await request(path, "POST", {})).status, 201);
  assert.equal((await request(path, "POST", {})).status, 200);
  const summary = await (await request("/api/insights/summary")).json();
  assert.equal(summary.totalCheckins, 1);
  assert.equal(summary.activeToday, 1);
  assert.equal(summary.weeklyCheckins, 1);
});
