'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { fixture, stages, exactPlan, exactApply, full, noKind, unix, native } = require('./terraform-fixture.cjs');

test('make terraform-apply checks fresh plan before kind and applies only saved bytes', t => {
  const f = fixture(t), r = f.run('make');
  stages(r, full); exactPlan(f, r); exactApply(f, r);
  assert.deepEqual(r.rows[4].args, ['load', 'docker-image', 'cicd-demo:local', '--name', 'cicd-demo']);
  assert.equal(r.rows[1].context, 'kind-cicd-demo');
  assert.equal(native(r.rows[1].config).toLowerCase(), path.join(f.project, '.kube/config').toLowerCase());
});
test('make policy rejection prevents kind and apply', t => {
  const f = fixture(t), r = f.run('make', { FAIL_STEP: 'policy' });
  stages(r, full.slice(0, 4), 2);
});
test('make LOAD_KIND_IMAGE=false suppresses load without bypassing policy', t => {
  const f = fixture(t), r = f.run('make', {}, 'plan-apply', ['LOAD_KIND_IMAGE=false']);
  stages(r, noKind); exactApply(f, r);
});
test('make preserves full registry port/digest and chosen cluster', t => {
  const f = fixture(t), image = `registry.example:5000/team/demo@sha256:${'a'.repeat(64)}`;
  const r = f.run('make', {}, 'plan-apply', [`IMAGE=${image}`, 'CLUSTER_NAME=demo-extra']);
  stages(r, full); exactPlan(f, r, { image });
  assert.deepEqual(r.rows[4].args, ['load', 'docker-image', image, '--name', 'demo-extra']);
  assert.equal(r.rows[1].context, 'kind-demo-extra');
});
test('make external environment preserves explicit context and never kind-loads', t => {
  const f = fixture(t), config = unix(path.join(f.project, 'private kube config'));
  const r = f.run('make', { TF_VAR_kubeconfig: config, TF_VAR_kube_context: 'external-context' }, 'plan-apply', ['TF_ENV=staging', 'LOAD_KIND_IMAGE=true']);
  stages(r, noKind); exactPlan(f, r, { env: 'staging' }); exactApply(f, r, 'staging');
  assert.equal(r.rows[1].config, config); assert.equal(r.rows[1].context, 'external-context');
});
for (const [key, value] of [['TF_ENV', '../escape'], ['DEPLOY_MODE', 'canary'], ['RELEASE_COLOR', 'red'], ['LOAD_KIND_IMAGE', 'yes']]) {
  test(`make rejects ${key} before any external invocation`, t => {
    const f = fixture(t), r = f.run('make', {}, 'plan-apply', [`${key}=${value}`]);
    stages(r, [], 2); assert.ok(r.stderr.includes(key), r.stderr);
  });
}
for (const override of [false, true]) {
  test(`make ci preserves its built image and single kind-load (outer override=${override})`, t => {
    const f = fixture(t);
    const vars = { RUN_TERRAFORM: 'true', IMAGE_NAME: 'registry:5000/ci/demo', IMAGE_TAG: 'build-42' };
    if (override) { vars.IMAGE = 'outer-image'; vars.LOAD_KIND_IMAGE = 'true'; }
    const r = f.run('make', vars, 'ci');
    stages(r, ['npm', 'npm', 'npm', 'docker', 'kind', ...noKind]);
    assert.deepEqual(r.rows.slice(0, 4).map(row => row.args), [
      ['ci'], ['run', 'lint'], ['test'], ['build', '-t', 'registry:5000/ci/demo:build-42', '.'],
    ]);
    assert.deepEqual(r.rows[4].args, ['load', 'docker-image', 'registry:5000/ci/demo:build-42', '--name', 'cicd-demo']);
    exactPlan(f, r, { image: 'registry:5000/ci/demo:build-42', build: 'build-42' });
    exactApply(f, r);
  });
}
