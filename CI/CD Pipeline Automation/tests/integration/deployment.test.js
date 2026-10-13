const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function exercise(script, failure, color = "green", overrides = {}) {
  const temporary = fs.realpathSync(os.tmpdir());
  const workspace = fs.mkdtempSync(path.join(temporary, "routing-regression-"));
  const calls = path.join(workspace, "calls.log");
  fs.writeFileSync(path.join(workspace, "kubectl"), `#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$ROUTING_CALLS"
if [[ "$*" == *"rollout status"* && "$FAIL_ROLLOUT" == "yes" ]]; then exit 1; fi
exit 0
`, { mode: 0o755 });
  try {
    const result = spawnSync(process.env.BASH_EXECUTABLE || "bash",
      [path.resolve(__dirname, "../../scripts", script), color], {
        encoding: "utf8",
        env: { ...process.env, PATH: `${workspace}${path.delimiter}${process.env.PATH}`,
          ROUTING_CALLS: calls, FAIL_ROLLOUT: failure ? "yes" : "no",
          IMAGE: "fixture:checked", LOAD_KIND_IMAGE: "false", KUBECONTEXT: "fixture-only", ...overrides }
      });
    assert.ifError(result.error);
    return { status: result.status, calls: fs.existsSync(calls) ? fs.readFileSync(calls, "utf8") : "" };
  } finally {
    assert.ok(fs.realpathSync(workspace).startsWith(temporary + path.sep));
    fs.rmSync(workspace, { recursive: true });
  }
}

describe("deployment traffic safety", () => {
  for (const script of ["blue-green.sh", "rolling.sh"]) {
    it(`${script} leaves the Service unchanged when rollout fails`, () => {
      const result = exercise(script, true);
      assert.notEqual(result.status, 0);
      assert.match(result.calls, /rollout status/);
      assert.doesNotMatch(result.calls, /patch service|apply -f .*service.yaml/);
    });
    it(`${script} switches only after readiness and replaces incompatible selectors`, () => {
      const result = exercise(script, false);
      assert.equal(result.status, 0);
      const readiness = result.calls.indexOf("rollout status");
      const switchTraffic = result.calls.indexOf("patch service");
      assert.ok(readiness >= 0 && switchTraffic > readiness);
      assert.match(result.calls, /--type=json.*\/spec\/selector/);
    });
  }
  for (const script of ["blue-green.sh", "rolling.sh"]) {
    it(`${script} preserves an external target's current context`, () => {
      const result = exercise(script, false, "green", { TF_ENV: "aws-eks", KUBECONTEXT: "" });
      assert.equal(result.status, 0);
      assert.doesNotMatch(result.calls, /--context|kind-cicd-demo/);
      assert.match(result.calls, /rollout status/);
    });
  }
  it("rejects an unknown color before any Kubernetes mutation", () => {
    const result = exercise("blue-green.sh", false, "invalid");
    assert.notEqual(result.status, 0);
    assert.equal(result.calls, "");
  });
});