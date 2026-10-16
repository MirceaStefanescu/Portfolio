const express = require("express");
const cors = require("cors");
const { rateLimit } = require("express-rate-limit");
const { randomUUID, randomBytes, createHash, createHmac, timingSafeEqual } = require("node:crypto");
const domain = require("./domain");
const { MemoryStore, SQLiteStore, PostgresStore } = require("./store");
const { startReminders } = require("./reminders");
const { telemetry } = require("./telemetry");
const path = require("node:path");
const { once } = require("node:events");

const hash = value => createHash("sha256").update(value).digest("hex");
class HttpError extends Error { constructor(status, message) { super(message); this.status = status; } }
const fail = (status, message) => { throw new HttpError(status, message); };
const ok = (body, status = 200, headers = {}) => ({ body, status, headers });

function applyBilling(state, event, now) {
  if (!event || typeof event.id !== "string" || event.id.length > 100) fail(400, "Invalid billing event");
  const digest = hash(JSON.stringify(event));
  const previous = state.billingEvents.find(e => e.id === event.id);
  if (previous) {
    if (previous.digest !== digest) fail(409, "Conflicting billing event");
    return { received: true, duplicate: true };
  }
  if (event.type !== "checkout.session.completed") fail(400, "Unsupported demo billing event");
  const session = state.checkouts.find(c => c.id === event.data?.object?.id);
  if (!session || session.status !== "pending" || session.expiresAt < now.toISOString()) fail(409, "Checkout is not pending or has expired");
  const user = state.users.find(u => u.id === session.userId);
  if (!user) fail(400, "Unknown customer");
  session.status = "completed";
  user.plan = session.planId;
  user.subscription = { id: "sub_demo_" + randomUUID(), status: "active", planId: session.planId,
    currentPeriodEnd: new Date(now.getTime() + 30 * 86400000).toISOString(), mode: "demonstration", amountCharged: 0 };
  for (const pending of state.checkouts.filter(c => c.userId === user.id && c.id !== session.id && c.status === "pending")) pending.status = "superseded";
  state.billingEvents.push({ id: event.id, digest, receivedAt: now.toISOString() });
  return { received: true, duplicate: false };
}

