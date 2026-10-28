'use strict';
// CI orchestration integration tests.
// Coordinator supplies BASH_EXECUTABLE; 'bash' is used for normal repo use on Linux.
// No real tools, services or network are invoked; all external commands are stubs.
// Stubs write to CALLS_FILE (env var, forward-slash path supplied by test harness).

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');

const BASH = process.env.BASH_EXECUTABLE || 'bash';
const CI_SH_SRC = path.resolve(__dirname, '../../scripts/ci.sh');
const TIMEOUT_MS = 15000;

// ---------------------------------------------------------------------------
// Resolve bash's absolute path once, to build a restricted PATH for subprocesses.
// Restricted PATH must provide bash/env/dirname but not real npm/docker/kind etc.
// ---------------------------------------------------------------------------
const BASH_REAL = (() => {
  if (path.isAbsolute(BASH)) {
    try { return fs.realpathSync(BASH); } catch { return BASH; }
  }
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    const candidate = path.join(dir, path.basename(BASH));
    try { fs.accessSync(candidate, fs.constants.X_OK); return fs.realpathSync(candidate); } catch { /* Try the next PATH entry. */ }
  }
  return BASH;
})();
const BASH_DIR = path.dirname(BASH_REAL);

// Platform bin dirs: bash's own dir + sibling usr/bin (Git Bash on Windows) + POSIX standard dirs.
// Filtered to dirs that actually exist so PATH stays clean.
const PLATFORM_BIN_DIRS = [...new Set([
  BASH_DIR,
  path.join(BASH_DIR, '..', 'usr', 'bin'),  // Git Bash: bash is in Git/bin, env/dirname in Git/usr/bin
  '/usr/bin',
  '/bin',
  '/usr/local/bin',
])].filter(d => { try { fs.accessSync(d); return true; } catch { return false; } });

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

/**
 * Creates an isolated temporary directory. Copies the actual ci.sh. Writes
 * harmless recording stubs for every external command and delegated script.
 * Stubs record: tool TAB arg... TAB IMAGE=v TAB IMAGE_NAME=v TAB IMAGE_TAG=v
 *               TAB KUBECONFIG=v TAB KUBECONTEXT=v NEWLINE
 * into the file at CALLS_FILE env var (forward-slash path supplied by makeEnv).
 */
function makeFixture() {
  const tmpParentResolved = fs.realpathSync(os.tmpdir());
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ci-orch-'));
  const resolvedTmp = fs.realpathSync(tmp);

  // Strict path.relative containment: resolvedTmp must be a direct child of tmpParentResolved
  // with no .. components and no absolute escape. Never use startsWith (lacks separator boundary).
  const rel = path.relative(tmpParentResolved, resolvedTmp);
  assert.ok(
    rel.length > 0 && !rel.startsWith('..') && !path.isAbsolute(rel) && !rel.includes('..'),
    `Fixture dir ${resolvedTmp} not safely under ${tmpParentResolved} (rel=${rel})`
  );
  assert.ok(!fs.lstatSync(tmp).isSymbolicLink(), `Fixture root is a link: ${tmp}`);

  const scriptsDir = path.join(resolvedTmp, 'scripts');
  const binDir     = path.join(resolvedTmp, 'bin');
  // callsFile: forward-slash path for CALLS_FILE env var (bash on all platforms)
  const callsFile     = path.join(resolvedTmp, 'calls').replace(/\\/g, '/');
  // callsFilePath: native OS path for Node.js fs.readFileSync
  const callsFilePath = path.join(resolvedTmp, 'calls');

  fs.mkdirSync(scriptsDir, { recursive: true });
  fs.mkdirSync(binDir,     { recursive: true });
  fs.mkdirSync(path.join(resolvedTmp, '.kube'), { recursive: true });

  fs.copyFileSync(CI_SH_SRC, path.join(scriptsDir, 'ci.sh'));
  fs.chmodSync(path.join(scriptsDir, 'ci.sh'), 0o755);

  // Stub source: records tool name, each arg separately (safe for values with spaces),
  // then key env vars. Uses ${CALLS_FILE} — no path interpolated into stub source.
  function stubSrc(name, exitCode) {
    // name is a plain identifier (npm, docker, terraform-gate.sh, etc.) — safe in single quotes.
    return [
      '#!/usr/bin/env bash',
      `printf '%s' '${name}' >> "\${CALLS_FILE}"`,
      `for _a in "$@"; do printf '\\t%s' "$_a" >> "\${CALLS_FILE}"; done`,
      `printf '\\tIMAGE=%s\\tIMAGE_NAME=%s\\tIMAGE_TAG=%s\\tKUBECONFIG=%s\\tKUBECONTEXT=%s\\n'` +
        ` "\${IMAGE:-}" "\${IMAGE_NAME:-}" "\${IMAGE_TAG:-}" "\${KUBECONFIG:-}" "\${KUBECONTEXT:-}"` +
        ` >> "\${CALLS_FILE}"`,
      `exit ${exitCode}`,
    ].join('\n');
  }

  function writeStub(filePath, name, exitCode = 0) {
    fs.writeFileSync(filePath, stubSrc(name, exitCode), { mode: 0o755 });
  }
  function writeFailStub(filePath, name) { writeStub(filePath, name, 1); }

  for (const cmd of ['npm', 'docker', 'kind', 'ansible-playbook']) {
    writeStub(path.join(binDir, cmd), cmd);
  }
  for (const script of ['terraform-gate.sh', 'blue-green.sh', 'rolling.sh', 'canary.sh']) {
    writeStub(path.join(scriptsDir, script), script);
  }

  fs.writeFileSync(callsFilePath, '');

  function cleanup() {
    // Re-resolve; strict containment + symlink check. Assertion failures propagate — never caught.
    assert.ok(!fs.lstatSync(resolvedTmp).isSymbolicLink(), 'Cleanup root became a link');
    const currentResolved = fs.realpathSync(resolvedTmp);
    const currentRel = path.relative(tmpParentResolved, currentResolved);
    assert.ok(
      currentRel.length > 0 && !currentRel.startsWith('..') &&
        !path.isAbsolute(currentRel) && !currentRel.includes('..'),
      `Cleanup target ${currentResolved} not safely under ${tmpParentResolved} (rel=${currentRel})`
    );
    // Verify the resolved path is the same object we created (reject any symlink swap)
    assert.equal(
      currentResolved, resolvedTmp,
      `Cleanup: fixture root changed or became a symlink: ${currentResolved} !== ${resolvedTmp}`
    );
    fs.rmSync(resolvedTmp, { recursive: true, force: true });
  }

  return { resolvedTmp, scriptsDir, binDir, callsFile, callsFilePath, writeStub, writeFailStub, cleanup };
}

