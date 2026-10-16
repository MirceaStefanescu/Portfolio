import { useEffect, useRef, useState } from "react";
import { fetchJson } from "./api.js";

const API = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8085";
const emptyHabit = { name: "", goal: "", schedule: "daily", weekday: 1, reminderTime: "09:00", channels: ["email", "push"] };
const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("habit-demo-token") || "");
  const [user, setUser] = useState(null), [habits, setHabits] = useState([]), [summary, setSummary] = useState(null);
  const [notifications, setNotifications] = useState([]), [groups, setGroups] = useState([]), [plans, setPlans] = useState([]);
  const [form, setForm] = useState(emptyHabit), [editing, setEditing] = useState(null);
  const [profile, setProfile] = useState({ name: "", timezone: "UTC" });
  const [checkout, setCheckout] = useState(null), [invite, setInvite] = useState("");
  const [group, setGroup] = useState({ name: "", target: 7, days: 7 });
  const [status, setStatus] = useState(""), [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const request = (path, method = "GET", body, credential = token) => fetchJson(API + path, {
    method, headers: { "Content-Type": "application/json", ...(credential ? { Authorization: "Bearer " + credential } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  const clear = () => {
    generation.current++; sessionStorage.removeItem("habit-demo-token"); setToken(""); setUser(null);
    setHabits([]); setSummary(null); setNotifications([]); setGroups([]); setCheckout(null); setEditing(null); setForm(emptyHabit);
  };
  const load = async (credential = token) => {
    const revision = ++generation.current;
    const [me, items, insights, inbox, teams, catalog] = await Promise.all([
      "/api/me", "/api/habits", "/api/insights/summary", "/api/notifications", "/api/groups", "/api/plans"
    ].map(path => request(path, "GET", undefined, credential)));
    if (revision !== generation.current) return;
    setUser(me); setProfile({ name: me.name, timezone: me.timezone }); setHabits(items); setSummary(insights);
    setNotifications(inbox); setGroups(teams); setPlans(catalog);
  };
  useEffect(() => { if (token) load(token).catch(error => { setStatus(error.message); clear(); }); }, [token]);
  const act = async (operation, message) => {
    setBusy(true); setStatus("");
    try { await operation(); await load(); setStatus(message); } catch (error) { setStatus(error.message); }
    finally { setBusy(false); }
  };
  const login = async identity => {
    setBusy(true);
    try {
      const result = await request("/api/auth/demo", "POST", { identity }, "");
      sessionStorage.setItem("habit-demo-token", result.token); setToken(result.token); setStatus("Signed in as a synthetic demo identity.");
    } catch (error) { setStatus(error.message); } finally { setBusy(false); }
  };
  const download = async (path, filename) => {
    const response = await fetch(API + path, { headers: { Authorization: "Bearer " + token } });
    if (!response.ok) throw new Error("Export failed. Sign in again if the session expired.");
    const url = URL.createObjectURL(await response.blob()), link = document.createElement("a");
    link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  if (!user) return <main className="page"><header className="hero"><div><p className="eyebrow">Habit Tracker & Routine Coach</p>
    <h1>Build a routine that fits your day.</h1><p className="subtitle">A complete local demonstration. Choose a synthetic identity to explore habits, coaching, reminders and shared challenges.</p></div></header>
    <section className="panel"><h2>Choose a demo identity</h2><p>Each identity has separate habits and a persistent inbox. No external account or payment is required.</p>
      <div className="actions">{["alice", "bob", "casey"].map(identity => <button key={identity} disabled={busy} onClick={() => login(identity)}>{identity[0].toUpperCase() + identity.slice(1)}</button>)}</div>
      <p role="status">{status}</p></section></main>;

  return <main className="page">
    <header className="hero"><div><p className="eyebrow">Habit Tracker & Routine Coach</p><h1>Your next small step, {user.name}.</h1>
      <p className="subtitle">Demonstration mode: local notifications, simulated subscriptions and rule-based coaching. No money is charged.</p>
      <div className="actions"><button className="ghost" disabled={busy} onClick={() => act(() => Promise.resolve(), "Updated.")}>Refresh</button>
        <button className="ghost" disabled={busy} onClick={async () => { try { await request("/api/auth/logout", "POST"); } finally { clear(); } }}>Sign out</button></div></div>
      <div className="stats"><div><span>Habits</span><strong>{summary?.totalHabits}</strong></div><div><span>Check-ins this week</span><strong>{summary?.weeklyCheckins}</strong></div><div><span>Completed today</span><strong>{summary?.activeToday}</strong></div></div>
    </header>
    <p className="status" role="status" aria-live="polite">{status}</p>
    <section className="panel"><h2>{user.onboarded ? "Your profile" : "Make this routine yours"}</h2>
      <form className="habit-form" onSubmit={event => { event.preventDefault(); act(() => request("/api/me", "PATCH", profile), "Profile saved. Dates and reminders follow your timezone."); }}>
        <label>Name<input required maxLength={80} value={profile.name} onChange={event => setProfile({ ...profile, name: event.target.value })}/></label>
        <label>IANA timezone<input required list="timezones" value={profile.timezone} onChange={event => setProfile({ ...profile, timezone: event.target.value })}/></label>
        <datalist id="timezones">{["UTC", "Europe/Bucharest", "Europe/London", "America/New_York", "Asia/Tokyo"].map(zone => <option key={zone} value={zone}/>)}</datalist>
        <button disabled={busy}>Save profile</button></form></section>
    <section className="panel"><h2>{editing ? "Edit habit" : "Create a habit"}</h2>
      <form className="habit-form" onSubmit={event => { event.preventDefault(); act(async () => {
        await request(editing ? "/api/habits/" + editing : "/api/habits", editing ? "PATCH" : "POST", { ...form, reminderTime: form.reminderTime || null });
        setForm(emptyHabit); setEditing(null);
      }, "Habit saved."); }}>
        <label>Habit<input required maxLength={120} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })}/></label>
        <label>Goal<input maxLength={300} value={form.goal} onChange={event => setForm({ ...form, goal: event.target.value })}/></label>
        <label>Schedule<select value={form.schedule} onChange={event => setForm({ ...form, schedule: event.target.value })}>{["daily", "weekdays", "weekly"].map(value => <option key={value}>{value}</option>)}</select></label>
        {form.schedule === "weekly" && <label>Weekday<select value={form.weekday} onChange={event => setForm({ ...form, weekday: Number(event.target.value) })}>{dayNames.map((day, index) => <option key={day} value={index}>{day}</option>)}</select></label>}
        <label>Reminder time (blank to disable)<input type="time" value={form.reminderTime || ""} onChange={event => setForm({ ...form, reminderTime: event.target.value })}/></label>
        <fieldset><legend>Local delivery</legend>{["email", "push"].map(channel => <label className="check" key={channel}><input type="checkbox" checked={form.channels.includes(channel)} onChange={event => setForm({ ...form, channels: event.target.checked ? [...form.channels, channel] : form.channels.filter(value => value !== channel) })}/>{channel}</label>)}</fieldset>
        <button disabled={busy}>{editing ? "Save changes" : "Add habit"}</button>
        {editing && <button type="button" className="ghost" onClick={() => { setEditing(null); setForm(emptyHabit); }}>Cancel edit</button>}
      </form></section>
    <section className="panel"><div className="panel-header"><h2>Your habits</h2><span>{user.timezone}</span></div><div className="habit-grid">
      {habits.map(habit => <article className="habit-card" key={habit.id}><div><h3>{habit.name}</h3><p>{habit.goal}</p>
        <p>{habit.schedule}{habit.schedule === "weekly" ? " on " + dayNames[habit.weekday] : ""} · Next: {habit.nextDue}</p>
        <p><strong>{habit.currentStreak}</strong> scheduled sessions in a row · Best: {habit.longestStreak}</p>
        {habit.milestones.length > 0 && <p className="milestone">Milestones: {habit.milestones.join(", ")} sessions</p>}<p>{habit.coaching}</p></div>
        <div className="actions"><button disabled={busy || !habit.dueToday || habit.completedToday} onClick={() => act(() => request(`/api/habits/${habit.id}/checkins`, "POST", {}), "Check-in recorded.")}>{habit.completedToday ? "Completed" : habit.dueToday ? "Check in" : "Not scheduled today"}</button>
          <button className="ghost" disabled={busy} onClick={() => { setEditing(habit.id); setForm(habit); }}>Edit</button>
          <button className="ghost" disabled={busy} onClick={() => act(() => request("/api/habits/" + habit.id, "DELETE"), "Habit removed.")}>Remove</button></div></article>)}</div></section>
    <section className="panel"><h2>Your local inbox</h2><p>Scheduled reminders are delivered here by the worker. Refresh to see delivery. Push messages simulate the Firebase delivery boundary.</p>
      <button disabled={busy} onClick={() => act(() => request("/api/reminders/test", "POST", {}), "Two demonstration reminders queued; refresh after delivery.")}>Send a demo reminder</button>
      <div className="habit-grid">{notifications.map(item => <article className="habit-card" key={item.id}><h3>{item.title}</h3><p>{item.body}</p><small>{item.channel} · {item.status} · {item.createdAt}</small>
        {item.status === "failed" && <button disabled={busy} onClick={() => act(() => request(`/api/notifications/${item.id}/retry`, "POST", {}), "Retry queued.")}>Retry delivery</button>}</article>)}</div></section>
    <section className="panel"><h2>Calendar and data</h2><p>Import the recurring calendar file into Google Calendar or Apple Calendar. Reimporting is manual; this demonstration does not access your online calendar.</p>
      <div className="actions"><button disabled={busy} onClick={() => act(() => download("/api/calendar.ics", "habit-calendar.ics"), "Calendar exported.")}>Export calendar</button>
        <button disabled={busy} onClick={() => act(() => download("/api/export.csv", "habit-checkins.csv"), "Check-ins exported.")}>Export CSV</button></div></section>
    <section className="panel"><h2>Subscription demonstration</h2><p>Current plan: <strong>{user.plan}</strong>. All demo features remain available. Catalog prices are examples; every simulation charges $0.</p>
      <div className="habit-grid">{plans.map(plan => <article className="habit-card" key={plan.id}><h3>{plan.name}</h3><p>${plan.priceMonthlyUsd}/month illustrative price</p><p>{plan.features.join(" · ")}</p>
        {plan.id !== "starter" && <button disabled={busy || !!checkout} onClick={() => act(async () => setCheckout(await request("/api/billing/checkout", "POST", { planId: plan.id })), "Demo checkout created.")}>Explore {plan.name}</button>}</article>)}</div>
      {checkout && <div className="checkout"><h3>Simulate checkout for {checkout.planId}</h3><p>No card details are collected. Select a result to exercise success or failure.</p><div className="actions">{["success", "declined", "cancel"].map(outcome => <button disabled={busy} key={outcome} onClick={() => act(async () => { await request(`/api/billing/checkout/${checkout.id}/complete`, "POST", { outcome }); setCheckout(null); }, "Simulated checkout: " + outcome)}>{outcome}</button>)}</div></div>}
      {user.plan !== "starter" && <button className="ghost" disabled={busy} onClick={() => act(() => request("/api/billing/cancel", "POST", {}), "Demo subscription canceled; no charge was made.")}>Cancel demo subscription</button>}</section>
    <section className="panel"><h2>Accountability groups</h2><p>Create a challenge, copy its invitation, then sign in as another demo identity to join.</p>
      <form className="habit-form" onSubmit={event => { event.preventDefault(); act(() => request("/api/groups", "POST", group), "Challenge created."); }}>
        <label>Group name<input required maxLength={80} value={group.name} onChange={event => setGroup({ ...group, name: event.target.value })}/></label>
        <label>Check-in target<input type="number" min="1" max="365" value={group.target} onChange={event => setGroup({ ...group, target: Number(event.target.value) })}/></label>
        <label>Days<input type="number" min="1" max="90" value={group.days} onChange={event => setGroup({ ...group, days: Number(event.target.value) })}/></label><button disabled={busy}>Create challenge</button></form>
      <form className="habit-form" onSubmit={event => { event.preventDefault(); act(() => request("/api/groups/join", "POST", { invite }), "Joined challenge."); }}><label>Invitation<input required value={invite} onChange={event => setInvite(event.target.value)}/></label><button disabled={busy}>Join</button></form>
      <div className="habit-grid">{groups.map(team => <article className="habit-card" key={team.id}><h3>{team.name}</h3><p>{team.startsOn} to {team.endsOn} · Target: {team.target}</p><label>Invitation<input readOnly value={team.invite} onFocus={event => event.target.select()}/></label>
        <ul>{team.leaderboard.map(member => <li key={member.userId}>{member.name}: {member.checkins} check-ins {member.completed ? "— target reached" : ""}</li>)}</ul></article>)}</div></section>
  </main>;
}
