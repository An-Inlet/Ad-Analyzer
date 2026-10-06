import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareSignIn} from '../../app/portal/static/auth.mjs';
const config = {enabled:true,providers:['google.com'],firebase:{projectId:'inlet-test',authDomain:'inlet-test.firebaseapp.com'}};
function fixture({existing=401, revoke=204, exchange=200, lost=false, popupFail=false, cleanupFail=false}={}) {
  const calls=[]; const sdkCalls=[];
  const sdk={inMemoryPersistence:{},browserPopupRedirectResolver:{},
    initializeApp(c,n){sdkCalls.push('app');return{};},
    initializeAuth(a,c){assert.equal(c.persistence,sdk.inMemoryPersistence);sdkCalls.push('memory');return{};},
    GoogleAuthProvider:class{setCustomParameters(p){assert.equal(p.prompt,'select_account');}},
    async signInWithPopup(a,p,r){assert.equal(r,sdk.browserPopupRedirectResolver);sdkCalls.push('popup');if(popupFail)throw Error('private provider response');return {user:{async getIdToken(force){assert.equal(force,true);return 'fixture-token';}}};},
    async signOut(){sdkCalls.push('clear');if(cleanupFail)throw Error('private cleanup error');},
    async deleteApp(){sdkCalls.push('delete');}};
  const fetcher=async(path,o={})=>{
    calls.push([path,o]);if(path.endsWith('auth-config'))return Response.json(config);
    if(o.method==='POST'){if(lost)throw Error('network lost');return Response.json({}, {status:exchange});}
    if(o.method==='DELETE')return new Response(null,{status:revoke});
    return Response.json({}, {status:existing});};
  return {calls,sdkCalls,sdk,fetcher};
}
test('disabled means no SDK import or provider operation',async()=>{
  const sign=await prepareSignIn(async()=>Response.json({enabled:false}),()=>{throw Error('SDK loaded');});assert.equal(sign,null);
});
test('fresh signup/signin has one exchange and always clears in-memory SDK',async()=>{
 const f=fixture();const sign=await prepareSignIn(f.fetcher,async()=>f.sdk);await sign('');
 assert.deepEqual(f.sdkCalls,['app','memory','popup','clear','delete']);
 const posts=f.calls.filter(([,o])=>o.method==='POST');assert.equal(posts.length,1);
 assert.equal(posts[0][1].headers['X-Inlet-Request'],'1');assert.equal(posts[0][1].credentials,'same-origin');
});
for(const scenario of [{lost:true},{exchange:401},{exchange:503}])test('uncertain/failed exchange never retries or adopts session '+JSON.stringify(scenario),async()=>{
 const f=fixture(scenario);const sign=await prepareSignIn(f.fetcher,async()=>f.sdk);
 await assert.rejects(sign(),/Check Session Again/);
 assert.equal(f.calls.filter(([,o])=>o.method==='POST').length,1);
 assert.equal(f.calls.filter(([p,o])=>p.endsWith('/session')&&!o.method).length,1);
 assert.deepEqual(f.sdkCalls.slice(-2),['clear','delete']);
});
test('confirmed logout precedes new popup; unknown logout blocks provider',async()=>{
 for(const revoke of [204,503]){const f=fixture({existing:200,revoke});const sign=await prepareSignIn(f.fetcher,async()=>f.sdk);
 if(revoke===204)await sign('__Host-inlet_csrf='+'a'.repeat(43));
 else{await assert.rejects(sign('__Host-inlet_csrf='+'a'.repeat(43)));assert.deepEqual(f.sdkCalls,[]);}
 assert.equal(f.calls[2][1].method,'DELETE');}
});
test('provider and cleanup errors never display confidential error text',async()=>{
 for(const scenario of [{popupFail:true},{cleanupFail:true}]){const f=fixture(scenario);const sign=await prepareSignIn(f.fetcher,async()=>f.sdk);
 await assert.rejects(sign(),e=>!e.message.includes('private'));assert.equal(f.sdkCalls.at(-1),'delete');}
});
test('arbitrary configured auth domain fails before loading SDK',async()=>{
 await assert.rejects(prepareSignIn(async()=>Response.json({...config,firebase:{...config.firebase,authDomain:'attacker.test'}}),()=>{throw Error('loaded');}),/not configured/);
});
