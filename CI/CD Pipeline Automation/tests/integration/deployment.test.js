const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const SOURCE = process.env.CICD_DELIVERY_SOURCE || path.resolve(__dirname, '../..');
const BASH = process.env.BASH_EXECUTABLE || '/bin/bash';
const unix = p => p.replace(/\\/g, '/');
const bashPaths = process.platform === 'win32'
  ? [path.dirname(BASH), path.resolve(path.dirname(BASH), '../usr/bin')]
  : ['/usr/bin', '/bin'];

function exercise(script, failure, color = 'green', overrides = {}) {
  const parent = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(parent, 'deployment lookup '));
  const resolved = fs.realpathSync(root);
  const project = path.join(root, 'project with spaces');
  const bin = path.join(root, 'bin');
  const calls = path.join(root, 'calls.jsonl');
  fs.mkdirSync(path.join(project, 'scripts'), { recursive: true });
  fs.mkdirSync(bin); fs.writeFileSync(calls, '');
  for (const name of ['blue-green.sh', 'rolling.sh']) {
    fs.copyFileSync(path.join(SOURCE, 'scripts', name), path.join(project, 'scripts', name));
  }
  const common = path.join(SOURCE, 'scripts/deployment-common.sh');
  if (fs.existsSync(common)) fs.copyFileSync(common, path.join(project, 'scripts/deployment-common.sh'));
  fs.cpSync(path.join(SOURCE, 'k8s'), path.join(project, 'k8s'), { recursive: true });
  fs.writeFileSync(path.join(bin, 'kubectl'), '#!/usr/bin/env bash\nexec "$FIXTURE_NODE" "$FIXTURE_PROGRAM" "$@"\n', { mode: 0o755 });
  if (overrides.KIND_PRESENT === 'yes') {
    fs.writeFileSync(path.join(bin, 'kind'), '#!/usr/bin/env bash\nexec "$FIXTURE_NODE" "$FIXTURE_PROGRAM" "$@"\n', { mode: 0o755 });
  }
  const env = {
    PATH: [bin, ...bashPaths].join(path.delimiter), HOME: unix(root),
    TMP: os.tmpdir(), TEMP: os.tmpdir(), TMPDIR: unix(os.tmpdir()),
    FIXTURE_NODE: unix(process.execPath), FIXTURE_PROGRAM: unix(path.join(__dirname, 'delivery-kubectl-fixture.cjs')),
    ROUTING_CALLS: calls, CONFIGMAP_STATE: 'present', SERVICE_STATE: 'present',
    FAIL_ROLLOUT: failure ? 'yes' : 'no', IMAGE: 'fixture:checked', LOAD_KIND_IMAGE: 'false',
    TF_ENV: 'local-kind', KUBECONFIG: unix(path.join(root, 'fixture config')), KUBECONTEXT: 'fixture-only',
    LC_ALL: 'C', MSYS2_ARG_CONV_EXCL: '*',
    LOCAL_KUBECTL: process.env.CICD_LOCAL_KUBECTL || '',
  };
  for (const key of ['SYSTEMROOT', 'SystemRoot', 'COMSPEC', 'ComSpec']) {
    if (process.env[key]) env[key] = process.env[key];
  }
  try {
    const result = spawnSync(BASH, ['--noprofile', '--norc', unix(path.join(project, 'scripts', script)), color], {
      encoding: 'utf8', timeout: 15000, windowsHide: true, env: { ...env, ...overrides },
    });
    assert.ifError(result.error);
    assert.equal(result.signal, null, result.stderr);
    return { ...result, rows: fs.readFileSync(calls, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)) };
  } finally {
    assert.equal(fs.lstatSync(root).isSymbolicLink(), false);
    assert.equal(fs.realpathSync(root), resolved);
    const relative = path.relative(parent, resolved);
    assert.ok(relative && !path.isAbsolute(relative) && !relative.split(path.sep).includes('..'));
    fs.rmSync(resolved, { recursive: true });
  }
}
function isFile(row, name) { return row.args.includes('-f') && row.args.some(x => x.endsWith('/' + name)); }
function serviceWrite(row) {
  return ['apply', 'create', 'patch'].includes(row.operation) && !row.args.includes('--local') &&
    (row.target === 'service' || isFile(row, 'service.yaml') || (row.input && JSON.parse(row.input).kind === 'Service'));
}
function configWrite(row) { return !row.local && ['apply', 'create'].includes(row.operation) && row.object?.kind === 'ConfigMap'; }
function successful(result) { assert.equal(result.status, 0, result.stdout + result.stderr); }

