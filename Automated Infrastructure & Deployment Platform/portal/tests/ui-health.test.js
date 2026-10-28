const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../public/app.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../public/index.html'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const reply=(services,ok=true)=>({ok,json:async()=>({services})});
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
async function page(){
  class Element {
    constructor(){this.children=[];this.textContent='';this.disabled=false;this.hidden=false;this.html='';this.value='';}
    set innerHTML(value){this.html=value;this.children=[];}
    get innerHTML(){return this.html;}
    appendChild(child){this.children.push(child);}
    addEventListener(){}
  }
  const elements=new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>[m[1],new Element()]));
  const requests=[],timers=[];
  vm.runInNewContext(source,{document:{getElementById:id=>{assert.ok(elements.has(id));return elements.get(id);},createElement:()=>new Element()},setInterval(fn){timers.push(fn);},fetch:async(url)=>{
    if(url==='/api/me')return {ok:true,json:async()=>({name:'Fixture',role:'admin',mode:'demo'})};
    assert.equal(url,'/api/services');const pending=deferred();requests.push(pending);return pending.promise;
  }});
  await flush();
  const text=e=>e.textContent+e.html+e.children.map(text).join(' ');
  return {requests,poll:()=>timers[0](),rows:()=>elements.get('serviceStatus').children.map(text),nodes:()=>elements.get('serviceStatus').children};
}

test('health UI reports one unavailable portal after HTTP failure and can recover',async()=>{
  const p=await page();p.requests[0].resolve(reply([],false));await flush();
  assert.equal(p.rows().length,1);assert.match(p.rows()[0],/Portal.*unreachable/);assert.doesNotMatch(p.rows()[0],/healthy/);
  p.poll();p.requests[1].resolve(reply([{name:'Jenkins',status:'healthy'}]));await flush();
  assert.equal(p.rows().length,2);assert.match(p.rows()[0],/Portal.*healthy/);assert.match(p.rows()[1],/Jenkins.*healthy/);
});

test('health UI replaces previous statuses on transport or JSON failure without a healthy duplicate',async()=>{
  const p=await page();p.requests[0].resolve(reply([{name:'Vault',status:'healthy'}]));await flush();
  p.poll();p.requests[1].reject(new Error('offline'));await flush();
  assert.equal(p.rows().length,1);assert.match(p.rows()[0],/Portal.*unreachable/);assert.doesNotMatch(p.rows()[0],/healthy|Vault/);
  p.poll();p.requests[2].resolve({ok:true,json:async()=>{throw new SyntaxError('bad JSON');}});await flush();
  assert.equal(p.rows().length,1);assert.match(p.rows()[0],/Portal.*unreachable/);
});

test('health UI rejects malformed payloads instead of reporting success',async()=>{
  for(const services of [null,{},'invalid',[null],[{}],[{name:'Vault',status:'invented'}],[{name:7,status:'healthy'}]]){
    const p=await page();p.requests[0].resolve(reply(services));await flush();
    assert.equal(p.rows().length,1);assert.match(p.rows()[0],/Portal.*unreachable/);assert.doesNotMatch(p.rows()[0],/healthy/);
  }
});

test('health UI ignores older success and older failure after a newer poll completes',async()=>{
  for(const oldFails of [false,true]){
    const p=await page();p.poll();assert.equal(p.requests.length,2);
    p.requests[1].resolve(reply([{name:'Vault',status:'unhealthy'}]));await flush();
    const expected=p.rows();
    if(oldFails)p.requests[0].reject(new Error('old failure'));
    else p.requests[0].resolve(reply([{name:'Vault',status:'healthy'}]));
    await flush();assert.deepEqual(p.rows(),expected);assert.match(p.rows()[1],/unhealthy/);
  }
});

test('health UI renders service labels as text and preserves each supported status',async()=>{
  const p=await page();const label='<img src=x onerror=alert(1)>';
  p.requests[0].resolve(reply(['healthy','unhealthy','unconfigured','unreachable'].map(status=>({name:label,status}))));await flush();
  assert.equal(p.rows().length,5);
  for(const [i,status] of ['healthy','unhealthy','unconfigured','unreachable'].entries()){
    const row=p.nodes()[i+1];assert.equal(row.html,'','service markup must not be parsed');
    assert.equal(row.children[0].textContent,label);assert.equal(row.children[1].textContent,status);
    assert.equal(row.children[1].className,'badge '+status);
  }
});
