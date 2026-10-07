// DOM doubles only; configured HTTPS/API acceptance is verified separately.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {checkedDiscovery,discoveryIntent,tiktokDiscovery} from '../../app/portal/static/tiktok-discovery.mjs';
class Element {value='';textContent='';hidden=false;disabled=false;children=[];replaceChildren(...v){this.children=v;this.value='';this.textContent='';}append(...v){this.children.push(...v);}}
const elements=new Map([...fs.readFileSync('app/portal/static/execution.html','utf8').matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element()]));
globalThis.document={getElementById:id=>elements.get(id),createElement:()=>new Element()};
globalThis.Option=class extends Element{constructor(label,value){super();this.textContent=label;this.value=value;}};
const $=id=>elements.get('discovery-'+id),text=e=>[e.textContent,...e.children.map(text)].join(' ');
const intent={account_id:7,identity_type:'TT_USER'};
const observed={schema_version:'inlet.tiktok-customer-discovery.v1',...intent,status:'observed',reason:null,environment:'contract_test',collection_completeness:'complete_requested_scope',observed_started_at:'2026-10-07T00:00:00Z',observed_ended_at:'2026-10-07T00:00:01Z',identity_count:1,pixel_count:1,event_count:null,identities:[{label:'Brand <script>',status:'AVAILABLE',permissions:[{name:'can_push_video',state:'null'}],reasons:['identity_route_not_assessed']}],pixels:[{label:'Store Pixel',ownership:'unknown',events_count:null,events_presence:'absent',events:[],events_display_truncated:false,reasons:['tracking_readiness_unknown']}],identities_display_truncated:false,pixels_display_truncated:false,display_truncated:false,publication_eligibility:'not_assessed',spending_authority:'none'};
assert.deepEqual(discoveryIntent('7','TT_USER'),intent);
for(const account of ['0','1.2','native-id','9007199254740992'])assert.throws(()=>discoveryIntent(account,'TT_USER'));
assert.throws(()=>discoveryIntent('7','bad'));
assert.equal(checkedDiscovery(observed,intent),observed);
for(const change of [{account_id:8},{spending_authority:'approved'},{publication_eligibility:'eligible'},{event_count:false},{display_truncated:true},{identity_count:21},{observed_ended_at:'2026-10-06T00:00:00Z'},{pixels:[{...observed.pixels[0],events_count:0}]}])assert.throws(()=>checkedDiscovery({...observed,...change},intent));
const calls=[];let workspace='1',signed=true,release=null,hold=false,response=observed;
const controller=tiktokDiscovery({state:()=>({workspace,signed}),guarded:async fn=>{try{await fn();}finally{controller.enable(false);}},api:async(path,method,body)=>{calls.push({path,method,body});if(path.endsWith('/accounts'))return {complete:true,accounts:[{id:7,name:'Brand',platform:'tiktok_ads'},{id:8,name:'Other',platform:'meta_ads'}]};if(hold)await new Promise(r=>release=r);return response;}});
controller.reset();controller.enable(false);assert.equal(calls.length,0);
await $('accounts').onclick();assert.equal($('account').children.length,2);
$('account').value='7';$('account').onchange();await $('read').onclick();
assert.deepEqual(calls.at(-1),{path:'/workspaces/1/execution/tiktok/discovery',method:'POST',body:intent});
assert.match(text($('identities')),/Brand <script>.*Reported Identity Status: Reported Available — Publication Not Assessed.*Reported As Null/);
assert.match(text($('summary')),/Unknown — Some Event Lists Were Not Reported/);
assert.match(text($('pixels')),/Events: Unknown.*Not Reported/);
assert.equal($('identities').children[0].textContent,'Brand <script>');
hold=true;const pending=$('read').onclick();await new Promise(r=>setImmediate(r));$('type').value='AUTH_CODE';$('type').onchange();release();await pending;assert.equal($('result').hidden,true);
$('type').value='TT_USER';const logout=$('read').onclick();await new Promise(r=>setImmediate(r));signed=false;workspace='';controller.reset();controller.enable(false);release();await logout;assert.equal($('result').hidden,true);assert.equal($('section').hidden,true);assert.equal($('identities').children.length,0);
assert.ok(!calls.some(c=>/approve|review|advance|consent/.test(c.path)));
