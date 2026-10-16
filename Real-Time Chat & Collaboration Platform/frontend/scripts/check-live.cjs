const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const WebSocket = require('ws');
const base = process.argv[2];
const target = JSON.parse(process.argv[3]);
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
let control;
if (Array.isArray(target)) {
  assert.ok(target.includes('-p') && target[target.indexOf('-p') + 1].startsWith('portfolio-demo-chat-'),
    'Only an isolated demo-check.py stack may be disrupted');
  control = (...args) => execFileSync(target[0], [...target.slice(1), ...args], {timeout:60000, stdio:'pipe'});
} else {
  const kube = target.kubernetes;
  assert.ok(Array.isArray(kube) && kube.includes('--context') && kube.includes('-n'));
  assert.match(kube[kube.indexOf('--context') + 1], /^kind-[a-z0-9-]+$/);
  const namespace = kube[kube.indexOf('-n') + 1];
  assert.match(namespace, /^chat-(demo|functional)-[a-z0-9-]+$/);
  const command = (...args) => execFileSync(kube[0], [...kube.slice(1), ...args], {timeout:70000, stdio:'pipe'}).toString();
  const identity = JSON.parse(command('get', 'namespace', namespace, '-o', 'json')).metadata;
  assert.equal(identity.uid, target.namespaceUid, 'Namespace identity changed');
  assert.equal(identity.labels['app.kubernetes.io/part-of'], 'portfolio-chat');
  assert.equal(identity.labels['portfolio-demo'], 'true');
  assert.equal(JSON.parse(command('get', 'deployment', 'kafka', '-o', 'json')).spec.replicas, 1);
  control = (action, service) => {
    assert.equal(service, 'kafka'); assert.ok(['stop', 'start'].includes(action));
    assert.equal(JSON.parse(command('get', 'namespace', namespace, '-o', 'json')).metadata.uid, target.namespaceUid);
    command('scale', 'deployment/kafka', '--replicas=' + (action === 'stop' ? '0' : '1'));
    if (action === 'start') command('rollout', 'status', 'deployment/kafka', '--timeout=60s');
    else command('wait', '--for=delete', 'pod', '-l', 'app=kafka', '--timeout=60s');
  };
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const clients = [];
async function client() {
  const response = await fetch(base + '/api/csrf', {signal: AbortSignal.timeout(15000)});
  const token = await response.json();
  const cookie = response.headers.getSetCookie().map(x => x.split(';')[0]).join('; ');
  const socket = new WebSocket(base.replace('http:', 'ws:') + '/ws/websocket', ['v12.stomp'],
    {handshakeTimeout:15000, headers: {Cookie: cookie, Origin: base}});
  const frames = [];
  socket.on('message', data => {
    for (const frame of data.toString().split('\0')) if (frame.trim()) frames.push(frame.trimStart());
  });
  const send = (command, headers, body = '') => socket.send(command + '\n' + Object.entries(headers)
    .map(([key, value]) => key + ':' + value).join('\n') + '\n\n' + body + '\0');
  const wait = async match => {
    const end = Date.now() + 30000;
    while (Date.now() < end) {
      const index = frames.findIndex(match);
      if (index >= 0) return frames.splice(index, 1)[0];
      if (frames.some(frame => frame.startsWith('ERROR'))) throw Error('STOMP error received');
      await pause(50);
    }
    throw Error('Expected STOMP frame missing');
  };
  const result = {socket, frames, send, wait, token, cookie}; clients.push(result);
  await new Promise((resolve, reject) => { socket.once('open', resolve); socket.once('error', reject); });
  send('CONNECT', {'accept-version': '1.2', 'heart-beat': '0,0', [token.headerName]: token.token});
  await wait(frame => frame.startsWith('CONNECTED'));
  return result;
}
const payload = frame => JSON.parse(frame.slice(frame.indexOf('\n\n') + 2));
const message = frame => frame.startsWith('MESSAGE');
async function main() {
  const a = await client(), b = await client();
  const response = await fetch(base + '/api/rooms', {method:'POST', signal: AbortSignal.timeout(15000),
    headers:{'Content-Type':'application/json', Cookie:a.cookie, [a.token.headerName]:a.token.token},
    body:JSON.stringify({name:'Protocol test ' + Date.now()})});
  assert.equal(response.status, 200);
  const room = await response.json();
  for (const c of [a, b]) {
    c.send('SUBSCRIBE', {id:'messages', destination:'/topic/rooms/' + room.id});
    c.send('SUBSCRIBE', {id:'presence', destination:'/topic/rooms/' + room.id + '/presence'});
    c.send('SUBSCRIBE', {id:'receipts', destination:'/user/queue/receipts'});
  }
  // Spring's simple broker does not acknowledge subscriptions.
  await pause(300);
  const activity = (c, name, typing = false, leave = false) => c.send('SEND', {
    destination:'/app/rooms/' + room.id + '/presence', 'content-type':'application/json'}, JSON.stringify({sender:name, typing, leave}));
  activity(a, 'Alice'); activity(b, 'Bob');
  for (const c of [a, b]) await c.wait(frame => message(frame) && payload(frame).members?.length === 2);
  activity(b, 'Bob', true);
  await a.wait(frame => message(frame) && payload(frame).members?.some(member => member.name === 'Bob' && member.typingUntil > Date.now()));
  const send = (c, content, requestId) => c.send('SEND', {destination:'/app/rooms/' + room.id + '/send',
    'content-type':'application/json'}, JSON.stringify({sender:'protocol-test', content, requestId}));
  const receipt = (c, id) => c.wait(frame => message(frame) && payload(frame).requestId === id).then(payload);
  const history = async query => {
    const result = await fetch(base + '/api/rooms/' + room.id + '/messages?query=' + encodeURIComponent(query || ''),
      {headers:{Cookie:b.cookie}, signal:AbortSignal.timeout(15000)});
    assert.equal(result.status, 200); return result.json();
  };
  send(a, 'Needle persistent message', 'message-1');
  const first = await receipt(a, 'message-1'); assert.equal(first.accepted, true);
  for (const c of [a, b]) await c.wait(frame => message(frame) && payload(frame).content === 'Needle persistent message');
  send(a, 'Needle persistent message', 'message-1');
  assert.equal((await receipt(a, 'message-1')).messageId, first.messageId);
  assert.equal((await history('NEEDLE')).length, 1);
  assert.equal((await history('does not exist')).length, 0);
  send(a, 'different content', 'message-1'); assert.equal((await receipt(a, 'message-1')).accepted, false);
  control('stop', 'kafka');
  try {
    send(a, 'saved during outage', 'outage-1');
    assert.equal((await receipt(a, 'outage-1')).accepted, true);
    assert.equal((await history('saved during outage')).length, 1);
  } finally { control('start', 'kafka'); }
  await b.wait(frame => message(frame) && payload(frame).content === 'saved during outage');
  activity(b, 'Bob', false, true);
  await a.wait(frame => message(frame) && payload(frame).members?.length === 1 && payload(frame).members[0].name === 'Alice');
  // A fresh session gets an independent demo-mode quota; authenticated mode keys it by principal.
  const c = await client();
  c.send('SUBSCRIBE', {id:'receipts', destination:'/user/queue/receipts'}); await pause(200);
  for (let index = 0; index < 61; index++) {
    const id = 'rate-' + index;
    send(c, 'limited message ' + index, id);
    assert.equal((await receipt(c, id)).accepted, index < 60);
  }
  console.log(JSON.stringify({status:'PASS', two_sessions:true, presence:true, typing:true, search:true,
    deduplication:true, durable_outage_recovery:true, rate_limit:true, explicit_leave:true}));
}
main().catch(error => {console.error(error); process.exitCode = 1;})
  .finally(() => {for (const client of clients) client.socket.close();});
