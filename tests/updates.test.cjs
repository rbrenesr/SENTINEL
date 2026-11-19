const {test} = require('node:test');
const assert = require('node:assert/strict');
const U = require('../assets/updates.js');
const now = Date.parse('2026-11-19T12:00:00Z');
const requestId = '12345678-1234-1234-1234-123456789abc';
const sampleToken = 'github_pat_' + 'x'.repeat(40);
const response = (status, body) => ({status, ok: status >= 200 && status < 300, json: async () => body, headers: new Headers()});

test('freshness reports actual data age independently of workflow success', () => {
  assert.equal(U.freshness('2026-11-19T11:30:00Z', now).delayed, false);
  assert.deepEqual(U.freshness('2026-11-19T10:00:00Z', now), {delayed:true,ageMinutes:120});
  assert.equal(U.freshness(null, now).delayed, true);
  assert.equal(U.freshness('2026-11-20T00:00:00Z', now).delayed, true);
});
test('queued or failed workflow is never labelled as newly published news', () => {
  assert.match(U.runLabel({status:'queued'}), /espera/);
  assert.match(U.runLabel({status:'completed',conclusion:'failure'}), /Falló/);
  assert.equal(U.runLabel({status:'completed',conclusion:'success'}), 'Ejecución completada');
  assert.equal(U.runURL('https://other.example'), null);
});
test('dispatch sends a temporary credential only to the fixed GitHub endpoint', async () => {
  let calls = [];
  const fetcher = async (url, options) => { calls.push({url,options}); return response(200,{workflow_run_id:123}); };
  const result = await U.dispatchCollection(sampleToken, requestId, fetcher);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, U.apiURL + '/dispatches');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer ' + sampleToken);
  assert.equal(calls[0].options.credentials, 'omit');
  assert.equal(calls[0].options.redirect, 'error');
  assert.deepEqual(JSON.parse(calls[0].options.body), {ref:'main',inputs:{request_id:requestId}});
  assert.equal(JSON.stringify(result).includes(sampleToken), false);
  assert.deepEqual(result,{id:'123',requestId});
});
test('dispatch supports the older empty 204 response', async () => {
  assert.deepEqual(await U.dispatchCollection(sampleToken,requestId,async()=>response(204)),{id:null,requestId});
});
test('empty, classic and malformed tokens never cause a network request', async () => {
  for (const value of ['', 'ghp_' + 'x'.repeat(40), 'github_pat_bad\nheader']) {
    let contacted = false;
    await assert.rejects(U.dispatchCollection(value,requestId,async()=>{contacted=true;}));
    assert.equal(contacted,false);
  }
});
test('authorization errors do not echo credentials or the response body', async () => {
  await assert.rejects(U.dispatchCollection(sampleToken,requestId,async()=>response(401,{message:sampleToken})),
    error=>error.status===401 && !error.message.includes(sampleToken));
});
test('public monitoring sends no token or cookies and ignores unrelated branches', async () => {
  let options;
  const runs = await U.readRuns(async (url,value)=>{options=value; return response(200,{workflow_runs:[
    {id:42,head_branch:'main'},{id:43,head_branch:'unrelated'},{id:'invalid',head_branch:'main'}
  ]});});
  assert.equal(options.credentials,'omit');
  assert.equal(options.headers.Authorization,undefined);
  assert.deepEqual(runs.map(run=>run.id),[42]);
});
test('rate limiting backs off rather than retrying the API continuously', async () => {
  const limited=response(403,{});
  limited.headers=new Headers({'x-ratelimit-remaining':'0','x-ratelimit-reset':String(Math.floor(Date.now()/1000)+3600)});
  await assert.rejects(U.readRuns(async()=>limited),error=>error.retryAt > Date.now()+3500000);
});
