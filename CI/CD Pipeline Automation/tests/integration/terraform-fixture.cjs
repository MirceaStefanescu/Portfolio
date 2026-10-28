'use strict';
// Exercises the actual Makefile and gate; every infrastructure command is a fixture.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const SOURCE = process.env.CICD_TERRAFORM_SOURCE || path.resolve(__dirname, '../..');
const BASH = process.env.BASH_EXECUTABLE || '/bin/bash';
const MAKE = process.env.MAKE_EXECUTABLE || 'make';
const unix = p => p.replace(/\\/g, '/');
function native(p) {
  if (process.platform !== 'win32') return path.normalize(p);
  const result = spawnSync(path.resolve(path.dirname(BASH), '../usr/bin/cygpath.exe'), ['-w', p], {
    timeout: 5000, encoding: 'utf8', windowsHide: true,
    env: { SystemRoot: process.env.SystemRoot, PATH: bashDirs.join(path.delimiter) },
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  return path.normalize(result.stdout.trim());
}
const bashDirs = process.platform === 'win32'
  ? [path.dirname(BASH), path.resolve(path.dirname(BASH), '../usr/bin')]
  : ['/usr/bin', '/bin'];

function fixture(t) {
  const parent = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(parent, 'tf gate '));
  const resolved = fs.realpathSync(root);
  t.after(() => {
    assert.equal(fs.lstatSync(root).isSymbolicLink(), false);
    assert.equal(fs.realpathSync(root), resolved);
    const rel = path.relative(parent, resolved);
    assert.ok(rel && !path.isAbsolute(rel) && !rel.split(path.sep).includes('..'));
    fs.rmSync(resolved, { recursive: true });
  });
  const project = path.join(root, 'project with spaces');
  const bin = path.join(root, 'bin');
  fs.mkdirSync(path.join(project, 'scripts'), { recursive: true });
  fs.mkdirSync(bin);
  for (const env of ['local-kind', 'staging']) {
    fs.mkdirSync(path.join(project, 'terraform/environments', env), { recursive: true });
  }
  for (const rel of ['Makefile', 'scripts/terraform-gate.sh', 'scripts/ci.sh']) {
    fs.copyFileSync(path.join(SOURCE, rel), path.join(project, rel));
    fs.chmodSync(path.join(project, rel), 0o755);
  }
  const calls = path.join(root, 'calls');
  fs.writeFileSync(calls, '');
  const record = tool => `#!/usr/bin/env bash
set -euo pipefail
printf '%s\\0' '${tool}' "$#" "$@" "\${TF_VAR_kubeconfig:-}" "\${TF_VAR_kube_context:-}" >> "$CALLS_FILE"
`;
  fs.writeFileSync(path.join(bin, 'terraform'), record('terraform') + `
op="$2"
[[ "\${FAIL_STEP:-}" != "tf-$op" ]] || exit 41
case "$op" in
  init) ;;
  plan)
    for arg in "$@"; do
      [[ "$arg" != -out=* ]] || printf 'PLAN-BYTES-RECORDED' > "\${arg#-out=}"
    done ;;
  show)
    [[ "$3" == -json && -f "$4" ]] || exit 42
    printf '{"format_version":"1.2","fixture":"FRESH","resource_changes":[]}\\n' ;;
  apply)
    [[ "$#" == 4 && "$3" == -input=false && -f "$4" ]] || exit 43
    [[ "$(< "$4")" == PLAN-BYTES-RECORDED ]] || exit 44 ;;
  *) exit 45 ;;
esac
`, { mode: 0o755 });
  fs.writeFileSync(path.join(bin, 'python'), record('policy') + `
[[ "$#" == 4 && "$1" == ../../scripts/check-policy.py && "$2" == . && "$3" == --plan ]] || exit 46
[[ "$(< "$4")" == *'"fixture":"FRESH"'* ]] || exit 47
[[ "\${FAIL_STEP:-}" != policy ]] || exit 41
`, { mode: 0o755 });
  fs.writeFileSync(path.join(bin, 'kind'), record('kind') + `
[[ "\${FAIL_STEP:-}" != kind ]] || exit 41
`, { mode: 0o755 });
  for (const tool of ['npm', 'docker']) {
    fs.writeFileSync(path.join(bin, tool), record(tool), { mode: 0o755 });
  }
  const env = {
    PATH: [bin, ...bashDirs].join(path.delimiter), HOME: unix(root),
    TMP: os.tmpdir(), TEMP: os.tmpdir(), TMPDIR: unix(os.tmpdir()),
    CALLS_FILE: unix(calls), LC_ALL: 'C',
  };
  for (const key of ['SYSTEMROOT', 'SystemRoot', 'COMSPEC', 'ComSpec']) {
    if (process.env[key]) env[key] = process.env[key];
  }
  function run(route = 'gate', vars = {}, mode = 'plan-apply', makeVars = []) {
    const executable = route === 'make' ? MAKE : BASH;
    const args = route === 'make'
      ? ['--no-print-directory', `SHELL=${unix(BASH)}`, '.SHELLFLAGS=--noprofile --norc -c', ...makeVars, mode === 'ci' ? 'ci' : 'terraform-apply']
      : ['--noprofile', '--norc', unix(path.join(project, 'scripts/terraform-gate.sh')), mode];
    const result = spawnSync(executable, args, {
      cwd: project, env: { ...env, ...vars }, timeout: 15000, encoding: 'utf8',
    });
    assert.equal(result.error, undefined, String(result.error));
    assert.equal(result.signal, null, result.stderr);
    const fields = fs.readFileSync(calls, 'utf8').split('\0');
    assert.equal(fields.pop(), '');
    const rows = [];
    while (fields.length) {
      const tool = fields.shift(), n = Number(fields.shift());
      assert.ok(Number.isInteger(n) && n >= 0 && n <= fields.length - 2);
      rows.push({ tool, args: fields.splice(0, n), config: fields.shift(), context: fields.shift() });
    }
    return { ...result, rows };
  }
  const plan = (env = 'local-kind') => path.join(project, 'terraform/environments', env, 'release.tfplan');
  const json = (env = 'local-kind') => path.join(project, 'terraform/environments', env, 'terraform-plan.json');
  return { run, project, plan, json };
}

function stages(result, expected, status = 0) {
  assert.equal(result.status, status, result.stdout + result.stderr);
  assert.deepEqual(result.rows.map(r => r.tool === 'terraform' ? `tf-${r.args[1]}` : r.tool), expected);
}
function exactPlan(f, result, { image = 'cicd-demo:local', env = 'local-kind', mode = 'blue-green', color = 'blue', build = 'local', sha = 'dev', environment = 'dev' } = {}) {
  const row = result.rows.find(r => r.tool === 'terraform' && r.args[1] === 'plan');
  assert.ok(row, 'actual Terraform plan invocation');
  assert.deepEqual(row.args.slice(0, 3), [`-chdir=terraform/environments/${env}`, 'plan', '-input=false']);
  assert.equal(native(row.args[3].slice(5)).toLowerCase(), f.plan(env).toLowerCase());
  assert.deepEqual(row.args.slice(4), [
    `-var=image=${image}`, `-var=deploy_mode=${mode}`, `-var=release_color=${color}`,
    `-var=environment=${environment}`, `-var=build_id=${build}`, `-var=git_sha=${sha}`,
  ]);
}
function exactApply(f, result, env = 'local-kind') {
  const row = result.rows.find(r => r.tool === 'terraform' && r.args[1] === 'apply');
  assert.ok(row, 'saved-plan apply invocation');
  assert.deepEqual(row.args.slice(0, 3), [`-chdir=terraform/environments/${env}`, 'apply', '-input=false']);
  assert.equal(row.args.length, 4);
  assert.equal(native(row.args[3]).toLowerCase(), f.plan(env).toLowerCase());
}
const full = ['tf-init', 'tf-plan', 'tf-show', 'policy', 'kind', 'tf-apply'];
const noKind = full.filter(s => s !== 'kind');


module.exports = { fixture, stages, exactPlan, exactApply, full, noKind, unix, native };
