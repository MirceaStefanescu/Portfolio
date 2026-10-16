const fs = require("node:fs/promises");
const path = require("node:path");
const { initialState } = require("./domain");

class MemoryStore {
  constructor(state = initialState()) { this.state = state; this.tail = Promise.resolve(); this.kind = "memory"; }
  async persist() {}
  transaction(fn) {
    const operation = this.tail.then(async () => {
      const draft = structuredClone(this.state);
      const result = await fn(draft);
      await this.persist(draft);
      this.state = draft;
      return structuredClone(result);
    });
    this.tail = operation.catch(() => {});
    return operation;
  }
  async close() { await this.tail; }
}
class SQLiteStore extends MemoryStore {
  static async open(filename) {
    const target = path.resolve(filename);
    await fs.mkdir(path.dirname(target), { recursive: true });
    const sqlite = require("node:sqlite");
    const Database = sqlite.Database || sqlite.DatabaseSync;
    const result = new SQLiteStore(); result.kind = "sqlite";
    result.db = new Database(target, { timeout: 3000 });
    result.db.exec("PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS habit_demo (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)");
    result.db.prepare("INSERT OR IGNORE INTO habit_demo VALUES (1, ?)").run(JSON.stringify(initialState()));
    return result;
  }
  transaction(fn) {
    const operation = this.tail.then(() => {
      this.db.exec("BEGIN IMMEDIATE");
      try {
        const state = JSON.parse(this.db.prepare("SELECT document FROM habit_demo WHERE id=1").get().document);
        if (state.version !== 1) throw new Error("Unsupported data schema");
        const result = fn(state);
        if (result?.then) throw new Error("SQLite transaction callbacks must be synchronous");
        this.db.prepare("UPDATE habit_demo SET document=? WHERE id=1").run(JSON.stringify(state));
        this.db.exec("COMMIT"); return structuredClone(result);
      } catch (error) { this.db.exec("ROLLBACK"); throw error; }
    });
    this.tail = operation.catch(() => {}); return operation;
  }
  async close() { await this.tail; this.db.close(); }
}
class PostgresStore {
  static async open(connectionString) {
    const { Pool } = require("pg");
    const result = new PostgresStore(); result.kind = "postgres";
    result.pool = new Pool({ connectionString, max: 5, connectionTimeoutMillis: 3000, query_timeout: 10000 });
    result.pool.on("error", () => { result.lastError = "PostgreSQL connection lost; requests will retry through the pool"; });
    try {
      await result.pool.query("CREATE TABLE IF NOT EXISTS habit_demo (id INTEGER PRIMARY KEY CHECK (id = 1), document JSONB NOT NULL)");
      await result.pool.query("INSERT INTO habit_demo VALUES (1, $1) ON CONFLICT DO NOTHING", [initialState()]);
      return result;
    } catch (error) { await result.pool.end(); throw error; }
  }
  async transaction(fn) {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const { rows } = await client.query("SELECT document FROM habit_demo WHERE id=1 FOR UPDATE");
      const state = rows[0].document;
      const result = await fn(state);
      await client.query("UPDATE habit_demo SET document=$1 WHERE id=1", [state]);
      await client.query("COMMIT"); this.lastError = null; return structuredClone(result);
    } catch (error) { await client.query("ROLLBACK"); throw error; }
    finally { client.release(); }
  }
  async close() { await this.pool.end(); }
}
module.exports = { MemoryStore, SQLiteStore, PostgresStore };