// ---------------------------------------------------------------------------
// Run helpers
// ---------------------------------------------------------------------------

/**
 * Restricted env: only fixture binDir + bash runtime dirs in PATH.
 * HOME set to fixture root (no real user profile).
 * CALLS_FILE is the forward-slash path for the stubs.
 * No deployment vars (DEPLOY_MODE, RUN_*, TF_ENV, IMAGE_*, KUBECONFIG, etc.) inherited.
 */
function makeEnv(fixture, overrides = {}) {
  const restrictedPath = [fixture.binDir, ...PLATFORM_BIN_DIRS].join(path.delimiter);
  const base = {
    PATH:       restrictedPath,
    HOME:       fixture.resolvedTmp,   // fixture home; prevents reading real user profile
    CALLS_FILE: fixture.callsFile,     // forward-slash path consumed by stubs
    TMPDIR:     os.tmpdir(),
    TEMP:       os.tmpdir(),
    TMP:        os.tmpdir(),
  };
  // Windows Git Bash needs SYSTEMROOT/COMSPEC for DLL resolution
  if (process.env.SYSTEMROOT) base.SYSTEMROOT = process.env.SYSTEMROOT;
  if (process.env.COMSPEC)    base.COMSPEC    = process.env.COMSPEC;
  return Object.assign(base, overrides);
}

/** Run ci.sh; --noprofile --norc prevents reading login profiles. */
function runCi(fixture, envOverrides = {}) {
  const result = spawnSync(
    BASH,
    ['--noprofile', '--norc', path.join(fixture.scriptsDir, 'ci.sh')],
    {
      env:      makeEnv(fixture, envOverrides),
      cwd:      fixture.resolvedTmp,
      timeout:  TIMEOUT_MS,
      encoding: 'utf8',
    }
  );
  const calls = fs.readFileSync(fixture.callsFilePath, 'utf8');
  return { result, status: result.status, stdout: result.stdout || '', stderr: result.stderr || '', calls };
}

/**
 * Assert that spawnSync itself succeeded (no spawn error, no signal kill).
 * Must be called before interpreting result.status — null status on spawn failure
 * passes any notEqual(status, 0) check and masks the real problem.
 */
function assertSpawnOk(r, label) {
  assert.equal(r.result.error, undefined,
    `${label || 'runCi'}: spawnSync spawn error (not a ci.sh exit): ${r.result.error}`);
  assert.equal(r.result.signal, null,
    `${label || 'runCi'}: process killed by signal: ${r.result.signal}`);
}

