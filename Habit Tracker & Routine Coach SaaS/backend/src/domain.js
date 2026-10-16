const { randomUUID } = require("node:crypto");

const plans = [
  { id: "starter", name: "Starter", priceMonthlyUsd: 0, features: ["Habits", "Reminders", "Insights"] },
  { id: "pro", name: "Pro", priceMonthlyUsd: 9, features: ["Calendar export", "Coaching", "Milestones"] },
  { id: "family", name: "Family", priceMonthlyUsd: 19, features: ["Groups", "Challenges", "Shared progress"] }
];
function initialState() {
  return { version: 1, users: [], habits: [], checkins: [], sessions: [], notifications: [],
    checkouts: [], billingEvents: [], groups: [] };
}
function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value + "T00:00:00Z");
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
function localDate(now, zone = "UTC") {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  return ["year", "month", "day"].map(key => parts.find(p => p.type === key).value).join("-");
}
function localTime(now, zone) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(now);
}
function addDays(date, amount) {
  const value = new Date(date + "T00:00:00Z"); value.setUTCDate(value.getUTCDate() + amount);
  return value.toISOString().slice(0, 10);
}
function due(habit, date) {
  const weekday = new Date(date + "T00:00:00Z").getUTCDay();
  return habit.schedule === "daily" || (habit.schedule === "weekdays" && weekday > 0 && weekday < 6) ||
    (habit.schedule === "weekly" && weekday === habit.weekday);
}
function previousDue(habit, date) {
  do { date = addDays(date, -1); } while (!due(habit, date));
  return date;
}
function progress(habit, checkins, today) {
  const dates = [...new Set(checkins.filter(c => c.habitId === habit.id && c.date <= today && due(habit, c.date)).map(c => c.date))].sort();
  const completed = new Set(dates);
  let day = today, current = 0, best = 0, run = 0, last;
  if (!due(habit, day) || !completed.has(day)) day = previousDue(habit, day);
  while (completed.has(day)) { current++; day = previousDue(habit, day); }
  for (const date of dates) {
    run = last === previousDue(habit, date) ? run + 1 : 1;
    best = Math.max(best, run); last = date;
  }
  let next = today;
  while (!due(habit, next) || completed.has(next)) next = addDays(next, 1);
  return { currentStreak: current, longestStreak: best, dueToday: due(habit, today),
    completedToday: completed.has(today), nextDue: next,
    milestones: [3, 7, 30, 100].filter(n => best >= n),
    coaching: current >= 3 ? `You completed ${current} scheduled sessions in a row. Keep the next step manageable.` :
      "Choose a small, specific action for your next scheduled session. Missing a day is a chance to restart." };
}
function seedUser(state, identity, now) {
  let user = state.users.find(u => u.id === identity);
  if (user) return user;
  user = { id: identity, name: identity[0].toUpperCase() + identity.slice(1), timezone: "UTC", plan: "starter", onboarded: false };
  state.users.push(user);
  for (const [name, goal, schedule] of [["Morning walk", "20 min", "daily"], ["Read 10 pages", "10 pages", "daily"], ["No sugar", "Mon-Fri", "weekdays"]]) {
    state.habits.push({ id: randomUUID(), userId: identity, name, goal, schedule, weekday: 1,
      reminderTime: "09:00", channels: ["email", "push"], createdAt: now.toISOString() });
  }
  return user;
}
function habitInput(input, previous) {
  const result = { ...(previous || { schedule: "daily", goal: "", weekday: 1, reminderTime: "09:00", channels: ["email", "push"] }) };
  for (const key of ["name", "schedule", "goal", "weekday", "reminderTime", "channels"]) {
    if (input[key] !== undefined) result[key] = input[key];
  }
  if (typeof result.name !== "string" || !result.name.trim() || result.name.length > 120) throw new Error("Habit name must be 1-120 characters.");
  if (!["daily", "weekdays", "weekly"].includes(result.schedule)) throw new Error("Schedule must be daily, weekdays or weekly.");
  if (typeof result.goal !== "string" || result.goal.length > 300) throw new Error("Goal must be a string of at most 300 characters.");
  if (!Number.isInteger(result.weekday) || result.weekday < 0 || result.weekday > 6) throw new Error("Weekday must be 0 (Sunday) to 6 (Saturday).");
  if (result.reminderTime !== null && !/^([01]\d|2[0-3]):[0-5]\d$/.test(result.reminderTime)) throw new Error("Reminder must be HH:mm or null.");
  if (!Array.isArray(result.channels) || result.channels.length > 2 || result.channels.some(c => !["email", "push"].includes(c))) throw new Error("Channels must be email and/or push.");
  return { ...result, name: result.name.trim(), channels: [...new Set(result.channels)] };
}
function reminders(state, now, selectedUser) {
  for (const user of state.users.filter(u => !selectedUser || u.id === selectedUser)) {
    const today = localDate(now, user.timezone), time = localTime(now, user.timezone);
    for (const habit of state.habits.filter(h => h.userId === user.id)) {
      if (!habit.reminderTime || time < habit.reminderTime || !due(habit, today) ||
          state.checkins.some(c => c.habitId === habit.id && c.date === today)) continue;
      for (const channel of habit.channels) {
        const key = `${habit.id}/${today}/${channel}`;
        if (!state.notifications.some(n => n.key === key)) state.notifications.push({ id: randomUUID(), key,
          userId: user.id, channel, title: "Habit reminder", body: `Time for ${habit.name}: ${habit.goal}`,
          status: "pending", createdAt: now.toISOString(), delivery: "local-demo" });
      }
    }
  }
}
function deliver(state, id, now) {
  const notification = state.notifications.find(n => n.id === id);
  if (notification && notification.status !== "delivered") {
    notification.status = "delivered"; notification.deliveredAt = now.toISOString();
    notification.provider = notification.channel === "push" ? "Firebase-style local inbox" : "Local email inbox";
    if (notification.channel === "push") notification.firebaseMessage = {
      message: { token: "demo-" + notification.userId, notification: { title: notification.title, body: notification.body } }
    };
  }
}
function csv(state, userId) {
  const cell = value => '"' + String(/^(?:\s*[=+\-@]|[\t\r])/.test(String(value)) ? "'" + value : value).replaceAll('"', '""') + '"';
  const lines = [["habit", "date", "schedule"]];
  for (const row of state.checkins.filter(c => c.userId === userId).sort((a, b) => a.date.localeCompare(b.date))) {
    const habit = state.habits.find(h => h.id === row.habitId);
    if (habit) lines.push([habit.name, row.date, habit.schedule]);
  }
  return lines.map(row => row.map(cell).join(",")).join("\r\n") + "\r\n";
}
function calendar(state, user, now) {
  const escape = value => value.replaceAll("\\", "\\\\").replaceAll("\r", "").replaceAll("\n", "\\n").replaceAll(",", "\\,").replaceAll(";", "\\;");
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Habit Coach Demo//EN", "CALSCALE:GREGORIAN"];
  const days = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
  for (const habit of state.habits.filter(h => h.userId === user.id)) {
    let date = localDate(now, user.timezone);
    while (!due(habit, date)) date = addDays(date, 1);
    const rule = habit.schedule === "daily" ? "FREQ=DAILY" : "FREQ=WEEKLY;BYDAY=" +
      (habit.schedule === "weekdays" ? "MO,TU,WE,TH,FR" : days[habit.weekday]);
    lines.push("BEGIN:VEVENT", "UID:" + habit.id + "@habit-demo", "DTSTAMP:" + now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z"),
      "DTSTART;VALUE=DATE:" + date.replaceAll("-", ""), "RRULE:" + rule, "SUMMARY:" + escape(habit.name), "DESCRIPTION:" + escape(habit.goal), "END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.map(line => {
    const folded = []; let current = "";
    for (const char of line) { if (Buffer.byteLength(current + char) > 74) { folded.push(current); current = " "; } current += char; }
    folded.push(current); return folded.join("\r\n");
  }).join("\r\n") + "\r\n";
}
module.exports = { plans, initialState, validDate, localDate, localTime, addDays, due, progress, seedUser, habitInput, reminders, deliver, csv, calendar };
