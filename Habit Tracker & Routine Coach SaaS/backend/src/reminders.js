const domain = require("./domain");

async function startReminders(store, { redisUrl, clock = () => new Date(), intervalMs = 30000 } = {}) {
  let queue, worker, busy = false, closing = false, lastError = null;
  if (redisUrl) {
    // BullMQ 6 declares the Redis driver optional. Fail before starting a worker
    // if this explicit application dependency is missing.
    require("ioredis");
    const { Queue, Worker } = require("bullmq");
    const url = new URL(redisUrl);
    if (!["redis:", "rediss:"].includes(url.protocol)) throw new Error("REDIS_URL must use redis or rediss");
    const connection = { host: url.hostname, port: Number(url.port || 6379),
      username: decodeURIComponent(url.username) || undefined, password: decodeURIComponent(url.password) || undefined,
      maxRetriesPerRequest: null, ...(url.protocol === "rediss:" ? { tls: {} } : {}) };
    queue = new Queue("habit-reminders", { connection: { ...connection, maxRetriesPerRequest: 1,
      enableOfflineQueue: false, connectTimeout: 1500 } });
    worker = new Worker("habit-reminders", job => store.transaction(state => domain.deliver(state, job.data.id, clock())), { connection, autorun: false });
    for (const component of [queue, worker]) component.on("error", () => { lastError = "Redis unavailable; pending notifications retained"; });
    worker.waitUntilReady().then(() => {
      if (!closing) return worker.run();
    }).catch(() => { lastError = "Reminder worker unavailable; pending notifications retained"; });
  }
  async function tick() {
    if (busy) return;
    busy = true;
    try {
      const pending = await store.transaction(state => {
        domain.reminders(state, clock());
        return state.notifications.filter(n => n.status === "pending").map(n => ({ id: n.id, retry: n.retryCount || 0 }));
      });
      for (const { id, retry } of pending) {
        if (queue) {
          const jobId = `${id}-${retry}`, existing = await queue.getJob(jobId);
          if (existing && await existing.getState() === "failed") {
            await store.transaction(state => {
              const notification = state.notifications.find(n => n.id === id);
              if (notification?.status === "pending" && (notification.retryCount || 0) === retry) notification.status = "failed";
            });
          } else await queue.add("deliver", { id }, { jobId, attempts: 3, backoff: { type: "exponential", delay: 500 }, removeOnComplete: 1000, removeOnFail: 1000 });
        }
        else await store.transaction(state => domain.deliver(state, id, clock()));
      }
      lastError = null;
    } catch { lastError = "Delivery deferred; durable outbox will be retried"; }
    finally { busy = false; }
  }
  const timer = setInterval(() => { void tick(); }, intervalMs); timer.unref();
  return { tick, status: () => ({ engine: queue ? "BullMQ/Redis" : "local-outbox", lastError }),
    close: async () => { closing = true; clearInterval(timer); if (worker) await worker.close(true); if (queue) await queue.close(); } };
}
module.exports = { startReminders };
