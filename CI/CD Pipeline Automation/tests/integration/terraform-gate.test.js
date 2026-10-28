'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { fixture, stages, exactPlan, exactApply, full, noKind, unix } = require('./terraform-fixture.cjs');

test('direct plan defaults and explicit-empty values retain prior image metadata', t => {
  const f = fixture(t), r = f.run('gate', { TF_ENV: '', DEPLOY_MODE: '', RELEASE_COLOR: '', LOAD_KIND_IMAGE: '', IMAGE: '', IMAGE_NAME: '', IMAGE_TAG: '' }, '');
  stages(r, full.slice(0, 4)); exactPlan(f, r);
});
test('plan with kind requested still has no kind or apply effects', t => {
  const f = fixture(t), r = f.run('gate', { LOAD_KIND_IMAGE: 'true' }, 'plan');
  stages(r, full.slice(0, 4));
});
test('direct plan-apply defaults do not repeat CI kind-load', t => {
  const f = fixture(t), r = f.run();
  stages(r, noKind); exactPlan(f, r); exactApply(f, r);
});
test('gate fallback image, strategy, color, build, environment and Git metadata are exact', t => {
  const f = fixture(t), r = f.run('gate', { IMAGE_NAME: 'registry:5000/team/app', IMAGE_TAG: 'build-7', DEPLOY_MODE: 'rolling', RELEASE_COLOR: 'green', ENVIRONMENT: 'staging', GIT_SHA: 'abcdef' });
  stages(r, noKind);
  exactPlan(f, r, { image: 'registry:5000/team/app:build-7', mode: 'rolling', color: 'green', build: 'build-7', sha: 'abcdef', environment: 'staging' });
});
test('gate full IMAGE takes precedence without shell interpolation', t => {
  const f = fixture(t), image = 'registry:5000/team/app:literal$HOME;value';
  const r = f.run('gate', { IMAGE: image, IMAGE_NAME: 'ignored', IMAGE_TAG: 'build', LOAD_KIND_IMAGE: 'true' });
  stages(r, full); exactPlan(f, r, { image, build: 'build' });
  assert.deepEqual(r.rows[4].args, ['load', 'docker-image', image, '--name', 'cicd-demo']);
});
test('apply refreshes stale JSON and uses existing plan without replanning', t => {
  const f = fixture(t);
  fs.writeFileSync(f.plan(), 'PLAN-BYTES-RECORDED');
  fs.writeFileSync(f.json(), '{"fixture":"STALE"}');
  const r = f.run('gate', { IMAGE: 'new-image-must-not-replan' }, 'apply');
  stages(r, ['tf-show', 'policy', 'tf-apply']); exactApply(f, r);
  assert.equal(JSON.parse(fs.readFileSync(f.json())).fixture, 'FRESH');
});
test('apply rejects a missing plan before policy or apply', t => {
  const f = fixture(t), r = f.run('gate', {}, 'apply');
  stages(r, ['tf-show'], 42);
});
test('apply cannot kind-load a different image from current variables', t => {
  const f = fixture(t), r = f.run('gate', { LOAD_KIND_IMAGE: 'true' }, 'apply');
  stages(r, [], 2); assert.ok(r.stderr.includes('LOAD_KIND_IMAGE'));
});
for (const step of full) {
  test(`gate ${step} failure stops exactly at that stage`, t => {
    const f = fixture(t);
    fs.writeFileSync(f.json(), '{"fixture":"STALE"}');
    const r = f.run('gate', { LOAD_KIND_IMAGE: 'true', FAIL_STEP: step });
    stages(r, full.slice(0, full.indexOf(step) + 1), 41);
  });
}
for (const [key, value] of [['TF_ENV', '../escape'], ['TF_ENV', 'Stage'], ['DEPLOY_MODE', 'canary'], ['DEPLOY_MODE', 'typo'], ['RELEASE_COLOR', 'red'], ['LOAD_KIND_IMAGE', 'TRUE']]) {
  test(`gate rejects ${key}=${value} before external work`, t => {
    const f = fixture(t), r = f.run('gate', { [key]: value });
    stages(r, [], 2); assert.ok(r.stderr.includes(key), r.stderr);
  });
}
test('gate rejects unknown operation before external work', t => {
  const f = fixture(t), r = f.run('gate', {}, 'destroy');
  stages(r, [], 2); assert.ok(r.stderr.includes('mode'));
});
test('gate preserves explicit Terraform context over ordinary kube variables', t => {
  const f = fixture(t), config = unix(path.join(f.project, 'chosen config'));
  const r = f.run('gate', { TF_VAR_kubeconfig: config, TF_VAR_kube_context: 'chosen', KUBECONFIG: 'ignored', KUBECONTEXT: 'ignored', CLUSTER_NAME: 'ignored' });
  stages(r, noKind);
  for (const row of r.rows) { assert.equal(row.config, config); assert.equal(row.context, 'chosen'); }
});
