const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('cancellation resumes polling after a delivered order and stops at compensation', async () => {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { value: id === 'customer' ? 'alice' : '1', textContent: '', append() {} });
    return elements.get(id);
  };
  let status = 'DELIVERED', next = 0;
  const timers = new Map();
  const context = vm.createContext({
    document: { getElementById: element, createElement: () => ({}) },
    crypto: { randomUUID: () => 'request-1' },
    setInterval: callback => { timers.set(++next, callback); return next; },
    clearInterval: id => timers.delete(id),
    fetch: async (url) => {
      let data = [];
      if (url.endsWith('/checkout')) data = { orderId: 'order-1' };
      else if (url.endsWith('/cancel')) { status = 'COMPENSATING'; data = {}; }
      else if (url === '/api/orders/order-1') data = { status };
      return { ok: true, json: async () => data };
    }
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../services/order-service/src/main/resources/static/demo.js'), 'utf8'), context);
  await element('checkout').onclick();
  assert.equal(timers.size, 0, 'terminal checkout must not leave a polling timer');
  await element('cancel').onclick();
  assert.equal(timers.size, 1, 'asynchronous compensation must be followed');
  assert.match(element('order').textContent, /COMPENSATING/);
  status = 'COMPENSATED';
  await [...timers.values()][0]();
  assert.match(element('order').textContent, /COMPENSATED/);
  assert.equal(timers.size, 0);
  assert.equal(element('error').textContent, '');
});
