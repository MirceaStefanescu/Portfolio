const { test } = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");
const { createHmac } = require("node:crypto");
const { mkdtemp, rm } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { createApp } = require("../src/server");
const { MemoryStore, SQLiteStore } = require("../src/store");
const { startReminders } = require("../src/reminders");
const { telemetry } = require("../src/telemetry");
const d = require("../src/domain");

const clock = () => new Date("2026-10-16T12:00:00Z");
async function api(t, options = {}) {
  const store = options.store || new MemoryStore();
  const server = createApp({ clock, store, ...options }).listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = "http://127.0.0.1:" + server.address().port;
  const request = (url, method = "GET", body, token) => fetch(base + url, {
    method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  const login = async identity => {
    const response = await request("/api/auth/demo", "POST", { identity });
    assert.equal(response.status, 200);
    const { token } = await response.json();
    const call = (url, method = "GET", body) => request(url, method, body, token);
    return { call, token };
  };
  return { login, request, store, base };
}

test("authentication isolates identities and revokes the actual session", async t => {
  const { login, request } = await api(t);
  assert.equal((await request("/api/habits")).status, 401);
  const alice = await login("alice"), bob = await login("bob");
  const habit = (await (await alice.call("/api/habits")).json())[0];
  assert.equal((await bob.call("/api/habits/" + habit.id, "PATCH", { name: "stolen" })).status, 404);
  assert.equal((await bob.call("/api/habits/" + habit.id + "/checkins", "POST", {})).status, 404);
  assert.equal((await bob.call("/api/habits/" + habit.id, "DELETE")).status, 404);
  assert.equal((await alice.call("/api/auth/logout", "POST")).status, 204);
  assert.equal((await alice.call("/api/me")).status, 401);
  assert.equal((await bob.call("/api/me")).status, 200);
});

test("onboarding timezone controls date and weekday recurrence", async t => {
  const { login } = await api(t, { clock: () => new Date("2026-10-16T23:30:00Z") });
  const { call } = await login("alice");
  assert.equal((await call("/api/me", "PATCH", { name: "Alice", timezone: "invalid/zone" })).status, 400);
  assert.equal((await call("/api/me", "PATCH", { name: "Alice", timezone: "Europe/Bucharest" })).status, 200);
  const habits = await (await call("/api/habits")).json();
  const weekday = habits.find(h => h.schedule === "weekdays");
  assert.equal(weekday.dueToday, false); // Saturday in Bucharest, Friday UTC.
  assert.equal((await call(`/api/habits/${weekday.id}/checkins`, "POST", {})).status, 409);
  assert.equal((await call(`/api/habits/${habits[0].id}/checkins`, "POST", {})).status, 201);
  assert.equal((await (await call("/api/checkins")).json())[0].date, "2026-10-17");
  assert.equal((await call(`/api/habits/${habits[0].id}/checkins`, "POST", { date: "2026-10-18" })).status, 409);
});

test("schedule-aware streaks skip weekends, allow today's unfinished session and award milestones", () => {
  const habit = { id: "walk", schedule: "weekdays", weekday: 1 };
  const entries = ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"].map(date => ({ habitId: "walk", date }));
  const result = d.progress(habit, entries, "2026-10-19");
  assert.equal(result.currentStreak, 7); assert.equal(result.longestStreak, 7);
  assert.deepEqual(result.milestones, [3, 7]); assert.equal(result.nextDue, "2026-10-19");
  assert.equal(d.progress(habit, entries, "2026-10-20").currentStreak, 0);
  assert.equal(d.due({ schedule: "weekly", weekday: 1 }, "2026-10-19"), true);
  assert.equal(d.due({ schedule: "weekly", weekday: 1 }, "2026-10-20"), false);
});

test("concurrent duplicate check-ins commit exactly once", async t => {
  const { login } = await api(t); const { call } = await login("alice");
  const habit = (await (await call("/api/habits")).json())[0];
  const responses = await Promise.all(Array.from({ length: 20 }, () => call(`/api/habits/${habit.id}/checkins`, "POST", {})));
  assert.equal(responses.filter(r => r.status === 201).length, 1);
  assert.equal(responses.filter(r => r.status === 200).length, 19);
  assert.equal((await (await call("/api/checkins")).json()).length, 1);
});

test("subscription success, failure, duplicate completion and cancellation never charge money", async t => {
  const { login } = await api(t), alice = await login("alice"), bob = await login("bob");
  assert.equal((await alice.call("/api/billing/checkout", "POST", { planId: "invented" })).status, 400);
  let checkout = await (await alice.call("/api/billing/checkout", "POST", { planId: "pro" })).json();
  assert.equal((await bob.call(`/api/billing/checkout/${checkout.id}/complete`, "POST", { outcome: "success" })).status, 404);
  await alice.call(`/api/billing/checkout/${checkout.id}/complete`, "POST", { outcome: "declined" });
  assert.equal((await (await alice.call("/api/me")).json()).plan, "starter");
  checkout = await (await alice.call("/api/billing/checkout", "POST", { planId: "family" })).json();
  const completed = await (await alice.call(`/api/billing/checkout/${checkout.id}/complete`, "POST", { outcome: "success" })).json();
  const repeated = await (await alice.call(`/api/billing/checkout/${checkout.id}/complete`, "POST", { outcome: "success" })).json();
  assert.equal(completed.id, repeated.id); assert.equal(completed.amountCharged, 0);
  await alice.call("/api/billing/cancel", "POST");
  assert.equal((await (await alice.call("/api/me")).json()).plan, "starter");
  assert.equal((await (await alice.call(`/api/billing/checkout/${checkout.id}/complete`, "POST", { outcome: "success" })).json()).status, "canceled");
});

test("Stripe-style webhook requires a fresh signature and rejects conflicting replay", async t => {
  const secret = "test-only-billing-key", { base, login } = await api(t, { billingSecret: secret });
  const { call } = await login("alice");
  const checkout = await (await call("/api/billing/checkout", "POST", { planId: "pro" })).json();
  const event = { id: "event-one", type: "checkout.session.completed", data: { object: { id: checkout.id } } };
  async function send(value, timestamp, key = secret) {
    const body = JSON.stringify(value), signature = createHmac("sha256", key).update(timestamp + "." + body).digest("hex");
    return fetch(base + "/api/billing/webhook", { method: "POST", headers: { "Content-Type": "application/json", "Stripe-Signature": `t=${timestamp},v1=${signature}` }, body });
  }
  const now = clock().getTime() / 1000;
  assert.equal((await send(event, now, "wrong")).status, 401);
  assert.equal((await send(event, now - 301)).status, 401);
  assert.equal((await send(event, now)).status, 200);
  assert.equal((await (await send(event, now)).json()).duplicate, true);
  assert.equal((await send({ ...event, type: "other" }, now)).status, 409);
});

test("local reminders deliver through a durable idempotent outbox without external messages", async t => {
  const store = new MemoryStore();
  await store.transaction(state => d.seedUser(state, "alice", clock()));
  const worker = await startReminders(store, { clock, intervalMs: 60000 }); t.after(() => worker.close());
  await worker.tick(); await worker.tick();
  const entries = await store.transaction(state => state.notifications);
  assert.equal(entries.length, 6); assert.ok(entries.every(n => n.status === "delivered"));
  const push = entries.find(n => n.channel === "push");
  assert.equal(push.firebaseMessage.message.token, "demo-alice");
  assert.equal(worker.status().engine, "local-outbox");
  assert.equal(d.localTime(new Date("2026-10-25T01:30:00Z"), "Europe/Bucharest"), "03:30");
});

test("CSV avoids formula execution and calendar exports recurring, escaped, folded events", () => {
  const state = d.initialState(), user = d.seedUser(state, "alice", clock());
  state.habits[0].name = '=HYPERLINK("https://invalid.example")';
  state.habits[1].name = "A, B; C\nBEGIN:VEVENT" + "ș".repeat(80);
  state.checkins.push({ habitId: state.habits[0].id, userId: user.id, date: "2026-10-16" });
  assert.ok(d.csv(state, user.id).includes("'=HYPERLINK"));
  const calendar = d.calendar(state, user, clock());
  assert.equal(calendar.split("\r\nBEGIN:VEVENT\r\n").length - 1, 3);
  assert.ok(calendar.includes("RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"));
  assert.ok(calendar.includes("A\\, B\\; C\\nBEGIN:VEVENT"));
  assert.ok(calendar.split("\r\n").every(line => Buffer.byteLength(line) <= 75));
});

test("groups require an invitation and expose only shared progress", async t => {
  const { login } = await api(t), alice = await login("alice"), bob = await login("bob");
  const group = await (await alice.call("/api/groups", "POST", { name: "Readers", target: 1, days: 7 })).json();
  assert.deepEqual(await (await bob.call("/api/groups")).json(), []);
  assert.equal((await bob.call("/api/groups/join", "POST", { invite: "bad" })).status, 404);
  await bob.call("/api/groups/join", "POST", { invite: group.invite });
  await bob.call("/api/groups/join", "POST", { invite: group.invite });
  const habit = (await (await bob.call("/api/habits")).json())[0];
  await bob.call(`/api/habits/${habit.id}/checkins`, "POST", {});
  const result = (await (await alice.call("/api/groups")).json())[0];
  assert.equal(result.members.length, 2); assert.equal(result.leaderboard[0].userId, "bob");
  assert.equal(result.leaderboard[0].completed, true); assert.equal(result.leaderboard[0].habits, undefined);
});

test("SQLite preserves state across reopen, rolls back errors and avoids stale overwrite between connections", async t => {
  const directory = await mkdtemp(path.join(tmpdir(), "habit-test-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const filename = path.join(directory, "state.sqlite"), one = await SQLiteStore.open(filename), two = await SQLiteStore.open(filename);
  try {
    await one.transaction(state => d.seedUser(state, "alice", clock()));
    await two.transaction(state => d.seedUser(state, "bob", clock()));
    await assert.rejects(one.transaction(state => { state.users = []; throw new Error("rollback"); }), /rollback/);
    assert.equal((await one.transaction(state => state.users)).length, 2);
  } finally { await one.close(); await two.close(); }
  const reopened = await SQLiteStore.open(filename);
  try { assert.equal((await reopened.transaction(state => state.habits)).length, 6); }
  finally { await reopened.close(); }
});

test("OpenTelemetry sends spans to a local collector without bearer tokens or habit content", async t => {
  const batches = [];
  const collector = http.createServer((req, res) => {
    const chunks = []; req.on("data", data => chunks.push(data));
    req.on("end", () => { batches.push({ url: req.url, body: Buffer.concat(chunks).toString() }); res.setHeader("Content-Type", "application/json"); res.end("{}"); });
  }).listen(0, "127.0.0.1"); await once(collector, "listening");
  t.after(() => new Promise(resolve => collector.close(resolve)));
  const tracing = telemetry(`http://127.0.0.1:${collector.address().port}/v1/traces`);
  const { login } = await api(t, { tracing }), alice = await login("alice");
  await alice.call("/api/habits"); await tracing.close();
  assert.ok(batches.length > 0); assert.equal(batches[0].url, "/v1/traces");
  const body = batches.map(b => b.body).join("");
  assert.ok(body.includes("habit-coach-demo")); assert.ok(body.includes("/api/habits"));
  assert.ok(!body.includes(alice.token)); assert.ok(!body.includes("Morning walk"));
});
