const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../public/app.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../public/index.html'),'utf8');
const kinds=['pipeline','terraform','helm'];
const cap=s=>s[0].toUpperCase()+s.slice(1);
const response=(data,ok=true)=>({ok,json:async()=>data});
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function page(role='admin'){
  const elements=new Map(),downloads=[],blobs=new Map(),revoked=[],pending=[];
  class Element {
    constructor(){this.value='';this.textContent='';this.innerHTML='';this.disabled=false;this.hidden=false;this.listeners={};}
    addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
    appendChild(){} remove(){}
    click(){if(this.disabled)return; if(this.download)downloads.push({filename:this.download,blob:blobs.get(this.href)});else return this.emit('click');}
    emit(type){return Promise.all((this.listeners[type]||[]).map(fn=>fn()));}
  }
  for(const match of html.matchAll(/<\w+\b[^>]*\bid="([^"]+)"[^>]*>/g)){
    const element=new Element();element.disabled=/\bdisabled\b/.test(match[0]);elements.set(match[1],element);
  }
  for(const [id,value] of Object.entries({appName:'orders',environment:'dev',provider:'github',appCount:'3'}))elements.get(id).value=value;
  const document={getElementById:id=>{assert.ok(elements.has(id),'real HTML must contain '+id);return elements.get(id);},createElement:()=>new Element(),body:new Element()};
  let uid=0;
  vm.runInNewContext(source,{document,Blob,URL:{createObjectURL(blob){const url='blob:fixture/'+(++uid);blobs.set(url,blob);return url;},revokeObjectURL:url=>revoked.push(url)},window:{location:{reload(){}}},setInterval(){},fetch:async(url,options)=>{
    if(url==='/api/me')return response({name:'Fixture',role,mode:'demo',csrf:'fixture'});
    if(url==='/api/services')return response({services:[]});
    const request=deferred();pending.push({url,options,...request});return request.promise;
  }});
  await flush();
  return {elements,downloads,revoked,pending,click:id=>elements.get(id).click(),edit:async(id,value)=>{elements.get(id).value=value;await elements.get(id).emit('input');}};
}
async function generate(p,kind,data){const call=p.click('generate'+cap(kind));p.pending.at(-1).resolve(response(data));await call;}

for(const kind of kinds){
  test(kind+' invalidates prior download during pending generation and after failure',async()=>{
    const p=await page();const button='download'+cap(kind);
    assert.equal(p.elements.get(button).disabled,true,'no initial artifact');
    await generate(p,kind,{filename:'first.txt',content:'first bytes'});
    assert.equal(p.elements.get(button).disabled,false);p.click(button);
    assert.equal(p.downloads.length,1);assert.equal(await p.downloads[0].blob.text(),'first bytes');
    const next=p.click('generate'+cap(kind));
    assert.equal(p.elements.get(button).disabled,true,'old artifact unavailable during regeneration');
    p.click(button);assert.equal(p.downloads.length,1);
    p.pending.at(-1).resolve(response({error:'Fixture failure',requestId:'r1'},false));await next;
    assert.match(p.elements.get(kind+'Output').textContent,/Fixture failure/);
    assert.equal(p.elements.get(button).disabled,true);p.click(button);assert.equal(p.downloads.length,1);
    assert.equal(p.elements.get('generate'+cap(kind)).disabled,false);
  });
  test(kind+' rejects malformed successful payloads without creating downloads',async()=>{
    const p=await page();
    for(const payload of [null,{}, {filename:'x',content:{}},{filename:'',content:'x'},{filename:7,content:'x'}]){
      await generate(p,kind,payload);
      assert.equal(p.elements.get('download'+cap(kind)).disabled,true);
      assert.match(p.elements.get(kind+'Output').textContent,/Invalid artifact response/);
      p.click('download'+cap(kind));assert.equal(p.downloads.length,0);
    }
  });
  test(kind+' ignores a superseded response after inputs change and a newer request completes',async()=>{
    const p=await page();const first=p.click('generate'+cap(kind));
    const old=p.pending.at(-1);await p.edit('appName','new-orders');
    const second=p.click('generate'+cap(kind));const recent=p.pending.at(-1);
    assert.notEqual(old,recent);recent.resolve(response({filename:'second.txt',content:'second'}));await second;
    old.resolve(response({filename:'first.txt',content:'first'}));await first;
    assert.equal(p.elements.get(kind+'Output').textContent,'second');
    p.click('download'+cap(kind));assert.equal(p.downloads[0].filename,'second.txt');
    assert.equal(await p.downloads[0].blob.text(),'second');
  });
}

test('artifact downloads stay independent when another generator fails',async()=>{
  const p=await page();
  for(const kind of kinds)await generate(p,kind,{filename:kind+'.txt',content:kind+' bytes'});
  const failed=p.click('generateTerraform');p.pending.at(-1).reject(new Error('network offline'));await failed;
  p.click('downloadPipeline');p.click('downloadTerraform');p.click('downloadHelm');
  assert.deepEqual(p.downloads.map(x=>x.filename),['pipeline.txt','helm.txt']);
  assert.deepEqual(await Promise.all(p.downloads.map(x=>x.blob.text())),['pipeline bytes','helm bytes']);
  assert.equal(p.revoked.length,2);
});

test('editing any shared input invalidates generated downloads',async()=>{
  for(const id of ['appName','environment','provider','appCount']){
    const p=await page();for(const kind of kinds)await generate(p,kind,{filename:kind+'.txt',content:kind});
    await p.edit(id,'changed');
    for(const kind of kinds){assert.equal(p.elements.get('download'+cap(kind)).disabled,true);p.click('download'+cap(kind));}
    assert.equal(p.downloads.length,0);
  }
});

test('viewer cannot activate generation through the UI',async()=>{
  const p=await page('viewer');
  for(const kind of kinds){assert.equal(p.elements.get('generate'+cap(kind)).disabled,true);p.click('generate'+cap(kind));}
  assert.equal(p.pending.length,0);
});
