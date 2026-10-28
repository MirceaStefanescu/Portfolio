const {test}=require('node:test');
const assert=require('node:assert/strict');
const request=require('supertest');
const {createApp}=require('../../src/app');

function count(text,metric,method,route,status){
  const prefix=`${metric}{method="${method}",route="${route}",status="${status}"} `;
  const line=text.split('\n').find(row=>row.startsWith(prefix));
  return line ? Number(line.slice(prefix.length)) : 0;
}
function observed(text,method,route,status,expected){
  for(const metric of ['http_requests_total','http_server_requests_seconds_count']){
    assert.equal(count(text,metric,method,route,status),expected,`${metric}: ${method} ${route} ${status}`);
  }
}

test('HTTP metrics count static GET, HEAD and conditional responses once with bounded labels',async()=>{
  const app=createApp();
  const first=await request(app).get('/').expect(200);
  await request(app).head('/').expect(200);
  await request(app).get('/').set('If-None-Match',first.headers.etag).expect(304);
  const metrics=await request(app).get('/metrics').expect(200);
  observed(metrics.text,'GET','unmatched',200,1);
  observed(metrics.text,'HEAD','unmatched',200,1);
  observed(metrics.text,'GET','unmatched',304,1);
});

test('HTTP metrics include parser rejections without exposing arbitrary paths',async()=>{
  const app=createApp();
  await request(app).post('/private-id-123').set('Content-Type','application/json').send('{').expect(400);
  await request(app).post('/private-id-456').send({data:'x'.repeat(110000)}).expect(413);
  const metrics=await request(app).get('/metrics').expect(200);
  observed(metrics.text,'POST','unmatched',400,1);
  observed(metrics.text,'POST','unmatched',413,1);
  assert.doesNotMatch(metrics.text,/private-id-/);
});

test('HTTP metrics count APIs and misses once and isolate independent app registries',async()=>{
  const first=createApp(),second=createApp();
  await request(first).get('/api/status').expect(200);
  await request(first).get('/absent-987').expect(404);
  await request(first).post('/api/status').send({valid:true}).expect(404);
  const metrics=await request(first).get('/metrics').expect(200);
  observed(metrics.text,'GET','/api/status',200,1);
  observed(metrics.text,'GET','unmatched',404,1);
  observed(metrics.text,'POST','unmatched',404,1);
  assert.doesNotMatch(metrics.text,/absent-987/);
  const other=await request(second).get('/metrics').expect(200);
  observed(other.text,'GET','/api/status',200,0);
  observed(other.text,'GET','unmatched',404,0);
});

test('each metrics scrape observes only previously completed scrapes',async()=>{
  const app=createApp();
  for(let previous=0;previous<3;previous++){
    const metrics=await request(app).get('/metrics').expect(200);
    observed(metrics.text,'GET','/metrics',200,previous);
  }
});

test('Prometheus exposition preserves HTTP histogram buckets and process metric names',async()=>{
  const app=createApp();
  await Promise.all(Array.from({length:5},()=>request(app).get('/api/info').expect(200)));
  const metrics=await request(app).get('/metrics').expect(200);
  const contentType=new (require('node:util').MIMEType)(metrics.headers['content-type']);
  assert.equal(contentType.essence,'text/plain');
  assert.equal(contentType.params.get('version'),'0.0.4');
  assert.equal(contentType.params.get('charset'),'utf-8');
  assert.match(metrics.text,/^# HELP http_requests_total Total number of HTTP requests$/m);
  assert.match(metrics.text,/^# TYPE http_requests_total counter$/m);
  assert.match(metrics.text,/^# TYPE http_server_requests_seconds histogram$/m);
  observed(metrics.text,'GET','/api/info',200,5);

  const buckets=[...metrics.text.matchAll(/^http_server_requests_seconds_bucket\{([^}]+)\} (\S+)$/gm)]
    .map(([,labels,value])=>({labels:Object.fromEntries([...labels.matchAll(/(\w+)="([^"]*)"/g)]
      .map(([,key,label])=>[key,label])),value:Number(value)}))
    .filter(({labels})=>labels.method==='GET'&&labels.route==='/api/info'&&labels.status==='200');
  assert.deepEqual(buckets.map(({labels})=>labels.le),
    ['0.005','0.01','0.025','0.05','0.1','0.25','0.5','1','2.5','5','+Inf']);
  let previous=0;
  for(const {value} of buckets){
    assert.ok(Number.isInteger(value)&&value>=previous&&value<=5,'cumulative bucket counts');
    previous=value;
  }
  assert.equal(previous,5,'infinite bucket covers every completed request');
  const sum=count(metrics.text,'http_server_requests_seconds_sum','GET','/api/info',200);
  assert.ok(Number.isFinite(sum)&&sum>0,'duration sum is a positive finite number');
  for(const name of ['process_cpu_user_seconds_total','process_start_time_seconds',
    'process_resident_memory_bytes','nodejs_heap_size_total_bytes']){
    const line=metrics.text.split('\n').find(row=>row.startsWith(name+' '));
    assert.ok(line,`${name} remains available`);
    assert.ok(Number.isFinite(Number(line.slice(name.length+1))),`${name} is finite`);
  }
  assert.match(metrics.text,/^nodejs_version_info\{[^\n]+\} 1$/m);
});

test('a keep-alive connection recovers after malformed JSON with separate error and success metrics',async()=>{
  const http=require('node:http');
  const {once}=require('node:events');
  const server=createApp().listen(0,'127.0.0.1');
  await once(server,'listening');
  const agent=new http.Agent({keepAlive:true,maxSockets:1});
  const call=(url,body)=>new Promise((resolve,reject)=>{
    const req=http.request({host:'127.0.0.1',port:server.address().port,path:url,agent,
      headers:body===undefined?{}:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}},res=>{
      const socketPort=res.socket.localPort;let text='';res.setEncoding('utf8');
      res.on('data',chunk=>{text+=chunk;});res.on('error',reject);
      res.on('end',()=>resolve({status:res.statusCode,text,socketPort}));
    });
    req.on('error',reject);req.end(body);
  });
  try {
    const bad=await call('/api/status','{');
    const good=await call('/api/status','{}');
    assert.equal(bad.status,400);assert.equal(good.status,200);
    assert.equal(bad.socketPort,good.socketPort,'same keep-alive connection');
    const metrics=await call('/metrics');assert.equal(metrics.status,200);
    observed(metrics.text,'GET','unmatched',400,1);
    observed(metrics.text,'GET','/api/status',200,1);
  } finally {
    agent.destroy();server.closeAllConnections();
    await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));
  }
});
