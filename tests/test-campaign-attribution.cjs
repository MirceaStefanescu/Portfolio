/* Campaign navigation tests run without browser packages, network or external services. */
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const root = resolve(__dirname, '..');
const script = readFileSync(resolve(root, 'docs/campaign-attribution.js'), 'utf8');
const site = 'https://mirceastefanescu.github.io/Portfolio/';
const enquiry = 'https://stefanescumircea1990.wordpress.com/software-services/?utm_source=github&utm_medium=portfolio&utm_campaign=it_services_202611#project-enquiry';

function visit(url, destinations) {
  const anchors = destinations.map(href => {
    const attributes = { href };
    return {
      attributes,
      getAttribute(name) { return attributes[name] ?? null; },
      setAttribute(name, value) { attributes[name] = value; }
    };
  });
  const forbid = () => { throw new Error('Unexpected browser side effect'); };
  const window = { location: { href: url }, fetch: forbid };
  Object.defineProperties(window, {
    localStorage: { get: forbid }, sessionStorage: { get: forbid }
  });
  const document = { querySelectorAll(selector) {
    assert.equal(selector, 'a[href]');
    return anchors;
  } };
  Object.defineProperty(document, 'cookie', { get: forbid, set: forbid });
  vm.runInNewContext(script, { window, document, URL, URLSearchParams, fetch: forbid,
    XMLHttpRequest: forbid, navigator: { sendBeacon: forbid }, console: { log: forbid } });
  return anchors;
}

test('preserves a valid campaign from the homepage through each diagnostic and back', () => {
  const query = '?utm_source=linkedin&utm_medium=social&utm_campaign=it_services_202611&utm_content=post-01&utm_term=spring-boot';
  for (const page of ['api-integration-diagnostic.html', 'cicd-pipeline-diagnostic.html', 'ai-regression-diagnostic.html']) {
    const link = visit(site + query, [page])[0].attributes;
    const diagnostic = new URL(link.href);
    assert.equal(diagnostic.origin, new URL(site).origin);
    assert.equal(diagnostic.pathname, '/Portfolio/' + page);
    assert.equal(diagnostic.search, query);
    const [cta, back] = visit(link.href, [enquiry, 'index.html#services']);
    assert.equal(new URL(cta.attributes.href).search, query);
    assert.equal(new URL(cta.attributes.href).hash, '#project-enquiry');
    assert.equal(new URL(back.attributes.href).search, query);
    assert.equal(new URL(back.attributes.href).hash, '#services');
    assert.equal(cta.attributes.referrerpolicy, 'origin');
  }
});

test('partial valid labels preserve authored fallback medium and campaign', () => {
  const output = new URL(visit(site + '?utm_source=reddit', [enquiry])[0].attributes.href);
  assert.equal(output.searchParams.get('utm_source'), 'reddit');
  assert.equal(output.searchParams.get('utm_medium'), 'portfolio');
  assert.equal(output.searchParams.get('utm_campaign'), 'it_services_202611');
});

test('preserves the Facebook and Threads campaign labels already used in Marketing Content', () => {
  for (const source of ['facebook', 'threads']) {
    for (const content of ['order_retry_checklist', 'order_retry']) {
      const query = '?utm_source=' + source + '&utm_medium=organic_social&utm_campaign=it_services_202611&utm_content=' + content;
      const diagnostic = visit(site + query, ['api-integration-diagnostic.html'])[0].attributes.href;
      const destination = new URL(visit(diagnostic, [enquiry])[0].attributes.href);
      assert.equal(destination.search, query);
      assert.equal(destination.hash, '#project-enquiry');
    }
  }
});

test('direct visits and campaigns without a source retain every authored link', () => {
  for (const query of ['', '?utm_campaign=it_services_202611', '?unknown=linkedin']) {
    const hrefs = ['api-integration-diagnostic.html', enquiry, '#contact'];
    assert.deepEqual(visit(site + query, hrefs).map(a => a.attributes.href), hrefs);
  }
});

test('duplicates including identical and percent-encoded keys fall back atomically', () => {
  for (const query of [
    '?utm_source=linkedin&utm_source=reddit',
    '?utm_source=linkedin&utm_source=linkedin',
    '?utm_source=linkedin&%75tm_source=reddit',
    '?utm_source=linkedin&utm_medium=social&utm_medium=email',
    '?utm_source=linkedin&utm_campaign=it_services_202611&utm_campaign=ai_diagnostic_202611'
  ]) {
    assert.equal(visit(site + query, [enquiry])[0].attributes.href, enquiry);
  }
});