function createApp({ corsOrigin = process.env.CORS_ORIGIN ?? "http://localhost:5173", store = new MemoryStore(),
  clock = () => new Date(), billingSecret = randomBytes(32).toString("hex"), tracing, reminders } = {}) {
  let allowedOrigin;
  try {
    const parsed = new URL(corsOrigin);
    if (typeof corsOrigin !== "string" || !["http:", "https:"].includes(parsed.protocol) || parsed.origin !== corsOrigin || parsed.hostname.includes("*")) throw new Error();
    allowedOrigin = parsed.origin;
  } catch { throw new TypeError("CORS_ORIGIN must be one exact HTTP(S) origin without credentials, path, query, fragment, or wildcard."); }
  const app = express(); app.disable("x-powered-by");
  app.use(cors({ origin: [allowedOrigin] }));
  app.use(rateLimit({windowMs: 60 * 1000, limit: 240, standardHeaders: "draft-8", legacyHeaders: false,
    skip: req => req.method === "OPTIONS" || req.path === "/api/health",
    message: {error: "Too many requests; retry after the indicated delay"}}));
  if (tracing) app.use(tracing.middleware);
  app.post("/api/billing/webhook", express.raw({ type: "application/json", limit: "32kb" }), async (req, res, next) => {
    try {
      const parts = Object.fromEntries(String(req.headers["stripe-signature"] || "").split(",").map(p => p.split("=")));
      const timestamp = Number(parts.t);
      if (!Buffer.isBuffer(req.body) || !Number.isInteger(timestamp) || Math.abs(clock().getTime() / 1000 - timestamp) > 300 || !/^[a-f0-9]{64}$/.test(parts.v1 || "")) fail(401, "Invalid webhook signature");
      const expected = createHmac("sha256", billingSecret).update(parts.t + ".").update(req.body).digest();
      if (!timingSafeEqual(expected, Buffer.from(parts.v1, "hex"))) fail(401, "Invalid webhook signature");
      let event;
      try { event = JSON.parse(req.body); } catch { fail(400, "Invalid JSON"); }
      res.json(await store.transaction(state => applyBilling(state, event, clock())));
    } catch (error) { next(error); }
  });
  app.use(express.json({ limit: "32kb" }));
  const route = (method, path, handler, authenticated = true) => app[method](path, async (req, res, next) => {
    try {
      const result = await store.transaction(state => {
        const now = clock(); let user;
        if (authenticated) {
          const bearer = /^Bearer ([A-Za-z0-9_-]{40,128})$/.exec(req.headers.authorization || "");
          const session = bearer && state.sessions.find(s => s.digest === hash(bearer[1]) && s.expiresAt > now.toISOString());
          user = session && state.users.find(u => u.id === session.userId);
          if (!user) fail(401, "Sign in to the local demonstration");
        }
        return handler(req, state, user, now);
      });
      res.set(result.headers).status(result.status);
      if (result.status === 204) res.end();
      else if (typeof result.body === "string") res.send(result.body);
      else res.json(result.body);
    } catch (error) { next(error); }
  });
  app.get("/api/health", (_req, res) => res.json({ status: "ok", mode: "demonstration", storage: store.kind,
    storageError: store.lastError || null,
    delivery: reminders?.status() || { engine: "not-started" }, time: clock().toISOString() }));
  app.get("/api/auth/identities", (_req, res) => res.json(["alice", "bob", "casey"]));
  route("post", "/api/auth/demo", (req, state, _user, now) => {
    if (!["alice", "bob", "casey"].includes(req.body?.identity)) fail(400, "Choose a synthetic demo identity");
    const user = domain.seedUser(state, req.body.identity, now);
    state.sessions = state.sessions.filter(s => s.expiresAt > now.toISOString());
    if (state.sessions.filter(s => s.userId === user.id).length >= 50) fail(429, "Too many demo sessions; sign out or wait for expiry");
    const token = randomBytes(32).toString("base64url");
    state.sessions.push({ userId: user.id, digest: hash(token), expiresAt: new Date(now.getTime() + 8 * 3600000).toISOString() });
    return ok({ token, user, mode: "demonstration" });
  }, false);
  route("post", "/api/auth/logout", (req, state) => {
    const digest = hash(req.headers.authorization.slice(7)); state.sessions = state.sessions.filter(s => s.digest !== digest);
    return ok(null, 204);
  });
  route("get", "/api/me", (_req, _state, user) => ok(user));
  route("patch", "/api/me", (req, _state, user) => {
    const { name, timezone } = req.body || {};
    if (typeof name !== "string" || !name.trim() || name.length > 80 || typeof timezone !== "string") fail(400, "Name and IANA timezone are required");
    try { domain.localDate(clock(), timezone); } catch { fail(400, "Invalid timezone"); }
    Object.assign(user, { name: name.trim(), timezone, onboarded: true }); return ok(user);
  });
  const owned = (state, user, id) => state.habits.find(h => h.id === id && h.userId === user.id) || fail(404, "Habit not found");
  const validated = (input, previous) => { try { return domain.habitInput(input, previous); } catch (error) { fail(400, error.message); } };
  route("get", "/api/habits", (_req, state, user, now) => ok(state.habits.filter(h => h.userId === user.id).map(h =>
    ({ ...h, ...domain.progress(h, state.checkins, domain.localDate(now, user.timezone)) }))));
  route("post", "/api/habits", (req, state, user, now) => {
    if (state.habits.filter(h => h.userId === user.id).length >= 100) fail(409, "Demo limit: 100 habits per identity");
    const habit = { ...validated(req.body || {}), id: randomUUID(), userId: user.id, createdAt: now.toISOString() };
    state.habits.push(habit); return ok(habit, 201);
  });
  route("patch", "/api/habits/:id", (req, state, user) => {
    const habit = owned(state, user, req.params.id); Object.assign(habit, validated(req.body || {}, habit)); return ok(habit);
  });
  route("delete", "/api/habits/:id", (req, state, user) => {
    owned(state, user, req.params.id); state.habits = state.habits.filter(h => h.id !== req.params.id);
    state.checkins = state.checkins.filter(c => c.habitId !== req.params.id); return ok(null, 204);
  });
  route("get", "/api/checkins", (req, state, user) => ok(state.checkins.filter(c => c.userId === user.id && (!req.query.habitId || c.habitId === req.query.habitId))));
  route("post", "/api/habits/:id/checkins", (req, state, user, now) => {
    const habit = owned(state, user, req.params.id), today = domain.localDate(now, user.timezone);
    const date = req.body?.date === undefined ? today : req.body.date;
    if (!domain.validDate(date)) fail(400, "Date must be a valid YYYY-MM-DD value.");
    if (date > today || !domain.due(habit, date)) fail(409, "Check-in must be a scheduled day, today or in the past");
    const existing = state.checkins.find(c => c.habitId === habit.id && c.date === date);
    if (existing) return ok(existing);
    const row = { id: randomUUID(), habitId: habit.id, userId: user.id, date, createdAt: now.toISOString() };
    state.checkins.push(row); return ok(row, 201);
  });
  route("get", "/api/insights/summary", (_req, state, user, now) => {
    const today = domain.localDate(now, user.timezone), week = domain.addDays(today, -6);
    const checkins = state.checkins.filter(c => c.userId === user.id);
    const habits = state.habits.filter(h => h.userId === user.id);
    return ok({ totalHabits: habits.length, totalCheckins: checkins.length, activeToday: checkins.filter(c => c.date === today).length,
      weeklyCheckins: checkins.filter(c => c.date >= week && c.date <= today).length, timezone: user.timezone,
      coachType: "rule-based demonstration", habits: habits.map(h => ({ id: h.id, name: h.name, ...domain.progress(h, checkins, today) })) });
  });
  route("get", "/api/notifications", (_req, state, user) => ok(state.notifications.filter(n => n.userId === user.id).slice(-100).reverse()));
  route("post", "/api/notifications/:id/retry", (req, state, user) => {
    const notification = state.notifications.find(n => n.id === req.params.id && n.userId === user.id) || fail(404, "Notification not found");
    if (notification.status !== "failed") fail(409, "Only failed deliveries can be retried");
    notification.retryCount = (notification.retryCount || 0) + 1; notification.status = "pending";
    return ok(notification, 202);
  });
  route("post", "/api/reminders/test", (_req, state, user, now) => {
    const rows = ["email", "push"].map(channel => ({ id: randomUUID(), userId: user.id, key: randomUUID(), channel,
      title: "Demo reminder", body: "A small action today builds tomorrow's routine.", status: "pending", delivery: "local-demo", createdAt: now.toISOString() }));
    state.notifications.push(...rows); return ok(rows, 202);
  });
  route("get", "/api/export.csv", (_req, state, user) => ok(domain.csv(state, user.id), 200, { "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": 'attachment; filename="habit-checkins.csv"' }));
  route("get", "/api/calendar.ics", (_req, state, user, now) => ok(domain.calendar(state, user, now), 200, { "Content-Type": "text/calendar; charset=utf-8", "Content-Disposition": 'attachment; filename="habit-calendar.ics"' }));
  app.get("/api/plans", (_req, res) => res.json(domain.plans));
  route("post", "/api/billing/checkout", (req, state, user, now) => {
    if (!["pro", "family"].includes(req.body?.planId)) fail(400, "Choose pro or family");
    const session = { id: "cs_demo_" + randomUUID(), userId: user.id, planId: req.body.planId, status: "pending", mode: "demonstration",
      expiresAt: new Date(now.getTime() + 1800000).toISOString() };
    state.checkouts.push(session); return ok({ ...session, sessionId: session.id, amountCharged: 0 }, 201);
  });
  route("post", "/api/billing/checkout/:id/complete", (req, state, user, now) => {
    const session = state.checkouts.find(c => c.id === req.params.id && c.userId === user.id) || fail(404, "Checkout not found");
    const outcome = req.body?.outcome;
    if (!["success", "declined", "cancel"].includes(outcome)) fail(400, "Choose success, declined or cancel");
    if (session.status === "completed" && outcome === "success") return ok(user.subscription);
    if (session.status !== "pending" || session.expiresAt < now.toISOString()) fail(409, "Checkout is closed or expired");
    if (outcome !== "success") { session.status = outcome; return ok({ status: outcome, amountCharged: 0 }); }
    applyBilling(state, { id: "evt_" + session.id, type: "checkout.session.completed", data: { object: { id: session.id } } }, now);
    return ok(user.subscription);
  });
  route("post", "/api/billing/cancel", (_req, _state, user) => {
    if (user.subscription) user.subscription.status = "canceled";
    user.plan = "starter"; return ok(user);
  });
  const groupView = (group, state) => ({ ...group, leaderboard: group.members.map(id => {
    const count = state.checkins.filter(c => c.userId === id && c.date >= group.startsOn && c.date <= group.endsOn).length;
    return { name: state.users.find(u => u.id === id)?.name || id, userId: id, checkins: count, completed: count >= group.target };
  }).sort((a, b) => b.checkins - a.checkins) });
  route("get", "/api/groups", (_req, state, user) => ok(state.groups.filter(g => g.members.includes(user.id)).map(g => groupView(g, state))));
  route("post", "/api/groups", (req, state, user, now) => {
    const { name, target = 7, days = 7 } = req.body || {};
    if (typeof name !== "string" || !name.trim() || name.length > 80 || !Number.isInteger(target) || target < 1 || target > 365 || !Number.isInteger(days) || days < 1 || days > 90) fail(400, "Provide a name, target 1..365 and days 1..90");
    const startsOn = domain.localDate(now, user.timezone);
    const group = { id: randomUUID(), name: name.trim(), invite: randomBytes(12).toString("hex"), members: [user.id],
      target, startsOn, endsOn: domain.addDays(startsOn, days - 1), timezone: user.timezone };
    state.groups.push(group); return ok(groupView(group, state), 201);
  });
  route("post", "/api/groups/join", (req, state, user) => {
    const group = state.groups.find(g => g.invite === req.body?.invite) || fail(404, "Invitation not found");
    if (!group.members.includes(user.id)) group.members.push(user.id); return ok(groupView(group, state));
  });
  if (process.env.SERVE_FRONTEND === "true") {
    const directory = path.join(__dirname, "../public");
    app.use(express.static(directory));
    app.get("*", (req, res, next) => req.path.startsWith("/api/") ? next() : res.sendFile(path.join(directory, "index.html")));
  }
  app.use((error, _req, res, _next) => {
    const status = error.status || 500;
    res.status(status).json({ error: status < 500 ? error.message : "Storage or service unavailable; retry the operation" });
  });
  app.locals.store = store;
  return app;
}