describe('deployment traffic safety', () => {
  for (const script of ['blue-green.sh', 'rolling.sh']) {
    it(`${script} leaves the Service unchanged when rollout fails`, () => {
      const result = exercise(script, true);
      assert.equal(result.status, 25, result.stderr);
      assert.ok(result.rows.some(r => r.operation === 'rollout'));
      assert.equal(result.rows.some(serviceWrite), false);
    });
    it(`${script} switches only after readiness and replaces incompatible selectors`, () => {
      const result = exercise(script, false); successful(result);
      const readiness = result.rows.findIndex(r => r.operation === 'rollout');
      assert.ok(readiness >= 0);
      assert.ok(result.rows.findIndex(serviceWrite) > readiness);
      const patch = result.rows.find(r => r.operation === 'patch' && r.target === 'service');
      assert.ok(patch.args.includes('--type=json'));
      assert.equal(JSON.parse(patch.args[patch.args.indexOf('-p') + 1])[0].path, '/spec/selector');
    });
    it(`${script} preserves an external target's current context`, () => {
      const result = exercise(script, false, 'green', { TF_ENV: 'aws-eks', KUBECONTEXT: '' }); successful(result);
      assert.equal(result.rows.some(r => r.args.includes('--context')), false);
      assert.ok(result.rows.some(r => r.operation === 'rollout'));
    });
  }
  it('rejects an unknown color before any Kubernetes mutation', () => {
    const result = exercise('blue-green.sh', false, 'invalid');
    assert.notEqual(result.status, 0); assert.deepEqual(result.rows, []);
  });
  for (const script of ['blue-green.sh', 'rolling.sh']) {
    for (const [mode, code] of [['forbidden', 23], ['unavailable', 24]]) {
      it(`${script} stops after a ${mode} ConfigMap read instead of resetting configuration`, () => {
        const result = exercise(script, false, 'green', { CONFIGMAP_STATE: mode });
        assert.equal(result.status, code, result.stderr);
        assert.match(result.stderr, /Forbidden|ServiceUnavailable/);
        assert.equal(result.rows.at(-1).operation, 'get');
        assert.equal(result.rows.at(-1).target, 'configmap');
        assert.equal(result.rows.some(configWrite), false);
        assert.equal(result.rows.some(serviceWrite), false);
      });
    }
    it(`${script} creates a genuinely missing ConfigMap and continues`, () => {
      const result = exercise(script, false, 'green', { CONFIGMAP_STATE: 'missing' }); successful(result);
      const writes = result.rows.filter(configWrite);
      assert.equal(writes.length, 1); assert.equal(writes[0].operation, 'create');
      assert.ok(result.rows.findIndex(configWrite) > result.rows.findIndex(r => r.operation === 'get'));
    });
    it(`${script} preserves existing ConfigMap data`, () => {
      const result = exercise(script, false); successful(result);
      assert.equal(result.rows.some(configWrite), false);
      const patches = result.rows.filter(r => r.operation === 'patch' && r.target === 'configmap');
      assert.equal(patches.length, 1);
      assert.deepEqual(Object.keys(JSON.parse(patches[0].args[patches[0].args.indexOf('-p') + 1]).data), ['DEPLOY_MODE']);
    });
    it(`${script} does not overwrite a concurrent ConfigMap creation`, () => {
      const result = exercise(script, false, 'green', { CONFIGMAP_STATE: 'missing', CONFIGMAP_RACE: 'yes' });
      assert.equal(result.status, 27, result.stderr);
      assert.equal(result.rows.at(-1).operation, 'create');
      assert.equal(result.rows.filter(configWrite).length, 1);
      assert.equal(result.rows.some(serviceWrite), false);
    });
  }
  for (const [mode, code] of [['forbidden', 23], ['unavailable', 24]]) {
    it(`blue-green stops after a ${mode} Service read without switching traffic`, () => {
      const result = exercise('blue-green.sh', false, 'green', { SERVICE_STATE: mode });
      assert.equal(result.status, code, result.stderr);
      assert.equal(result.rows.at(-1).target, 'service');
      assert.equal(result.rows.some(serviceWrite), false);
    });
  }
  for (const color of ['blue', 'green']) {
    it(`first blue-green Service selects ready ${color} from its initial creation`, () => {
      const result = exercise('blue-green.sh', false, color, { SERVICE_STATE: 'missing' }); successful(result);
      const writes = result.rows.filter(serviceWrite);
      assert.ok(writes.length >= 1); assert.equal(writes[0].operation, 'create');
      assert.deepEqual(JSON.parse(writes[0].input).spec.selector, { app: 'cicd-demo', color });
      assert.ok(result.rows.findIndex(serviceWrite) > result.rows.findIndex(r => r.operation === 'rollout'));
    });
  }
  it('blue-green preserves a concurrently created Service', () => {
    const result = exercise('blue-green.sh', false, 'green', { SERVICE_STATE: 'missing', SERVICE_RACE: 'yes' });
    assert.equal(result.status, 28, result.stderr);
    assert.equal(result.rows.filter(serviceWrite).length, 1);
    assert.equal(result.rows.at(-1).operation, 'create');
  });
  it('blue-green does not create a Service after failed local rendering', () => {
    const result = exercise('blue-green.sh', false, 'green', { SERVICE_STATE: 'missing', FAIL_LOCAL_PATCH: 'yes' });
    assert.notEqual(result.status, 0);
    assert.equal(result.rows.some(r => r.operation === 'create'), false);
  });
});

