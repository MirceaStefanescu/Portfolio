class SecretState {
  constructor(maxAgeMs) {
    if (!Number.isFinite(maxAgeMs) || maxAgeMs <= 0) throw new Error("Secret maximum age must be positive");
    this.maxAgeMs = maxAgeMs;
    this.secret = null;
    this.lastFetchMs = 0;
    this.failed = false;
  }
  success(secret, now = Date.now()) { this.secret = secret; this.lastFetchMs = now; this.failed = false; }
  failure() { this.failed = true; }
  usable(now = Date.now()) { return this.secret !== null && now - this.lastFetchMs <= this.maxAgeMs && now >= this.lastFetchMs; }
  healthy(now = Date.now()) { return this.usable(now) && !this.failed; }
}
module.exports = { SecretState };
