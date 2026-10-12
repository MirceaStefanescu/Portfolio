import { useEffect, useState } from "react";
import { fetchJson } from "./api.js";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8085";

const schedules = [
  { value: "daily", label: "Daily" },
  { value: "weekdays", label: "Weekdays" },
  { value: "weekly", label: "Weekly" }
];

const defaultForm = { name: "", schedule: "daily", goal: "" };


export default function App() {
  const [habits, setHabits] = useState([]);
  const [insights, setInsights] = useState(null);
  const [form, setForm] = useState(defaultForm);
  const [status, setStatus] = useState("");

  const loadAll = async () => {
    const [habitsData, insightsData] = await Promise.all([
      fetchJson(`${API_BASE}/api/habits`),
      fetchJson(`${API_BASE}/api/insights/summary`)
    ]);
    setHabits(habitsData);
    setInsights(insightsData);
  };

  useEffect(() => {
    loadAll().catch((error) => setStatus(error.message));
  }, []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setStatus("Add a habit name.");
      return;
    }

    try {
      setStatus("Creating habit...");
      await fetchJson(`${API_BASE}/api/habits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      });
      setForm(defaultForm);
      await loadAll();
      setStatus("Habit created.");
    } catch (error) {
      setStatus(error.message);
    }
  };

  const handleCheckIn = async (habitId) => {
    try {
      setStatus("Logging check-in...");
      await fetchJson(`${API_BASE}/api/habits/${habitId}/checkins`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      await loadAll();
      setStatus("Check-in recorded.");
    } catch (error) {
      setStatus(error.message);
    }
  };

  const handleDelete = async (habitId) => {
    try {
      setStatus("Removing habit...");
      await fetchJson(`${API_BASE}/api/habits/${habitId}`, { method: "DELETE" });
      await loadAll();
      setStatus("Habit removed.");
    } catch (error) {
      setStatus(error.message);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Habit Tracker & Routine Coach</p>
          <h1>Track your daily habits.</h1>
          <p className="subtitle">
            An in-memory demo for habits, daily check-ins, and seven-day counts.
          </p>
        </div>
        <div className="stats">
          <div>
            <span>Total habits</span>
            <strong>{insights?.totalHabits ?? "-"}</strong>
          </div>
          <div>
            <span>Check-ins (7d)</span>
            <strong>{insights?.weeklyCheckins ?? "-"}</strong>
          </div>
          <div>
            <span>Active today</span>
            <strong>{insights?.activeToday ?? "-"}</strong>
          </div>
        </div>
      </header>

      <section className="panel">
        <h2>Create a habit</h2>
        <form onSubmit={handleCreate} className="habit-form">
          <input
            name="name"
            placeholder="e.g. Morning walk"
            value={form.name}
            onChange={handleChange}
          />
          <select name="schedule" value={form.schedule} onChange={handleChange}>
            {schedules.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            name="goal"
            placeholder="Goal (optional)"
            value={form.goal}
            onChange={handleChange}
          />
          <button type="submit">Add habit</button>
        </form>
        <p className="status">{status}</p>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Your habits</h2>
          <span>{habits.length} active</span>
        </div>
        <div className="habit-grid">
          {habits.map((habit) => (
            <article key={habit.id} className="habit-card">
              <div>
                <h3>{habit.name}</h3>
                <p>Schedule: {habit.schedule}</p>
                {habit.goal && <p>Goal: {habit.goal}</p>}
              </div>
              <div className="actions">
                <button onClick={() => handleCheckIn(habit.id)}>Check-in</button>
                <button className="ghost" onClick={() => handleDelete(habit.id)}>
                  Remove
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