function remoteMutation(row) { return !row.local && ['apply', 'create', 'patch'].includes(row.operation); }
function checkIdentity(result, app, namespace, color, script) {
  successful(result);
  const writes = result.rows.filter(remoteMutation);
  const objects = writes.map(r => r.object).filter(Boolean);
  assert.deepEqual(objects.map(x => x.kind).sort(), ['ConfigMap', 'Deployment', 'Namespace', 'Service'].sort());
  const ns = objects.find(x => x.kind === 'Namespace');
  assert.equal(ns.metadata.name, namespace);
  for (const object of objects.filter(x => x.kind !== 'Namespace')) assert.equal(object.metadata.namespace, namespace);
  const cm = objects.find(x => x.kind === 'ConfigMap');
  assert.equal(cm.metadata.name, `${app}-env`);
  const dep = objects.find(x => x.kind === 'Deployment');
  const suffix = script === 'rolling.sh' ? 'rolling' : color;
  const selector = script === 'rolling.sh' ? { app, track: 'stable' } : { app, color };
  assert.equal(dep.metadata.name, `${app}-${suffix}`);
  assert.equal(dep.metadata.labels.app, app);
  assert.deepEqual(dep.spec.selector.matchLabels, selector);
  assert.deepEqual(dep.spec.template.metadata.labels, selector);
  const container = dep.spec.template.spec.containers.find(x => x.name === 'app');
  assert.equal(container.envFrom[0].configMapRef.name, cm.metadata.name);
  assert.equal(container.image, 'fixture:checked');
  assert.equal(container.readinessProbe.httpGet.path, '/health');
  assert.equal(container.livenessProbe.httpGet.port, 8080);
  assert.equal(dep.spec.replicas, 2);
  const service = objects.find(x => x.kind === 'Service');
  assert.equal(service.metadata.name, app);
  assert.deepEqual(service.spec.selector, selector);
  assert.equal(service.spec.ports[0].port, 80);
  const rollout = result.rows.find(x => x.operation === 'rollout');
  assert.ok(rollout.args.includes(`deployment/${dep.metadata.name}`));
  for (const row of result.rows.filter(x => ['get', 'rollout'].includes(x.operation) || (!x.local && x.operation === 'patch'))) {
    assert.equal(row.args[row.args.indexOf('-n') + 1], namespace);
    if (row.target === 'configmap') assert.ok(row.args.includes(cm.metadata.name));
    if (row.target === 'service') assert.ok(row.args.includes(app));
  }
  assert.ok(result.rows.findIndex(serviceWrite) > result.rows.findIndex(x => x.operation === 'rollout'));
}