/** Parse calls file into array of { tool, args[], IMAGE, IMAGE_NAME, IMAGE_TAG, KUBECONFIG, KUBECONTEXT }. */
function parseCalls(raw) {
  return raw.split('\n').filter(Boolean).map(line => {
    line = line.replace(/\r$/, '');   // strip Windows CR if present
    const parts = line.split('\t');
    const tool  = parts[0];
    const metaStart = parts.findIndex(p => p.startsWith('IMAGE='));
    const args = (metaStart === -1 ? parts.slice(1) : parts.slice(1, metaStart));
    const meta = {};
    (metaStart === -1 ? [] : parts.slice(metaStart)).forEach(p => {
      const eq = p.indexOf('=');
      if (eq !== -1) meta[p.slice(0, eq)] = p.slice(eq + 1);
    });
    return { tool, args, ...meta };
  });
}

/**
 * Assert an exact ordered sequence of calls.
 * expected: array of { tool, args?, meta? } where meta keys are IMAGE, IMAGE_NAME, etc.
 */
function assertCallSequence(calls, expected, label) {
  assert.equal(
    calls.length, expected.length,
    `${label}: expected ${expected.length} call(s), got ${calls.length}.` +
    ` Actual: [${calls.map(c => [c.tool, ...c.args].join(' ')).join('], [')}]`
  );
  for (let i = 0; i < expected.length; i++) {
    const e = expected[i], a = calls[i];
    assert.equal(a.tool, e.tool, `${label} call[${i}]: tool`);
    if (e.args !== undefined)
      assert.deepEqual(a.args, e.args, `${label} call[${i}] (${a.tool}): args`);
    if (e.meta !== undefined)
      for (const [k, v] of Object.entries(e.meta))
        assert.equal(a[k], v, `${label} call[${i}] (${a.tool}): env.${k}`);
  }
}

