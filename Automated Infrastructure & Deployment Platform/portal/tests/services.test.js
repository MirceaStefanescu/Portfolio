const {test, before, after, beforeEach} = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const {once} = require('node:events');
const {setTimeout: delay} = require('node:timers/promises');
process.env.PORTAL_AUTH_MODE='demo';
process.env.LOG_LEVEL='error';
const {config}=require('../src/config');
const {app}=require('../src/server');
const fields=['jenkinsUrl','vaultAddr','prometheusUrl','grafanaUrl'];
const paths=['/login','/v1/sys/health','/-/ready','/api/health'];
let portal,base;
before(async()=>{portal=app.listen(0,'127.0.0.1');await once(portal,'listening');base=`http://127.0.0.1:${portal.address().port}`;});
after(()=>close(portal));
beforeEach(()=>{for(const field of fields)config[field]=null;});
function close(server){server.closeAllConnections();return new Promise(resolve=>server.close(resolve));}
async function fixture(t,handler){
  const server=http.createServer(handler);server.listen(0,'127.0.0.1');await once(server,'listening');
  t.after(()=>close(server));return `http://127.0.0.1:${server.address().port}`;
}
async function poll(predicate,label,ms=1000){
  const end=Date.now()+ms;
  while(!predicate()&&Date.now()<end)await delay(10);
  assert.ok(predicate(),label);
}
async function services(id='fixture-health'){
  const response=await fetch(base+'/api/services',{headers:{'x-request-id':id},signal:AbortSignal.timeout(5000)});
  assert.equal(response.status,200);assert.equal(response.headers.get('x-request-id'),id);
  const data=await response.json();assert.equal(data.requestId,id);
  assert.deepEqual(data.services.map(x=>x.id),['jenkins','vault','prometheus','grafana']);
  return data.services;
}
async function count(){const text=await(await fetch(base+'/api/metrics')).text();return Number(text.match(/endpoint="services"\} (\d+)/)[1]);}

test('services report mixed outcomes independently with exact paths and one request metric',async t=>{
  const seen=[];
  const upstream=await fixture(t,(req,res)=>{seen.push([req.method,req.url]);
    if(req.url==='/login')res.end('ok');
    else if(req.url==='/v1/sys/health'){res.writeHead(503);res.end('sealed');}
    else req.socket.destroy();
  });
  config.jenkinsUrl=config.vaultAddr=config.grafanaUrl=upstream;
  const initial=await count();const result=await services();
  assert.deepEqual(result.map(x=>x.status),['healthy','unhealthy','unconfigured','unreachable']);
  assert.equal(result[0].httpStatus,200);assert.equal(result[1].httpStatus,503);
  assert.ok(!('httpStatus' in result[2])&&!('httpStatus' in result[3]));
  assert.ok(result.every(x=>!('url' in x)&&!('body' in x)));
  assert.deepEqual(seen.sort(),[['GET','/api/health'],['GET','/login'],['GET','/v1/sys/health']]);
  assert.equal(await count(),initial+1);
});

test('services start all probes before any response is released',async t=>{
  const pending=[];
  const upstream=await fixture(t,(req,res)=>pending.push({path:req.url,res}));
  for(const field of fields)config[field]=upstream;
  const request=services();
  try {
    await poll(()=>pending.length===4,'all four requests must reach the barrier before release');
    assert.deepEqual(pending.map(x=>x.path).sort(),[...paths].sort());
  } finally {for(const {res} of pending)res.end('ready');}
  assert.ok((await request).every(x=>x.status==='healthy'));
});

test('services cancel unused open response bodies on repeated healthy and unhealthy probes',async t=>{
  let open=0,received=0,closed=0;
  const upstream=await fixture(t,(req,res)=>{
    open++;received++;res.once('close',()=>{open--;closed++;});
    res.writeHead(req.url==='/v1/sys/health'?503:200,{'Content-Type':'text/plain'});
    res.flushHeaders();res.write('body deliberately never ends');
  });
  for(const field of fields)config[field]=upstream;
  for(let round=0;round<3;round++){
    const result=await services('repeat-'+round);
    assert.deepEqual(result.map(x=>x.status),['healthy','unhealthy','healthy','healthy']);
    await poll(()=>open===0,'every unfinished upstream response must close after status-only inspection');
    assert.equal(received,4*(round+1));assert.equal(closed,received);
  }
});

test('services abort probes without headers and recover on the next request',async t=>{
  let received=0,closed=0,ready=false;
  const upstream=await fixture(t,(req,res)=>{
    received++;res.once('close',()=>closed++);
    if(ready)res.end('ready');
  });
  for(const field of fields)config[field]=upstream;
  const result=await services('timeout');
  assert.equal(received,4);assert.ok(result.every(x=>x.status==='unreachable'));
  await poll(()=>closed===4,'timeout abort must close each pending upstream response');
  ready=true;
  assert.ok((await services('recovery')).every(x=>x.status==='healthy'));
});

test('services handle absent URLs and bodyless 204 responses',async t=>{
  assert.ok((await services('unconfigured')).every(x=>x.status==='unconfigured'));
  const upstream=await fixture(t,(req,res)=>{res.writeHead(204);res.end();});
  for(const field of fields)config[field]=upstream;
  const result=await services('no-body');
  assert.ok(result.every(x=>x.status==='healthy'&&x.httpStatus===204));
});

test('services reflect changed upstream status on each request without stale results',async t=>{
  let status=200,received=0;
  const upstream=await fixture(t,(req,res)=>{received++;res.writeHead(status);res.end('fixture');});
  config.jenkinsUrl=upstream;
  const initial=await count();
  assert.equal((await services('before-change'))[0].status,'healthy');
  status=503;
  const changed=await services('after-change');
  assert.equal(changed[0].status,'unhealthy');assert.equal(changed[0].httpStatus,503);
  assert.equal(received,2);assert.equal(await count(),initial+2);
});
