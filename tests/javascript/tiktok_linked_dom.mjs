// Response-fixture DOM acceptance, deliberately separate from configured API tests.
const media=__MEDIA__, original=fetch.bind(window), $=id=>document.getElementById(id);
const assert=(value,message)=>{if(!value)throw new Error(message);};
const wait=async(predicate)=>{for(let n=0;n<500;n++){if(predicate())return;await new Promise(r=>setTimeout(r,10));}throw new Error('Timed out: '+predicate.toString()+'; '+$('linked-message').textContent);};
const choose=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'));};
const json=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
const rid='b'.repeat(32),eid='c'.repeat(32),digest='a'.repeat(64),option='d'.repeat(64),mid='e'.repeat(32);
let confirmed=false, lastAnswer=null, approvals=0,runs=0,delay=null,release=null,calls=0;
const saved=()=>({id:rid,digest,environment:'contract_test',confirmed,option_id:option,requirements_text:'Review Linked Identity And Ads Only Visibility',identity_type:'TT_USER',visibility:'Ads Only',creation:'Creates A New Linked Post',spending_authority:'none',financial_qualification:'not_assessed',media,configuration:config,identity_label:'Owned TikTok Identity',creative:{text:'Exact Copy',landing_page:'https://example.com',audience:{countries:['US'],languages:['en']}},campaign:{name:'<img src=x>',currency:'USD',budget_micros:100000000,starts_at:'2026-10-08',ends_at:'2026-10-09'}});
const config={kind:'tiktok_linked_push_v13',account_timezone:'America/New_York',video:media.video,cover:media.cover,identity:{identity_id:'123'},pixel_id:'456',age_groups:['AGE_25_34'],click_attribution_window:'SEVEN_DAYS',view_attribution_window:'OFF',engaged_view_attribution_window:'OFF',comment_disabled:true,share_disabled:true,video_download_disabled:true};
document.cookie='__Host-inlet_csrf='+'x'.repeat(43)+'; Path=/; Secure; SameSite=Strict';
window.fetch=async(url,init={})=>{
  if(!String(url).startsWith('/api/'))return original(url,init);
  calls++;const body=init.body?JSON.parse(init.body):null;
  if(String(url).includes('/media/')&&!String(url).endsWith('/media')){const name=String(url).split('/').pop();const bytes=await(await original('/'+name)).arrayBuffer();return new Response(bytes,{headers:{'Content-Type':media[name].mime}});}
  if(url.endsWith('/session'))return init.method==='DELETE'?new Response(null,{status:204}):json({user_id:'owner'});
  if(url.endsWith('/workspaces'))return json([{id:1,name:'Owned Workspace'}]);
  if(url.endsWith('/campaign-drafts'))return json([{draft_id:'f'.repeat(32),revision:1,name:'Video Campaign'}]);
  if(url.endsWith('/options')){if(delay==='options')await new Promise(r=>release=r);return json({name:'Video',environment:'contract_test',options:[{id:option,name:'Linked Identity',requirements_text:'Exact Rules',review_available:true}],blockers:[]});}
  if(url.endsWith('/preview'))return json({artifact:{definition:{account:{platform:'tiktok_ads'},content:{media:media.video}}}});
  if(url.endsWith('/media'))return json(Object.values(media));
  if(url.endsWith('/confirmation')){confirmed=true;return json(saved());}
  if(url.endsWith('/linked/reviews')){lastAnswer=body.answer;return json(saved());}
  if(url.endsWith('/mandates'))return json([{id:mid,revision:1,state:'active',account_names:['TikTok Account'],policy:{environment:'contract_test',total_cap_micros:100000000,per_plan_cap_micros:100000000,currency:'USD',starts_at:'2026-10-08',ends_at:'2026-10-09'}}]);
  if(url.endsWith('/creation-reviews'))return json({id:eid,review_digest:digest,plan_digest:digest,platform:'tiktok_ads',environment:'contract_test',purpose:'create_paused',configuration:config,creative:{text:'Exact Copy',landing_page:'https://example.com',audience:{countries:['US'],languages:['en']}},campaign_name:'Exact Campaign',currency:'USD',reserved_upper_micros:100000000,starts_at:'2026-10-08',ends_at:'2026-10-09',qualification_expires_at:'2026-10-08'});
  if(url.endsWith('/approval')){approvals++;return json({ok:true});}
  if(url.endsWith('/runs')){runs++;return json({id:'9'.repeat(32)});}
  throw new Error('Unexpected fixture route '+url);
};
try{
 await import('/app/assets/tiktok-linked.mjs');await wait(()=>!$('linked-selection').hidden&&!$('linked-workspace').disabled);
 choose('linked-workspace','1');await wait(()=>$('linked-draft').options.length===2&&!$('linked-draft').disabled);choose('linked-draft','f'.repeat(32));$('linked-load').click();await wait(()=>!$('linked-configuration').hidden&&!$('linked-option').disabled);
 choose('linked-option',option);choose('linked-cover','cover');await wait(()=>$('execution-linked-media').textContent.includes('Exact Private Media Loaded')&&!$('linked-cover').disabled);
 assert($('linked-save').disabled,'explicit declarations required');for(const id of ['linked-pair','linked-rights','linked-post','linked-visibility']){assert(!$(id).checked,'declaration default');$(id).checked=true;$(id).dispatchEvent(new Event('change'));}
 $('linked-save').click();await wait(()=>!$('linked-saved').hidden&&!$('linked-confirm-check').disabled);
 assert(lastAnswer.kind==='tiktok_linked_push'&&Object.values(lastAnswer).filter(x=>x===true).length===4,'exact explicit answer');assert(!$('linked-summary').querySelector('img'),'safe text rendering');assert($('linked-confirm').disabled,'no implied configuration confirmation');
 $('linked-confirm-check').checked=true;$('linked-confirm-check').dispatchEvent(new Event('change'));$('linked-confirm').click();await wait(()=>!$('linked-spending').hidden&&!$('linked-mandate').disabled);
 assert($('linked-mandate').options.length===2,'actual nested policy environment retains consented mandate');choose('linked-mandate',mid);assert($('linked-mandate-summary').textContent.includes('100.000000 USD'),'exact mandate limits');$('linked-prepare').click();await wait(()=>!$('linked-execution').hidden&&!$('linked-approve-check').disabled&&$('execution-linked-review-media').textContent.includes('Exact Private Media Loaded'));
 assert(approvals===0&&runs===0&&$('linked-approve').disabled,'creation review alone grants no approval');$('linked-approve-check').checked=true;$('linked-approve-check').dispatchEvent(new Event('change'));$('linked-approve').click();await wait(()=>!$('linked-start').disabled);$('linked-start').click();await wait(()=>!$('linked-run').hidden);assert(runs===1&&approvals===1,'separate actions');
 choose('linked-cover','');assert($('linked-saved').hidden&&$('linked-execution').hidden&&$('linked-start').disabled,'media change clears exact authority');await wait(()=>!$('linked-load').disabled);
 delay='options';$('linked-load').click();await wait(()=>release);choose('linked-draft','');release();await wait(()=>!$('linked-refresh').disabled);assert($('linked-saved').hidden&&$('linked-configuration').hidden,'delayed old catalog cannot resurrect after selection change');
 delay=null;choose('linked-draft','f'.repeat(32));document.cookie='__Host-inlet_csrf='+'z'.repeat(43)+'; Path=/; Secure; SameSite=Strict';const before=calls;$('linked-load').click();await wait(()=>$('linked-selection').hidden);assert(calls===before,'changed original session denied before API IO');
 await original('/__result__',{method:'POST',body:'passed'});
}catch(error){await original('/__result__',{method:'POST',body:error.stack||String(error)});}