// ---------------------------------------------------------------------------
// Custom npm stub for failure tests: records all calls, exits 1 on failOn command.
// ---------------------------------------------------------------------------
function writeNpmFailStub(fix, failOn) {
  const conditions = {
    ci:   `if [[ "\${1:-}" == "ci" ]]; then exit 1; fi`,
    lint: `if [[ "\${1:-}" == "run" && "\${2:-}" == "lint" ]]; then exit 1; fi`,
    test: `if [[ "\${1:-}" == "test" ]]; then exit 1; fi`,
  };
  const src = [
    '#!/usr/bin/env bash',
    `printf '%s' 'npm' >> "\${CALLS_FILE}"`,
    `for _a in "$@"; do printf '\\t%s' "$_a" >> "\${CALLS_FILE}"; done`,
    `printf '\\tIMAGE=%s\\tIMAGE_NAME=%s\\tIMAGE_TAG=%s\\tKUBECONFIG=%s\\tKUBECONTEXT=%s\\n'` +
      ` "\${IMAGE:-}" "\${IMAGE_NAME:-}" "\${IMAGE_TAG:-}" "\${KUBECONFIG:-}" "\${KUBECONTEXT:-}"` +
      ` >> "\${CALLS_FILE}"`,
    conditions[failOn],
    'exit 0',
  ].join('\n');
  fs.writeFileSync(path.join(fix.binDir, 'npm'), src, { mode: 0o755 });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test('defaults: exact npm-ci / npm-run-lint / npm-test / docker-build sequence, no other calls', () => {
  const fix = makeFixture();
  try {
    const r = runCi(fix, { IMAGE_NAME: 'demo', IMAGE_TAG: 'v1' });
    assertSpawnOk(r, 'defaults');
    assert.equal(r.status, 0, `Expected exit 0. stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);
    assertCallSequence(calls, [
      { tool: 'npm',    args: ['ci'] },
      { tool: 'npm',    args: ['run', 'lint'] },
      { tool: 'npm',    args: ['test'] },
      { tool: 'docker', args: ['build', '-t', 'demo:v1', '.'],
        meta: { IMAGE_NAME: 'demo', IMAGE_TAG: 'v1' } },
    ], 'defaults');
  } finally {
    fix.cleanup();
  }
});

test('explicit-empty vars use defaults and succeed without deploy or terraform calls', () => {
  const fix = makeFixture();
  try {
    // Explicitly set all control vars to ''; bash :- operator substitutes defaults for empty strings
    const r = runCi(fix, {
      DEPLOY_MODE:   '',
      RELEASE_COLOR: '',
      RUN_TERRAFORM: '',
      RUN_ANSIBLE:   '',
      RUN_DEPLOY:    '',
      TF_ENV:        '',
      IMAGE_NAME:    'demo',
      IMAGE_TAG:     'v1',
    });
    assertSpawnOk(r, 'explicit-empty');
    assert.equal(r.status, 0, `Expected exit 0 for empty vars. stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);
    assertCallSequence(calls, [
      { tool: 'npm', args: ['ci'] },
      { tool: 'npm', args: ['run', 'lint'] },
      { tool: 'npm', args: ['test'] },
      { tool: 'docker', args: ['build', '-t', 'demo:v1', '.'] },
    ], 'explicit-empty');
    assert.ok(!calls.find(c => c.tool === 'blue-green.sh'),    'no deploy on empty RUN_DEPLOY');
    assert.ok(!calls.find(c => c.tool === 'terraform-gate.sh'),'no terraform on empty RUN_TERRAFORM');
    assert.ok(!calls.find(c => c.tool === 'kind'),             'no kind load on empty flags');
    assert.ok(!calls.find(c => c.tool === 'ansible-playbook'), 'no ansible on empty RUN_ANSIBLE');
  } finally {
    fix.cleanup();
  }
});

test('blue-green deploy: exact script, color arg, IMAGE env, kind argv', () => {
  const fix = makeFixture();
  try {
    const r = runCi(fix, {
      DEPLOY_MODE:   'blue-green',
      RELEASE_COLOR: 'green',
      RUN_DEPLOY:    'true',
      IMAGE_NAME:    'myapp',
      IMAGE_TAG:     'sha-abc',
      TF_ENV:        'local-kind',
      CLUSTER_NAME:  'ci-cluster',
    });
    assertSpawnOk(r, 'blue-green');
    assert.equal(r.status, 0, `stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);

    const kindCall = calls.find(c => c.tool === 'kind');
    assert.ok(kindCall, 'kind must be called for local-kind + RUN_DEPLOY=true');
    assert.deepEqual(kindCall.args,
      ['load', 'docker-image', 'myapp:sha-abc', '--name', 'ci-cluster'], 'kind argv');

    const bgCall = calls.find(c => c.tool === 'blue-green.sh');
    assert.ok(bgCall, 'blue-green.sh must be called');
    assert.deepEqual(bgCall.args, ['green'], 'blue-green.sh color arg');
    assert.equal(bgCall.IMAGE,      'myapp:sha-abc', 'blue-green.sh IMAGE');
    assert.equal(bgCall.IMAGE_NAME, 'myapp',         'blue-green.sh IMAGE_NAME');
    assert.equal(bgCall.IMAGE_TAG,  'sha-abc',       'blue-green.sh IMAGE_TAG');
    assert.ok(!calls.find(c => c.tool === 'rolling.sh'), 'no rolling.sh');
    assert.ok(!calls.find(c => c.tool === 'canary.sh'),  'no canary.sh');
  } finally {
    fix.cleanup();
  }
});

test('rolling deploy: exact rolling.sh call, IMAGE env, no blue-green or canary', () => {
  const fix = makeFixture();
  try {
    const r = runCi(fix, {
      DEPLOY_MODE:   'rolling',
      RELEASE_COLOR: 'blue',
      RUN_DEPLOY:    'true',
      IMAGE_NAME:    'myapp',
      IMAGE_TAG:     'v2',
      TF_ENV:        'local-kind',
    });
    assertSpawnOk(r, 'rolling');
    assert.equal(r.status, 0, `stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);
    const rollCall = calls.find(c => c.tool === 'rolling.sh');
    assert.ok(rollCall, 'rolling.sh must be called');
    assert.deepEqual(rollCall.args, [], 'rolling.sh takes no positional args');
    assert.equal(rollCall.IMAGE, 'myapp:v2', 'rolling.sh IMAGE env');
    assert.ok(!calls.find(c => c.tool === 'blue-green.sh'), 'no blue-green.sh');
    assert.ok(!calls.find(c => c.tool === 'canary.sh'),     'no canary.sh');
  } finally {
    fix.cleanup();
  }
});

test('canary deploy: exact canary.sh call, IMAGE_NAME/IMAGE_TAG env, no others', () => {
  const fix = makeFixture();
  try {
    const r = runCi(fix, {
      DEPLOY_MODE:   'canary',
      RELEASE_COLOR: 'blue',
      RUN_DEPLOY:    'true',
      RUN_TERRAFORM: 'false',
      IMAGE_NAME:    'myapp',
      IMAGE_TAG:     'v3',
      TF_ENV:        'local-kind',
    });
    assertSpawnOk(r, 'canary');
    assert.equal(r.status, 0, `stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);
    const canaryCall = calls.find(c => c.tool === 'canary.sh');
    assert.ok(canaryCall, 'canary.sh must be called');
    assert.deepEqual(canaryCall.args, [], 'canary.sh takes no positional args');
    assert.equal(canaryCall.IMAGE_NAME, 'myapp', 'canary.sh IMAGE_NAME');
    assert.equal(canaryCall.IMAGE_TAG,  'v3',    'canary.sh IMAGE_TAG');
    assert.ok(!calls.find(c => c.tool === 'blue-green.sh'), 'no blue-green.sh');
    assert.ok(!calls.find(c => c.tool === 'rolling.sh'),    'no rolling.sh');
  } finally {
    fix.cleanup();
  }
});

test('all-enabled: exact terraform plan-apply arg, Ansible metadata args, correct order', () => {
  const fix = makeFixture();
  try {
    const r = runCi(fix, {
      DEPLOY_MODE:   'blue-green',
      RELEASE_COLOR: 'blue',
      RUN_TERRAFORM: 'true',
      RUN_ANSIBLE:   'true',
      RUN_DEPLOY:    'true',
      IMAGE_NAME:    'myapp',
      IMAGE_TAG:     'v4',
      TF_ENV:        'local-kind',
      CLUSTER_NAME:  'cicd-demo',
      ENVIRONMENT:   'staging',
      GIT_SHA:       'deadbeef',
    });
    assertSpawnOk(r, 'all-enabled');
    assert.equal(r.status, 0, `stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);
    const tools  = calls.map(c => c.tool);
    assertCallSequence(calls, [
      { tool: 'npm', args: ['ci'] },
      { tool: 'npm', args: ['run', 'lint'] },
      { tool: 'npm', args: ['test'] },
      { tool: 'docker', args: ['build', '-t', 'myapp:v4', '.'] },
      { tool: 'kind', args: ['load', 'docker-image', 'myapp:v4', '--name', 'cicd-demo'] },
      { tool: 'terraform-gate.sh', args: ['plan-apply'], meta: { IMAGE_NAME: 'myapp', IMAGE_TAG: 'v4' } },
      { tool: 'ansible-playbook' },
      { tool: 'blue-green.sh', args: ['blue'], meta: { IMAGE: 'myapp:v4' } },
    ], 'all-enabled');

    const tfCall = calls.find(c => c.tool === 'terraform-gate.sh');
    assert.ok(tfCall, 'terraform-gate.sh must be called');
    assert.deepEqual(tfCall.args, ['plan-apply'], 'terraform-gate.sh arg');

    const ansibleCall = calls.find(c => c.tool === 'ansible-playbook');
    assert.ok(ansibleCall, 'ansible-playbook must be called');
    assert.deepEqual(ansibleCall.args, [
      '-i', 'ansible/inventory/local.ini',
      'ansible/playbooks/configure-app.yml',
      '-e', 'app_environment=staging',
      '-e', 'release_color=blue',
      '-e', 'build_id=v4',
      '-e', 'git_sha=deadbeef',
      '-e', 'deploy_mode=blue-green',
    ], 'ansible-playbook args');

    const bgCall = calls.find(c => c.tool === 'blue-green.sh');
    assert.ok(bgCall, 'blue-green.sh must be called');

    const tfIdx     = tools.indexOf('terraform-gate.sh');
    const ansibleIdx = tools.indexOf('ansible-playbook');
    const bgIdx     = tools.indexOf('blue-green.sh');
    assert.ok(tfIdx < ansibleIdx, 'Terraform must precede Ansible');
    assert.ok(ansibleIdx < bgIdx, 'Ansible must precede deploy');
  } finally {
    fix.cleanup();
  }
});

// ---------------------------------------------------------------------------
// Failure tests: assert exit 1, spawnOk, and EXACT complete call sequence
// up to and including the failed stage (no more, no less).
// ---------------------------------------------------------------------------

test('npm ci failure: exit 1, exactly [npm(ci)] recorded', () => {
  const fix = makeFixture();
  try {
    writeNpmFailStub(fix, 'ci');
    const r = runCi(fix, { IMAGE_NAME: 'demo', IMAGE_TAG: 'v1', TF_ENV: 'local-kind' });
    assertSpawnOk(r, 'npm-ci-fail');
    assert.equal(r.status, 1, `Expected exit 1. stderr: ${r.stderr}`);
    assertCallSequence(parseCalls(r.calls), [
      { tool: 'npm', args: ['ci'] },
    ], 'npm-ci-fail');
  } finally {
    fix.cleanup();
  }
});

test('npm lint failure: exit 1, exactly [npm(ci), npm(run,lint)] recorded', () => {
  const fix = makeFixture();
  try {
    writeNpmFailStub(fix, 'lint');
    const r = runCi(fix, { IMAGE_NAME: 'demo', IMAGE_TAG: 'v1', RUN_DEPLOY: 'true', TF_ENV: 'local-kind' });
    assertSpawnOk(r, 'npm-lint-fail');
    assert.equal(r.status, 1, `Expected exit 1. stderr: ${r.stderr}`);
    assertCallSequence(parseCalls(r.calls), [
      { tool: 'npm', args: ['ci'] },
      { tool: 'npm', args: ['run', 'lint'] },
    ], 'npm-lint-fail');
  } finally {
    fix.cleanup();
  }
});

test('npm test failure: exit 1, exactly [npm(ci), npm(run,lint), npm(test)] recorded', () => {
  const fix = makeFixture();
  try {
    writeNpmFailStub(fix, 'test');
    const r = runCi(fix, { IMAGE_NAME: 'demo', IMAGE_TAG: 'v1', RUN_DEPLOY: 'true', TF_ENV: 'local-kind' });
    assertSpawnOk(r, 'npm-test-fail');
    assert.equal(r.status, 1, `Expected exit 1. stderr: ${r.stderr}`);
    assertCallSequence(parseCalls(r.calls), [
      { tool: 'npm', args: ['ci'] },
      { tool: 'npm', args: ['run', 'lint'] },
      { tool: 'npm', args: ['test'] },
    ], 'npm-test-fail');
  } finally {
    fix.cleanup();
  }
});

test('docker failure: exit 1, exact 4-call sequence through docker', () => {
  const fix = makeFixture();
  try {
    fix.writeFailStub(path.join(fix.binDir, 'docker'), 'docker');
    const r = runCi(fix, {
      IMAGE_NAME: 'demo', IMAGE_TAG: 'v1',
      RUN_DEPLOY: 'true', RUN_TERRAFORM: 'true',
      TF_ENV: 'local-kind',
    });
    assertSpawnOk(r, 'docker-fail');
    assert.equal(r.status, 1, `Expected exit 1. stderr: ${r.stderr}`);
    assertCallSequence(parseCalls(r.calls), [
      { tool: 'npm',    args: ['ci'] },
      { tool: 'npm',    args: ['run', 'lint'] },
      { tool: 'npm',    args: ['test'] },
      { tool: 'docker', args: ['build', '-t', 'demo:v1', '.'] },
    ], 'docker-fail');
  } finally {
    fix.cleanup();
  }
});

test('kind failure: exit 1, exact 5-call sequence through kind', () => {
  const fix = makeFixture();
  try {
    fix.writeFailStub(path.join(fix.binDir, 'kind'), 'kind');
    const r = runCi(fix, {
      IMAGE_NAME: 'demo', IMAGE_TAG: 'v1',
      RUN_DEPLOY: 'true', RUN_TERRAFORM: 'true',
      TF_ENV: 'local-kind', CLUSTER_NAME: 'cicd-demo',
    });
    assertSpawnOk(r, 'kind-fail');
    assert.equal(r.status, 1, `Expected exit 1. stderr: ${r.stderr}`);
    assertCallSequence(parseCalls(r.calls), [
      { tool: 'npm',    args: ['ci'] },
      { tool: 'npm',    args: ['run', 'lint'] },
      { tool: 'npm',    args: ['test'] },
      { tool: 'docker', args: ['build', '-t', 'demo:v1', '.'] },
      { tool: 'kind',   args: ['load', 'docker-image', 'demo:v1', '--name', 'cicd-demo'] },
    ], 'kind-fail');
  } finally {
    fix.cleanup();
  }
});

test('Terraform failure: exit 1, exact 6-call sequence through terraform-gate.sh', () => {
  const fix = makeFixture();
  try {
    fix.writeFailStub(path.join(fix.scriptsDir, 'terraform-gate.sh'), 'terraform-gate.sh');
    const r = runCi(fix, {
      IMAGE_NAME: 'demo', IMAGE_TAG: 'v1',
      RUN_TERRAFORM: 'true', RUN_ANSIBLE: 'true', RUN_DEPLOY: 'true',
      TF_ENV: 'local-kind', CLUSTER_NAME: 'cicd-demo',
    });
    assertSpawnOk(r, 'terraform-fail');
    assert.equal(r.status, 1, `Expected exit 1. stderr: ${r.stderr}`);
    assertCallSequence(parseCalls(r.calls), [
      { tool: 'npm',               args: ['ci'] },
      { tool: 'npm',               args: ['run', 'lint'] },
      { tool: 'npm',               args: ['test'] },
      { tool: 'docker',            args: ['build', '-t', 'demo:v1', '.'] },
      { tool: 'kind',              args: ['load', 'docker-image', 'demo:v1', '--name', 'cicd-demo'] },
      { tool: 'terraform-gate.sh', args: ['plan-apply'] },
    ], 'terraform-fail');
  } finally {
    fix.cleanup();
  }
});

test('Ansible failure: exit 1, exact 6-call sequence through ansible-playbook', () => {
  // RUN_TERRAFORM=false so no terraform; RUN_DEPLOY=true causes kind load
  const fix = makeFixture();
  try {
    fix.writeFailStub(path.join(fix.binDir, 'ansible-playbook'), 'ansible-playbook');
    const r = runCi(fix, {
      IMAGE_NAME: 'demo', IMAGE_TAG: 'v1',
      RUN_ANSIBLE: 'true', RUN_DEPLOY: 'true',
      TF_ENV: 'local-kind', CLUSTER_NAME: 'cicd-demo',
      ENVIRONMENT: 'dev', GIT_SHA: 'dev',
    });
    assertSpawnOk(r, 'ansible-fail');
    assert.equal(r.status, 1, `Expected exit 1. stderr: ${r.stderr}`);
    assertCallSequence(parseCalls(r.calls), [
      { tool: 'npm',              args: ['ci'] },
      { tool: 'npm',              args: ['run', 'lint'] },
      { tool: 'npm',              args: ['test'] },
      { tool: 'docker',           args: ['build', '-t', 'demo:v1', '.'] },
      { tool: 'kind',             args: ['load', 'docker-image', 'demo:v1', '--name', 'cicd-demo'] },
      { tool: 'ansible-playbook', args: [
          '-i', 'ansible/inventory/local.ini',
          'ansible/playbooks/configure-app.yml',
          '-e', 'app_environment=dev',
          '-e', 'release_color=blue',
          '-e', 'build_id=v1',
          '-e', 'git_sha=dev',
          '-e', 'deploy_mode=blue-green',
        ]},
    ], 'ansible-fail');
  } finally {
    fix.cleanup();
  }
});

// ---------------------------------------------------------------------------
// Validation rejection: exit 2, zero calls, offending variable name in stderr.
// ---------------------------------------------------------------------------

function assertValidationRejection(label, envOverrides, expectedVarName) {
  const fix = makeFixture();
  try {
    const r = runCi(fix, envOverrides);
    assertSpawnOk(r, label);
    assert.equal(r.status, 2,
      `${label}: expected exit 2, got ${r.status}. stderr: ${r.stderr}`);
    assert.equal(r.calls.trim(), '',
      `${label}: calls file must be EMPTY on validation failure; got: ${r.calls}`);
    assert.ok(r.stderr.length > 0,
      `${label}: stderr must not be empty`);
    assert.ok(r.stderr.includes(expectedVarName),
      `${label}: stderr must contain '${expectedVarName}'. Got: ${r.stderr}`);
  } finally {
    fix.cleanup();
  }
}

test('invalid DEPLOY_MODE: exit 2, empty calls, DEPLOY_MODE in stderr', () => {
  assertValidationRejection('invalid-DEPLOY_MODE', { DEPLOY_MODE: 'purple' }, 'DEPLOY_MODE');
});

test('invalid RELEASE_COLOR: exit 2, empty calls, RELEASE_COLOR in stderr', () => {
  assertValidationRejection('invalid-RELEASE_COLOR', { RELEASE_COLOR: 'red' }, 'RELEASE_COLOR');
});

test('invalid RUN_TERRAFORM: exit 2, empty calls, RUN_TERRAFORM in stderr', () => {
  assertValidationRejection('invalid-RUN_TERRAFORM', { RUN_TERRAFORM: 'yes' }, 'RUN_TERRAFORM');
});

test('invalid RUN_ANSIBLE: exit 2, empty calls, RUN_ANSIBLE in stderr', () => {
  assertValidationRejection('invalid-RUN_ANSIBLE', { RUN_ANSIBLE: '1' }, 'RUN_ANSIBLE');
});

test('invalid RUN_DEPLOY: exit 2, empty calls, RUN_DEPLOY in stderr', () => {
  assertValidationRejection('invalid-RUN_DEPLOY', { RUN_DEPLOY: 'True' }, 'RUN_DEPLOY');
});

test('TF_ENV uppercase letters: exit 2, empty calls, TF_ENV in stderr', () => {
  assertValidationRejection('TF_ENV-uppercase', { TF_ENV: 'Local-Kind' }, 'TF_ENV');
});

test('TF_ENV with forward slash: exit 2, empty calls, TF_ENV in stderr', () => {
  assertValidationRejection('TF_ENV-slash', { TF_ENV: 'env/bad' }, 'TF_ENV');
});

test('TF_ENV path traversal (../escape): exit 2, empty calls, TF_ENV in stderr', () => {
  // ../escape contains '/' and '..' — both illegal under ^[a-z0-9-]+$
  assertValidationRejection('TF_ENV-traversal', { TF_ENV: '../escape' }, 'TF_ENV');
});

test('TF_ENV with spaces: exit 2, empty calls, TF_ENV in stderr', () => {
  assertValidationRejection('TF_ENV-spaces', { TF_ENV: 'my env' }, 'TF_ENV');
});

test('canary+Terraform: exit 2, empty calls, Canary message in stderr', () => {
  const fix = makeFixture();
  try {
    const r = runCi(fix, { DEPLOY_MODE: 'canary', RUN_TERRAFORM: 'true', TF_ENV: 'local-kind' });
    assertSpawnOk(r, 'canary+terraform');
    assert.equal(r.status, 2,  `Expected exit 2. stderr: ${r.stderr}`);
    assert.equal(r.calls.trim(), '', `calls must be empty; got: ${r.calls}`);
    assert.ok(r.stderr.includes('Canary'),
      `stderr must contain 'Canary'. Got: ${r.stderr}`);
  } finally {
    fix.cleanup();
  }
});

// ---------------------------------------------------------------------------
// Kubernetes context forwarding
// ---------------------------------------------------------------------------

test('external TF_ENV: preserves KUBECONFIG/KUBECONTEXT unchanged, no kind call', () => {
  const fix = makeFixture();
  try {
    const r = runCi(fix, {
      TF_ENV:       'staging',             // not local-kind → kind block skipped
      KUBECONFIG:   '/custom/kube/config',
      KUBECONTEXT:  'my-staging-context',
      RUN_DEPLOY:   'true',
      DEPLOY_MODE:  'blue-green',
      RELEASE_COLOR:'blue',
      IMAGE_NAME:   'myapp',
      IMAGE_TAG:    'v5',
    });
    assertSpawnOk(r, 'external-TF_ENV');
    assert.equal(r.status, 0, `stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);
    assert.ok(!calls.find(c => c.tool === 'kind'), 'kind must NOT be called for non-local-kind TF_ENV');
    const bgCall = calls.find(c => c.tool === 'blue-green.sh');
    assert.ok(bgCall, 'blue-green.sh must be called');
    assert.equal(bgCall.KUBECONFIG,  '/custom/kube/config',  'KUBECONFIG preserved verbatim');
    assert.equal(bgCall.KUBECONTEXT, 'my-staging-context',   'KUBECONTEXT preserved verbatim');
  } finally {
    fix.cleanup();
  }
});

test('local-kind target: kind called with exact argv; KUBECONFIG/KUBECONTEXT with spaces intact', () => {
  const fix = makeFixture();
  try {
    // kubeconfig path contains spaces; use forward slashes for bash env var
    const spacedNative  = path.join(fix.resolvedTmp, 'my kube', 'config');
    const spacedForBash = spacedNative.replace(/\\/g, '/');
    fs.mkdirSync(path.dirname(spacedNative), { recursive: true });
    fs.writeFileSync(spacedNative, '# stub');

    const r = runCi(fix, {
      TF_ENV:        'local-kind',
      KUBECONFIG:    spacedForBash,
      KUBECONTEXT:   'kind-my cluster',  // contains a space
      RUN_DEPLOY:    'true',
      DEPLOY_MODE:   'blue-green',
      RELEASE_COLOR: 'blue',
      IMAGE_NAME:    'myapp',
      IMAGE_TAG:     'v6',
      CLUSTER_NAME:  'my-cluster',
    });
    assertSpawnOk(r, 'local-kind-spaces');
    assert.equal(r.status, 0, `stderr: ${r.stderr}`);
    const calls = parseCalls(r.calls);

    const kindCall = calls.find(c => c.tool === 'kind');
    assert.ok(kindCall, 'kind must be called for local-kind');
    assert.deepEqual(kindCall.args,
      ['load', 'docker-image', 'myapp:v6', '--name', 'my-cluster'], 'kind argv');

    const bgCall = calls.find(c => c.tool === 'blue-green.sh');
    assert.ok(bgCall, 'blue-green.sh must be called');
    assert.equal(bgCall.KUBECONFIG,  spacedForBash,      'KUBECONFIG with spaces intact');
    assert.equal(bgCall.KUBECONTEXT, 'kind-my cluster',  'KUBECONTEXT with spaces intact');
  } finally {
    fix.cleanup();
  }
});