async function start() {
  if (process.env.HABIT_MODE && process.env.HABIT_MODE !== "demo") throw new Error("This application supports explicit demonstration identities only");
  const store = process.env.DATABASE_URL ? await PostgresStore.open(process.env.DATABASE_URL) :
    await SQLiteStore.open(process.env.HABIT_DATA_FILE || "data/habits.sqlite");
  const tracing = telemetry(process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT);
  const intervalMs = Number(process.env.REMINDER_INTERVAL_MS || 10000);
  if (!Number.isInteger(intervalMs) || intervalMs < 500 || intervalMs > 60000) { await store.close(); throw new Error("REMINDER_INTERVAL_MS must be 500..60000"); }
  const reminders = await startReminders(store, { redisUrl: process.env.REDIS_URL, intervalMs });
  const app = createApp({ store, tracing, reminders, billingSecret: process.env.DEMO_BILLING_WEBHOOK_SECRET || randomBytes(32).toString("hex") });
  const server = app.listen(Number(process.env.PORT || 8085), process.env.HOST || "127.0.0.1", () => console.log("Habit demonstration API ready; no real payments or messages"));
  try { await once(server, "listening"); }
  catch (error) { await reminders.close(); await tracing.close(); await store.close(); throw error; }
  let closing = false;
  const close = async () => {
    if (closing) return; closing = true;
    await new Promise(resolve => server.close(resolve));
    await reminders.close(); await tracing.close(); await store.close();
  };
  for (const signal of ["SIGINT", "SIGTERM"]) process.once(signal, () => { void close(); });
  return { app, server, close };
}
if (require.main === module) start().catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { createApp, start, applyBilling };
