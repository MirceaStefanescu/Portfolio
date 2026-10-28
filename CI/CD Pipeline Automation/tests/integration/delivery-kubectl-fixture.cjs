'use strict';
// Isolated command recorder. Native mode delegates ONLY --local transformations.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const args = process.argv.slice(2);
const at = key => args.indexOf(key);
const value = key => at(key) < 0 ? undefined : args[at(key) + 1];
const operation = args.find(x => ['get', 'apply', 'create', 'patch', 'set', 'rollout', 'load'].includes(x));
const target = args[at(operation) + 1];
const local = args.includes('--local');
const file = value('-f');
const input = file === '-' ? fs.readFileSync(0, 'utf8') : '';
const fail = (code, message) => { process.stderr.write(message + '\n'); process.exit(code); };
let object;
if (file === '-') object = JSON.parse(input);
else if (file) {
  const snapshots = require('./delivery-manifests.json').manifests;
  const key = path.relative(process.cwd(), path.resolve(file)).replace(/\\/g, '/');
  const snapshot = snapshots[key];
  if (!snapshot) fail(91, `Unknown manifest: ${key}`);
  const digest = crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  if (digest !== snapshot.sha256) fail(92, `Manifest snapshot changed: ${key}`);
  object = structuredClone(snapshot.object);
}
const row = { args, operation, target, local, input, object, context: value('--context'), kubeconfig: process.env.KUBECONFIG };
fs.appendFileSync(process.env.ROUTING_CALLS, JSON.stringify(row) + '\n');
if (operation === 'load') {
  if (process.env.KIND_FAIL === 'yes') fail(31, 'kind load failed');
} else if (operation === 'get') {
  const mode = target === 'configmap' ? process.env.CONFIGMAP_STATE : process.env.SERVICE_STATE;
  if (mode === 'forbidden') fail(23, `Forbidden reading ${target}`);
  if (mode === 'unavailable') fail(24, `ServiceUnavailable reading ${target}`);
  if (mode === 'missing') {
    if (args.some(x => x === '--ignore-not-found' || x === '--ignore-not-found=true')) process.exit(0);
    fail(1, `NotFound ${target}`);
  }
  process.stdout.write(`${target}/${args[at(operation) + 2]}\n`);
} else if (operation === 'rollout') {
  if (process.env.FAIL_ROLLOUT === 'yes') fail(25, 'Readiness failed');
} else if (local) {
  if (operation === 'patch' && process.env.FAIL_LOCAL_PATCH === 'yes') fail(26, 'Local render failed');
  if (operation === 'patch' && object?.kind === process.env.FAIL_LOCAL_PATCH_KIND) {
    fs.writeSync(1, JSON.stringify(object));
    fail(26, 'Local render failed after output');
  }
  if (operation === 'set' && process.env.FAIL_SET_IMAGE === 'yes') {
    fs.writeSync(1, JSON.stringify(object));
    fail(29, 'Image render failed after output');
  }
  if (process.env.LOCAL_KUBECTL) {
    // Never forward get/apply/create/rollout or an unrecognized command to real kubectl.
    if (!['patch', 'set'].includes(operation)) fail(93, 'Unsupported native local operation');
    const native = spawnSync(process.env.LOCAL_KUBECTL, ['--kubeconfig=NUL', ...args.filter((x, i) => x !== '--context' && args[i - 1] !== '--context')], {
      encoding: 'utf8', input, windowsHide: true, timeout: 10000,
    });
    if (native.error) fail(94, String(native.error));
    process.stdout.write(native.stdout); process.stderr.write(native.stderr); process.exit(native.status ?? 95);
  }
  if (operation === 'patch') {
    for (const patch of JSON.parse(value('-p'))) {
      if (patch.op !== 'replace') fail(96, 'Fixture supports replace only');
      const keys = patch.path.split('/').slice(1).map(x => x.replace(/~1/g, '/').replace(/~0/g, '~'));
      let parent = object;
      for (const key of keys.slice(0, -1)) parent = parent[key];
      const leaf = keys.at(-1);
      if (!Object.hasOwn(parent, leaf)) fail(97, `Missing JSON path ${patch.path}`);
      parent[leaf] = patch.value;
    }
  } else if (operation === 'set' && target === 'image') {
    const assignment = args.find(x => x.startsWith('app='));
    object.spec.template.spec.containers.find(x => x.name === 'app').image = assignment.slice(4);
  } else fail(98, 'Unsupported local command');
  process.stdout.write(JSON.stringify(object));
} else if (operation === 'create') {
  if (object?.kind === 'ConfigMap' && process.env.CONFIGMAP_RACE === 'yes') fail(27, 'AlreadyExists configmap');
  if (object?.kind === 'Service' && process.env.SERVICE_RACE === 'yes') fail(28, 'AlreadyExists service');
} else if (!['apply', 'patch'].includes(operation)) fail(90, `Unexpected fixture command: ${args.join(' ')}`);