test('rejects unregistered, empty, oversized, injection and personal-data values', () => {
  for (const invalid of [
    'utm_source=', 'utm_source=Jane_Doe', 'utm_source=person%40example.com',
    'utm_source=peopleperhour', 'utm_source=whatsapp',
    'utm_source=%2B40722123456', 'utm_source=linkedin%0A',
    'utm_source=' + 'x'.repeat(65), 'utm_source=%3Cscript%3E',
    'utm_source=https%3A%2F%2Fexample.com', 'utm_source=%2523linkedin',
    'utm_source=linkedin&utm_campaign=it_services_202613',
    'utm_source=linkedin&utm_campaign=Jane_Doe',
    'utm_source=linkedin&utm_content=person%40example.com',
    'utm_source=linkedin&utm_term=custom-search-text',
    'utm_source=linkedin&utm_medium=social+email'
  ]) {
    assert.equal(visit(site + '?' + invalid, [enquiry])[0].attributes.href, enquiry, invalid);
  }
});

test('supports reviewed global channels and drops unknown incoming parameters', () => {
  for (const source of ['baidu', 'wechat', 'weibo', 'yandex', 'vk', 'naver', 'line', 'workana']) {
    const query = '?utm_source=' + source + '&utm_medium=social&email=private%40example.com&redirect=https%3A%2F%2Fexample.com&utm_id=private';
    const out = new URL(visit(site + query, [enquiry])[0].attributes.href);
    assert.equal(out.searchParams.get('utm_source'), source);
    assert.deepEqual([...out.searchParams.keys()], ['utm_source', 'utm_medium', 'utm_campaign']);
  }
});

test('does not rewrite unrelated destinations, fragment links or lookalike hosts', () => {
  const destinations = [
    '#services', 'mailto:hello@example.com', 'javascript:alert(1)',
    'https://github.com/MirceaStefanescu/Portfolio',
    'https://example.com/api-integration-diagnostic.html',
    'https://stefanescumircea1990.wordpress.com.example.com/software-services/#project-enquiry',
    'https://stefanescumircea1990.wordpress.com@evil.example/software-services/#project-enquiry',
    'https://user@stefanescumircea1990.wordpress.com/software-services/#project-enquiry',
    'http://stefanescumircea1990.wordpress.com/software-services/#project-enquiry',
    'https://stefanescumircea1990.wordpress.com/software-services/#other',
    'https://stefanescumircea1990.wordpress.com/another-page/#project-enquiry',
    'https://mirceastefanescu.github.io/elsewhere/index.html',
    'https://mirceastefanescu.github.io/Portfolio/assets/web-app.png',
    'https://[invalid'
  ];
  assert.deepEqual(visit(site + '?utm_source=linkedin', destinations).map(a => a.attributes.href), destinations);
});

test('rewrites every real enquiry CTA and diagnostic link across the four actual pages', () => {
  for (const page of ['index.html', 'api-integration-diagnostic.html', 'cicd-pipeline-diagnostic.html', 'ai-regression-diagnostic.html']) {
    const html = readFileSync(resolve(root, 'docs', page), 'utf8');
    assert.equal((html.match(/<script src="campaign-attribution\.js" defer><\/script>/g) || []).length, 1);
    const hrefs = [...html.matchAll(/<a\b[^>]*\bhref="([^"]+)"/g)].map(m => m[1].replaceAll('&amp;', '&'));
    assert.ok(hrefs.some(href => href.startsWith(enquiry.split('?')[0])), page);
    const rewritten = visit(site + page + '?utm_source=linkedin&utm_medium=social', hrefs);
    hrefs.forEach((href, i) => {
      if (href === enquiry || /^(api-integration|cicd-pipeline|ai-regression)-diagnostic\.html$/.test(href)) {
        assert.equal(new URL(rewritten[i].attributes.href).searchParams.get('utm_source'), 'linkedin', page);
      }
    });
    // The existing price, assessment scope and delivery condition remain in all pages.
    assert.match(html, /EUR 200/);
    assert.match(html, /five work hours/);
    assert.match(html, /seven calendar days/);
  }
});

test('repeated execution is idempotent and does not accumulate query duplicates', () => {
  const input = site + '?utm_source=linkedin&utm_medium=social&utm_content=api';
  const once = visit(input, [enquiry])[0].attributes.href;
  const twice = visit(input, [once])[0].attributes.href;
  assert.equal(twice, once);
  for (const key of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content']) {
    assert.equal(new URL(twice).searchParams.getAll(key).length, 1);
  }
});
