const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../../public/app.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../../public/index.html'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const goodInfo=()=>({build:{service:'demo',gitSha:'abc123',startedAt:'2026-10-26T10:00:00Z'},pipeline:{stages:['checkout','deploy']}});
const goodStatus=()=>({environment:'test',releaseColor:'blue',buildId:'build-42'});
const ok=body=>({ok:true,status:200,json:async()=>body});
async function page(infoReply,statusReply){
 class Element {
  constructor(){this.children=[];this.textContent='Loading...';this.markup='';}
  set innerHTML(v){this.markup=v;this.children=[];this.textContent='';}
  get innerHTML(){return this.markup;}
  appendChild(child){this.children.push(child);}
 }
 const elements=new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>[m[1],new Element()]));
 const calls=[],errors=[];
 vm.runInNewContext(source,{document:{getElementById:id=>{assert.ok(elements.has(id));return elements.get(id);},createElement:()=>new Element()},console:{error:e=>errors.push(e)},fetch:async url=>{
  calls.push(url);assert.ok(['/api/info','/api/status'].includes(url));
  const response=url==='/api/info'?infoReply:statusReply;
  if(response instanceof Error)throw response;
  return await response;
 }});
 await flush();
 return {elements,calls,errors};
}
function unavailable(p){
 for(const id of ['env','color','build','service','sha','started'])assert.equal(p.elements.get(id).textContent,'unavailable',id);
 assert.deepEqual(p.elements.get('stages').children.map(x=>x.textContent),['unavailable']);
}
test('dashboard renders all fields and pipeline stages on valid API responses',async()=>{
 const p=await page(ok(goodInfo()),ok(goodStatus()));
 for(const [id,value] of Object.entries({env:'test',color:'blue',build:'build-42',service:'demo',sha:'abc123',started:'2026-10-26T10:00:00Z'}))assert.equal(p.elements.get(id).textContent,value);
 assert.deepEqual(p.elements.get('stages').children.map(x=>x.textContent),['checkout','deploy']);assert.equal(p.errors.length,0);
});
test('dashboard marks every field and stages unavailable on either endpoint HTTP failure',async()=>{
 for(const failed of ['info','status']){
  const bad={ok:false,status:503,json:async()=>{throw Error('must not parse error response');}};
  const p=await page(failed==='info'?bad:ok(goodInfo()),failed==='status'?bad:ok(goodStatus()));unavailable(p);assert.equal(p.errors.length,1);
 }
});
test('dashboard handles transport and JSON decoding failures without permanent loading fields',async()=>{
 for(const bad of [new Error('offline'),{ok:true,status:200,json:async()=>{throw new SyntaxError('invalid JSON');}}]){
  unavailable(await page(bad,ok(goodStatus())));unavailable(await page(ok(goodInfo()),bad));
 }
});
test('dashboard rejects incomplete or malformed metadata before rendering a mixed success',async()=>{
 for(const info of [null,{}, {...goodInfo(),build:null},{...goodInfo(),build:{...goodInfo().build,service:3}}, {...goodInfo(),pipeline:{stages:'deploy'}},{...goodInfo(),pipeline:{stages:[null]}},{...goodInfo(),pipeline:{stages:['deploy',4]}}])unavailable(await page(ok(info),ok(goodStatus())));
 for(const status of [null,{}, {...goodStatus(),buildId:42},{...goodStatus(),releaseColor:null}])unavailable(await page(ok(goodInfo()),ok(status)));
});
test('dashboard renders metadata and stage labels as literal text',async()=>{
 const marker='<img src=x onerror=alert(1)>';
 const info=goodInfo();info.build.service=marker;info.pipeline.stages=[marker];
 const p=await page(ok(info),ok({...goodStatus(),buildId:marker}));
 assert.equal(p.elements.get('service').textContent,marker);assert.equal(p.elements.get('build').textContent,marker);
 const item=p.elements.get('stages').children[0];assert.equal(item.textContent,marker);assert.equal(item.innerHTML,'');
});
test('DT01: deferred fetch replies exercise both completion orders',async()=>{
 for(const infoFirst of [true,false]){
  let resolveInfo,resolveStatus;
  const infoPromise=new Promise(r=>{resolveInfo=r;});
  const statusPromise=new Promise(r=>{resolveStatus=r;});
  const p=await page(infoPromise,statusPromise);
  // before either resolves: all six metadata fields must remain Loading...
  for(const id of ['env','color','build','service','sha','started'])assert.equal(p.elements.get(id).textContent,'Loading...',`before-resolve ${id}`);
  assert.deepEqual(p.elements.get('stages').children,[]);
  // resolve the first of the pair; flush; intermediate state still all Loading...
  if(infoFirst){resolveInfo(ok(goodInfo()));}else{resolveStatus(ok(goodStatus()));}
  await flush();
  for(const id of ['env','color','build','service','sha','started'])assert.equal(p.elements.get(id).textContent,'Loading...',`after-first-resolve ${id}`);
  assert.deepEqual(p.elements.get('stages').children,[]);
  // resolve the second; flush; all expected values and stage order, zero errors
  if(infoFirst){resolveStatus(ok(goodStatus()));}else{resolveInfo(ok(goodInfo()));}
  await flush();
  for(const [id,value] of Object.entries({env:'test',color:'blue',build:'build-42',service:'demo',sha:'abc123',started:'2026-10-26T10:00:00Z'}))assert.equal(p.elements.get(id).textContent,value,`after-both-resolve ${id}`);
  assert.deepEqual(p.elements.get('stages').children.map(x=>x.textContent),['checkout','deploy']);
  assert.equal(p.errors.length,0);
 }
});
test('DT02: HTTP 503 on one endpoint while peer stays pending then resolves valid',async()=>{
 for(const failedEndpoint of ['info','status']){
  let resolvePeer;
  const peerPromise=new Promise(r=>{resolvePeer=r;});
  const bad={ok:false,status:503,json:async()=>{throw new Error('must not parse error response');}};
  const infoReply=failedEndpoint==='info'?bad:peerPromise;
  const statusReply=failedEndpoint==='status'?bad:peerPromise;
  const p=await page(infoReply,statusReply);
  // HTTP error does not throw; Promise.all rejects via ok:false check; peer still pending
  // assert every field and stages unavailable and exactly one logged error
  unavailable(p);
  assert.equal(p.errors.length,1,`one error before peer resolves (failed=${failedEndpoint})`);
  // now resolve the peer with valid data; flush; state must remain fully unavailable
  const peerBody=failedEndpoint==='info'?ok(goodStatus()):ok(goodInfo());
  resolvePeer(peerBody);
  await flush();
  unavailable(p);
  assert.equal(p.errors.length,1,`still one error after peer resolves (failed=${failedEndpoint})`);
 }
});
