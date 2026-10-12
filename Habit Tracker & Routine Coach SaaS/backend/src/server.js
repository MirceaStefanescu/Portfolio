const express = require("express");
const cors = require("cors");
const { randomUUID } = require("crypto");

function createApp({ corsOrigin = process.env.CORS_ORIGIN ?? "http://localhost:5173" } = {}) {
  let allowedOrigin;
  try {
    const parsed = new URL(corsOrigin);
    if (typeof corsOrigin !== "string" || !["http:", "https:"].includes(parsed.protocol) ||
        parsed.origin !== corsOrigin || parsed.hostname.includes("*")) {
      throw new Error("Invalid origin");
    }
    allowedOrigin = parsed.origin;
  } catch {
    throw new TypeError("CORS_ORIGIN must be one exact HTTP(S) origin without credentials, path, query, fragment, or wildcard.");
  }

  const app = express();
  app.use(cors({ origin: [allowedOrigin] }));
  app.use(express.json());

  const demoUser = {
    id: "user_demo",
    name: "Demo User",
    timezone: "UTC",
    plan: "starter"
  };

  const habits = new Map();
  const checkins = [];

  const nowIso = () => new Date().toISOString();
  const todayDate = () => new Date().toISOString().slice(0, 10);

  const validateHabit = ({ name, schedule, goal }, partial = false) => {
    if ((!partial || name !== undefined) && (typeof name !== "string" || !name.trim())) {
      return "Habit name must be a nonblank string.";
    }
    if (schedule !== undefined && !["daily", "weekdays", "weekly"].includes(schedule)) {
      return "Schedule must be daily, weekdays or weekly.";
    }
    if (goal !== undefined && typeof goal !== "string") {
      return "Goal must be a string.";
    }
    return null;
  };

  const validDate = (value) => {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(value + "T00:00:00Z");
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  };

  const sampleHabits = [
    { name: "Morning walk", schedule: "daily", goal: "20 min" },
    { name: "Read 10 pages", schedule: "daily", goal: "10 pages" },
    { name: "No sugar", schedule: "weekdays", goal: "Mon-Fri" }
  ];

  sampleHabits.forEach((habit) => {
    const id = randomUUID();
    habits.set(id, {
      id,
      userId: demoUser.id,
      name: habit.name,
      schedule: habit.schedule,
      goal: habit.goal,
      createdAt: nowIso()
    });
  });

  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", time: nowIso() });
  });

  app.get("/api/me", (req, res) => {
    res.json(demoUser);
  });

  app.get("/api/habits", (req, res) => {
    res.json(Array.from(habits.values()));
  });

  app.post("/api/habits", (req, res) => {
    const { name, schedule, goal } = req.body || {};
    const error = validateHabit({ name, schedule, goal });
    if (error) return res.status(400).json({ error });

    const id = randomUUID();
    const habit = {
      id,
      userId: demoUser.id,
      name: name.trim(),
      schedule: schedule ?? "daily",
      goal: goal || "",
      createdAt: nowIso()
    };

    habits.set(id, habit);
    res.status(201).json(habit);
  });

  app.patch("/api/habits/:id", (req, res) => {
    const habit = habits.get(req.params.id);
    if (!habit) {
      return res.status(404).json({ error: "Habit not found." });
    }

    const { name, schedule, goal } = req.body || {};
    const error = validateHabit({ name, schedule, goal }, true);
    if (error) return res.status(400).json({ error });
    if (name !== undefined) habit.name = name.trim();
    if (schedule !== undefined) habit.schedule = schedule;
    if (goal !== undefined) habit.goal = goal;

    habits.set(habit.id, habit);
    res.json(habit);
  });

  app.delete("/api/habits/:id", (req, res) => {
    const exists = habits.delete(req.params.id);
    if (!exists) {
      return res.status(404).json({ error: "Habit not found." });
    }

    for (let i = checkins.length - 1; i >= 0; i -= 1) {
      if (checkins[i].habitId === req.params.id) {
        checkins.splice(i, 1);
      }
    }

    res.status(204).send();
  });

  app.get("/api/checkins", (req, res) => {
    const { habitId } = req.query;
    const result = habitId
      ? checkins.filter((checkin) => checkin.habitId === habitId)
      : checkins;
    res.json(result);
  });

  app.post("/api/habits/:id/checkins", (req, res) => {
    const habit = habits.get(req.params.id);
    if (!habit) {
      return res.status(404).json({ error: "Habit not found." });
    }

    const date = req.body?.date === undefined ? todayDate() : req.body.date;
    if (!validDate(date)) return res.status(400).json({ error: "Date must be a valid YYYY-MM-DD value." });
    const existing = checkins.find((item) => item.habitId === habit.id && item.date === date);
    if (existing) return res.status(200).json(existing);
    const checkin = {
      id: randomUUID(),
      habitId: habit.id,
      userId: demoUser.id,
      date,
      createdAt: nowIso()
    };

    checkins.push(checkin);
    res.status(201).json(checkin);
  });

  app.get("/api/insights/summary", (req, res) => {
    const today = todayDate();
    const last7Days = new Set();
    for (let i = 0; i < 7; i += 1) {
      const date = new Date(today + "T00:00:00Z");
      date.setUTCDate(date.getUTCDate() - i);
      last7Days.add(date.toISOString().slice(0, 10));
    }

    const weeklyCheckins = checkins.filter((checkin) => last7Days.has(checkin.date));
    const activeToday = checkins.filter((checkin) => checkin.date === today).length;

    res.json({
      totalHabits: habits.size,
      totalCheckins: checkins.length,
      activeToday,
      weeklyCheckins: weeklyCheckins.length
    });
  });

  app.get("/api/plans", (req, res) => {
    res.json([
      {
        id: "starter",
        name: "Starter",
        priceMonthlyUsd: 0,
        features: ["Basic habits", "Daily reminders", "Weekly insights"]
      },
      {
        id: "pro",
        name: "Pro",
        priceMonthlyUsd: 9,
        features: ["Unlimited habits", "Advanced insights", "Calendar sync"]
      },
      {
        id: "family",
        name: "Family",
        priceMonthlyUsd: 19,
        features: ["Shared goals", "Accountability groups", "Premium support"]
      }
    ]);
  });

  app.post("/api/billing/checkout", (req, res) => {
    const { planId } = req.body || {};
    res.json({
      planId: planId || "starter",
      sessionId: `demo_${randomUUID()}`,
      url: "https://billing.example.com/checkout/demo"
    });
  });

  return app;
}

if (require.main === module) {
  const port = process.env.PORT || 8085;
  createApp().listen(port, () => {
    console.log("Habit demo API listening on port " + port);
  });
}

module.exports = { createApp };
