const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const {once} = require('node:events');
const {normalizeInput} = require('../src/validation');
process.env.PORTAL_AUTH_MODE = 'demo';
process.env.LOG_LEVEL = 'error';
const {app} = require('../src/server');
const valid = {appName:'orders', environment:'dev'};
let server, base;
before(async () => {
  server=app.listen(0,'127.0.0.1'); await once(server,'listening');
  base='http://127.0.0.1:'+server.address().port;
});
after(() => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); }));
const post = (endpoint, payload) => fetch(base+endpoint, {method:'POST',
  headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
const counters = async () => (await (await fetch(base+'/api/metrics')).text());

test('name and provider fields reject JSON non-string values without coercion', () => {
  for(const field of ['appName','environment','provider']) {
    for(const value of [null,true,false,12,[],['orders'],{}, {toString:null}]) {
      assert.equal(normalizeInput({...valid,[field]:value}).valid,false,field+':'+JSON.stringify(value));
    }
  }
});
test('count rejects null boolean array object and blank values', () => {
  for(const appCount of [null,true,false,[],[3],{}, {valueOf:null,toString:null},'', '   ']) {
    assert.equal(normalizeInput({...valid,appCount}).valid,false,JSON.stringify(appCount));
  }
});
test('malformed objects cannot trigger custom conversion', () => {
  const hostile={toString(){throw new Error('conversion must not run');},valueOf(){throw new Error('conversion must not run');}};
  for(const field of ['appName','environment','provider','appCount']) {
    assert.equal(normalizeInput({...valid,[field]:hostile}).valid,false);
  }
});
test('existing defaults normalization and integer clamping remain compatible', () => {
  assert.deepEqual(normalizeInput({appName:' ORDERS ',environment:' DEV '}),
    {valid:true,appName:'orders',environment:'dev',provider:'github',appCount:1});
  for(const [appCount,expected] of [[0,0],[-2,0],[999,50],[' 3 ',3],[50,50]]) {
    assert.equal(normalizeInput({...valid,provider:' JENKINS ',appCount}).appCount,expected);
  }
  for(const appCount of [1.5,'1.5',NaN,Infinity,-Infinity]) assert.equal(normalizeInput({...valid,appCount}).valid,false);
});

for(const endpoint of ['/api/pipeline','/api/terraform','/api/helm']) {
  test(endpoint+' returns a client error for JSON objects with conversion-shaped fields',async () => {
    const before=await counters();
    for(const field of ['appName','environment','provider','appCount']) {
      const response=await post(endpoint,{...valid,[field]:{toString:null,valueOf:null}});
      assert.equal(response.status,400,field);
      const body=await response.json();assert.equal(typeof body.error,'string');assert.equal('content' in body,false);
    }
    assert.equal(await counters(),before);
  });
  test(endpoint+' rejects malformed JSON field types without success metrics or artifacts',async () => {
    const before=await counters();
    for(const payload of [[],null,{...valid,appName:['orders']},{...valid,environment:12},
      {...valid,provider:false},{...valid,appCount:true},{...valid,appCount:[]},
      {...valid,appName:{toString:null}},{...valid,environment:{toString:null}},
      {...valid,appCount:{valueOf:null,toString:null}}]) {
      const response=await post(endpoint,payload);
      assert.equal(response.status,400,JSON.stringify(payload));
      const body=await response.json();
      assert.equal(typeof body.error,'string'); assert.equal('content' in body,false);assert.equal('filename' in body,false);
    }
    assert.equal(await counters(),before);
    const response=await post(endpoint,{...valid,appCount:2});
    assert.equal(response.status,200);
    const body=await response.json();assert.equal(typeof body.filename,'string');assert.equal(typeof body.content,'string');
    const label=endpoint.split('/').at(-1);
    const counter=new RegExp(`(portal_requests_total\\{endpoint="${label}"\\} )(\\d+)`);
    assert.equal(await counters(),before.replace(counter,(_,prefix,n)=>prefix+(Number(n)+1)));
  });
}