describe('deployment identity and preflight', () => {
  for (const script of ['blue-green.sh', 'rolling.sh']) {
    it(`${script} uses one custom identity across all rendered resources and commands`, () => {
      const result = exercise(script, false, 'green', { APP_NAME: 'billing-api', NAMESPACE: 'audit-qa', CONFIGMAP_STATE: 'missing', SERVICE_STATE: 'missing' });
      checkIdentity(result, 'billing-api', 'audit-qa', 'green', script);
    });
    it(`${script} supports names at the 63-character label limit`, () => {
      const app = 'a'.repeat(63), namespace = 'n'.repeat(63);
      checkIdentity(exercise(script, false, 'green', { APP_NAME: app, NAMESPACE: namespace, CONFIGMAP_STATE: 'missing', SERVICE_STATE: 'missing' }), app, namespace, 'green', script);
    });
    it(`${script} rejects malformed resource identities before external mutations`, () => {
      for (const invalid of [{ APP_NAME: 'invalid"name' }, { APP_NAME: 'A'.repeat(64) }, { NAMESPACE: 'invalid/name' }, { NAMESPACE: 'n'.repeat(64) }]) {
        const result = exercise(script, false, 'green', invalid);
        assert.notEqual(result.status, 0);
        assert.equal(result.rows.some(remoteMutation), false);
      }
    });
    it(`${script} fails before Kubernetes writes when kind loading is requested but kind is absent`, () => {
      const result = exercise(script, false, 'green', { LOAD_KIND_IMAGE: 'true' });
      assert.notEqual(result.status, 0); assert.match(result.stderr + result.stdout, /kind/i);
      assert.equal(result.rows.some(remoteMutation), false);
    });
    it(`${script} stops on a failed kind image load`, () => {
      const result = exercise(script, false, 'green', { LOAD_KIND_IMAGE: 'true', KIND_PRESENT: 'yes', KIND_FAIL: 'yes' });
      assert.equal(result.status, 31); assert.equal(result.rows.filter(r => r.operation === 'load').length, 1);
      assert.equal(result.rows.some(remoteMutation), false);
    });
    it(`${script} loads exactly the requested image into the chosen kind cluster before deployment`, () => {
      const result = exercise(script, false, 'green', { LOAD_KIND_IMAGE: 'true', KIND_PRESENT: 'yes', CLUSTER_NAME: 'audit-kind' });
      successful(result);
      const loads = result.rows.filter(r => r.operation === 'load'); assert.equal(loads.length, 1);
      assert.deepEqual(loads[0].args, ['load', 'docker-image', 'fixture:checked', '--name', 'audit-kind']);
      assert.ok(result.rows.indexOf(loads[0]) < result.rows.findIndex(remoteMutation));
    });
    it(`${script} does not require kind for an external Kubernetes environment`, () => {
      const result = exercise(script, false, 'green', { LOAD_KIND_IMAGE: 'true', TF_ENV: 'aws-eks', KUBECONTEXT: '' });
      successful(result); assert.equal(result.rows.some(r => r.operation === 'load'), false);
    });
    it(`${script} rejects unknown LOAD_KIND_IMAGE values before mutation`, () => {
      const result = exercise(script, false, 'green', { LOAD_KIND_IMAGE: 'tru' });
      assert.notEqual(result.status, 0); assert.equal(result.rows.some(remoteMutation), false);
    });
    it(`${script} completes local rendering before any Kubernetes mutation`, () => {
      const result = exercise(script, false, 'green', { FAIL_LOCAL_PATCH: 'yes', SERVICE_STATE: 'missing' });
      assert.equal(result.status, 26); assert.equal(result.rows.some(remoteMutation), false);
    });
    it(`${script} never applies partial output from a failed image transformation`, () => {
      const result = exercise(script, false, 'green', { FAIL_SET_IMAGE: 'yes' });
      assert.equal(result.status, 29); assert.equal(result.rows.some(remoteMutation), false);
    });
    it(`${script} preserves a nested deployment render failure even after partial output`, () => {
      const result = exercise(script, false, 'green', { FAIL_LOCAL_PATCH_KIND: 'Deployment' });
      assert.equal(result.status, 26); assert.equal(result.rows.some(remoteMutation), false);
    });
  }
  it('blue identity is preserved independently of the green template', () => {
    checkIdentity(exercise('blue-green.sh', false, 'blue', { APP_NAME: 'billing-api', NAMESPACE: 'audit-qa', CONFIGMAP_STATE: 'missing', SERVICE_STATE: 'missing' }), 'billing-api', 'audit-qa', 'blue', 'blue-green.sh');
  });
});
