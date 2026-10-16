const test = require("node:test");
const assert = require("node:assert/strict");
const { SecretState } = require("../src/secretState");

test("cached secrets expire and recovery clears degraded health", () => {
  const state = new SecretState(1000);
  assert.equal(state.usable(10), false);
  state.success({ db_password: "synthetic" }, 100);
  assert.equal(state.healthy(200), true);
  state.failure();
  assert.equal(state.healthy(300), false);
  assert.equal(state.usable(300), true);
  assert.equal(state.usable(1101), false);
  state.success({ db_password: "new-synthetic" }, 1200);
  assert.equal(state.healthy(1200), true);
  assert.equal(state.usable(1199), false);
});

test("invalid cache age is rejected", () => {
  for (const age of [0, -1, NaN, Infinity]) assert.throws(() => new SecretState(age));
});
