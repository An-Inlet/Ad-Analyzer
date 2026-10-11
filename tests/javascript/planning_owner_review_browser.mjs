// Genuine portal actions; provider data and saved plans come only from owned APIs.
const cfg=__CONFIG__,$=id=>document.getElementById('planning-'+id);
const assert=(v,m)=>{if(!v)throw Error(m);},native=window.fetch.bind(window);
const json=async r=>{assert(r.ok,'HTTP '+r.status);return r.json();};
const until=async(fn,message)=>{const end=Date.now()+35000;while(!fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(node,value,event='change')=>{assert(node,'control exists');node.value=value;node.dispatchEvent(new Event(event));};
const checked=(node,value)=>{assert(node,'checkbox exists');node.checked=value;node.dispatchEvent(new Event('change'));};
const role=(host,name)=>host.querySelector(`[data-role="${name}"]`);
const canonical=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
const settled=()=>!$('list-refresh').disabled;
const root=`/api/customer/v1/workspaces/${cfg.workspace_id}/planning`;
const owner=()=>document.getElementById('google-owner-inputs');
let catalog=null,discovery=null,created=null,generated=null,downloaded=null,revision=null;
let createPosts=0,generatePosts=0,freshReads=0,inputPosts=0,transition=null;
let originalCreateBody=null,originalGenerateBody=null;
try{
 await json(await native('/api/customer/v1/session'));
 const sessionCookies=document.cookie;
 window.fetch=async(...args)=>{
  const path=String(args[0]),method=args[1]?.method??'GET';
  if(path.endsWith('/inputs')&&method==='POST')inputPosts++;
  const response=await native(...args);
  if(path===root+'/target-catalog-v2'&&method==='POST'&&response.ok){catalog=await response.clone().json();freshReads++;}
  if(path===root+'/google-budget-owners'&&method==='POST'&&response.ok)discovery=await response.clone().json();
  if(path===root+'/plans'&&method==='POST'){
   createPosts++;originalCreateBody=JSON.parse(args[1].body);assert(response.ok,'actual create succeeds');created=await response.clone().json();
   // Actual committed receipt recovery; never send a second create with a new key.
   if(cfg.journey==='positive')throw TypeError('lost committed input response');
  }
  if(path.endsWith('/generate')&&method==='POST'){
   generatePosts++;originalGenerateBody=JSON.parse(args[1].body);if(response.ok)generated=await response.clone().json();
  }
  if(path.includes('/export?version=1')&&response.ok)downloaded=await response.clone().json();
  if(path.endsWith('/inputs')&&method==='POST'&&response.ok){revision=await response.clone().json();assert(JSON.parse(args[1].body).inputs.google_daily_budget_intents.length===0,'explicit removal request');}
  return response;
 };
 await import('/app/assets/planning.mjs');
 await until(()=>settled()&&$('workspace').options.length>1,'workspace list');
 change($('workspace'),String(cfg.workspace_id));await until(()=>settled()&&!$('new').hidden,'owned plans');
 $('new').click();await until(()=>settled()&&!$('editor').hidden,'owner editor');
 assert(owner()&&!owner().hidden,'private V6 controls');
 const input=cfg.form;
 change($('goal'),input.goal_id);checked($('accounts').querySelector(`input[value="${cfg.account_id}"]`),true);
 $('milestone').value=input.milestone;$('product').value=input.product_offer;$('creative').value='1';
 change($('start'),new Date(input.reporting_window.starts_at).toISOString().slice(0,16));
 change($('end'),new Date(input.reporting_window.ends_at_exclusive).toISOString().slice(0,16));
 checked($('comparison-enabled'),true);
 change($('comparison-start'),new Date(input.comparison_window.starts_at).toISOString().slice(0,16));
 change($('comparison-end'),new Date(input.comparison_window.ends_at_exclusive).toISOString().slice(0,16));
 const capture=$('selected-captures').querySelector('input');assert(Number(capture.dataset.captureAccount)===cfg.account_id,'owned selected account');capture.value=input.selected_reporting[0].capture_id;
 checked($('include-product'),true);$('product-name').value='Reusable travel mug';$('list-price').value='25';$('price-currency').value='USD';$('product-restrictions').value='No approved health claims or testimonials.';
 const image=$('image-library').querySelector(`[data-planning-media-id="${cfg.media_id}"] input[type=checkbox]`);checked(image,true);
 async function readAlternative(){
  const before=freshReads;$('targets-read').click();await until(()=>settled()&&freshReads===before+1&&role($('scenarios'),'scenario-add'),'fresh actual target catalog');
  assert(catalog.targets.length===6,'complete projected target list');
  const index=catalog.targets.findIndex(t=>t.entity.kind==='campaign'&&t.entity.reference.entity_id==='1');assert(index>=0,'exact observed campaign A');
  role($('scenarios'),'scenario-add').click();
  change(role($('scenarios'),'scenario-title'),'Owner Review Alternative','input');
  change(role($('scenarios'),'scenario-reserve'),'900','input');
  role($('scenarios'),'scenario-row-add').click();
  change(role($('scenarios'),'scenario-target'),String(index));
  change(role($('scenarios'),'scenario-amount'),'100','input');
 }
 await readAlternative();
 role(owner(),'owner-discover').click();await until(()=>settled()&&discovery!==null&&(cfg.journey==='partial'?role(owner(),'owner-status').textContent.includes('Read fresh targets'):role(owner(),'owner-option')?.options.length>1),'receipt discovery');
 if(cfg.journey==='partial'){
  assert(discovery.status==='unavailable'&&discovery.owners.length===0,'partial membership unavailable');
  assert(role(owner(),'owner-status').textContent.includes('Read fresh targets and review the full affected campaigns.'),'concrete membership recovery');
  assert(!role(owner(),'owner-include')||role(owner(),'owner-include').disabled,'no incomplete owner inclusion');
 }else{
  assert(discovery.status==='available'&&discovery.owners.length===1,'exact shared owner discovered');
  const option=discovery.owners[0];assert(option.affected_campaigns.length===2,'complete affected members');
  assert(option.affected_campaigns.every(t=>t.account.account_id===cfg.account_id),'exact account members');
  change(role(owner(),'owner-option'),'0');change(role(owner(),'owner-scenario'),'alternative_1');
  change(role(owner(),'owner-requested'),'5','input');role(owner(),'owner-include').click();
  assert(owner().textContent.includes('Mug Campaign 1')&&owner().textContent.includes('Mug Campaign 2'),'both member labels');
 }
 $('save').click();
 if(cfg.journey==='positive'){await until(()=>settled()&&!$('pending').hidden,'unknown committed create');$('recover').click();}
 await until(()=>settled()&&$('editor').hidden&&!$('current').hidden,'owned saved inputs');
 assert(createPosts===1,'one create with stable receipt recovery');
 assert(Array.isArray(originalCreateBody.inputs.google_daily_budget_intents),'explicit V6 field');
 assert(originalCreateBody.inputs.google_daily_budget_intents.length===(cfg.journey==='partial'?0:1),'exact explicit inclusion');
 if(cfg.journey!=='partial'){
  const sent=originalCreateBody.inputs.google_daily_budget_intents[0],option=discovery.owners[0];
  for(const key of ['account_id','owner_selection_id','expected_observation_digest','expected_owner_facts_digest','currency','cadence','unit'])assert(sent[key]===option[key],'exact discovered owner field '+key);
  assert(sent.account_id===cfg.account_id&&sent.scenario_key==='alternative_1'&&sent.requested_amount_micros===5000000,'explicit account alternative and daily hypothesis');
  assert(!('owner_key' in sent)&&!('source_binding_digest' in sent),'request contains no resolved server fields');
 }
 $('generate').click();await until(()=>settled()&&generated!==null&&!$('document').hidden,'genuine owner version');
 assert(generatePosts===1,'one original generation');
 const documentValue=generated.document;assert(documentValue.policy_version==='inlet.descriptive-review.v6','exact private policy');
 const savedReviews=documentValue.google_budget_owner_review.reviews;
 assert(savedReviews.length===(cfg.journey==='partial'?0:1),'exact saved owner count');
 if(cfg.journey!=='partial'){
  const saved=savedReviews[0].intent,sent=originalCreateBody.inputs.google_daily_budget_intents[0];
  for(const key of Object.keys(sent))assert(saved[key]===sent[key],'saved original primitive '+key);
  const actualMembers=savedReviews[0].witness.affected_campaigns;
  assert(JSON.stringify(actualMembers)===JSON.stringify(discovery.owners[0].affected_campaigns),'exact saved original complete member set');
  assert(savedReviews[0].disposition==='investigate_only'&&savedReviews[0].application==='unavailable','saved no-apply disposition');
 }
 const proof=document.getElementById('google-owner-review');assert(proof&&!proof.hidden,'saved owner panel');
 assert(![...proof.querySelectorAll('button')].some(b=>/apply/i.test(b.textContent)),'no apply control');
 if(cfg.journey!=='partial')assert(proof.textContent.includes('Review Required — Not Qualified Against The Period Ceiling')&&proof.textContent.includes('Inlet will not apply these changes.')&&proof.textContent.includes('Mug Campaign 2'),'saved investigation and affected member');
 const plan=root+'/plans/'+created.plan_id;
 $('export').click();await until(()=>settled()&&downloaded!==null,'actual export');
 assert(downloaded.document_digest===generated.document_digest,'exact saved export');
 // Endpoint receipt replays use the exact original keys, never another generation.
 const receipt=await json(await native(root+'/plans/requests/generate/'+originalGenerateBody.request_key));
 assert(receipt.document_digest===generated.document_digest,'exact generation receipt');
 const history=await json(await native(plan+'/versions/1'));assert(history.document_digest===generated.document_digest,'exact historical version');
 if(cfg.journey==='positive'){
  $('edit').click();await until(()=>settled()&&!$('editor').hidden,'saved owner edit');
  const remove=role(owner(),'owner-remove');assert(remove,'explicit removal of saved hypothesis');remove.click();
  await readAlternative();checked($('replace-targets'),true);
  $('save').click();await until(()=>settled()&&$('editor').hidden&&revision!==null,'explicit V6 empty correction');
  assert(revision.input_revision===2,'CAS creates second input only');
 }
 if(cfg.journey==='complete_to_partial'){
  const originalDocument=canonical(documentValue),originalDigest=generated.document_digest;
  $('edit').click();await until(()=>settled()&&!$('editor').hidden,'saved owner edit for recovery');
  assert(owner().textContent.includes('Saved Or Changed Review — Reselect Before Saving'),'historical entry begins unready');
  role(owner(),'owner-remove').click();await readAlternative();
  discovery=null;role(owner(),'owner-discover').click();
  await until(()=>settled()&&discovery?.status==='available'&&role(owner(),'owner-option')?.options.length>1,'fresh complete discovery');
  const completeCatalog=structuredClone(catalog),completeDiscovery=structuredClone(discovery);
  change(role(owner(),'owner-option'),'0');change(role(owner(),'owner-scenario'),'alternative_1');
  change(role(owner(),'owner-requested'),'5','input');role(owner(),'owner-include').click();
  assert(owner().textContent.includes('Included Review')&&!owner().textContent.includes('Saved Or Changed Review'),'fresh unsaved review truly ready');
  assert(inputPosts===0,'no intermediate input save');
  const csrf=document.cookie.split('; ').find(v=>v.startsWith('__Host-inlet_csrf='));
  assert(csrf,'existing CSRF transport');
  await json(await native('/__fixture__/make-partial',{method:'POST',headers:{'X-CSRF-Token':decodeURIComponent(csrf.slice(csrf.indexOf('=')+1))}}));
  await readAlternative();discovery=null;role(owner(),'owner-discover').click();
  await until(()=>settled()&&discovery?.status==='unavailable'&&role(owner(),'owner-status').textContent.includes('Read fresh targets and review the full affected campaigns.'),'fresh partial discovery settled');
  assert(discovery.reason==='google_budget_owner_unavailable'&&discovery.owners.length===0,'exact partial owner refusal');
  assert(!role(owner(),'owner-include')||role(owner(),'owner-include').disabled,'incomplete owner cannot be included');
  assert(catalog.composite_digest!==completeCatalog.composite_digest,'fresh catalog commitment');
  for(const field of ['workspace_id','account_id','connection_id','connection_version','platform'])assert(catalog.native_observation[field]===completeCatalog.native_observation[field],'same owned native scope '+field);
  assert(owner().textContent.includes('Saved Or Changed Review — Reselect Before Saving')&&owner().textContent.includes('Requested Daily Hypothesis USD 5.000000 Per Day'),'previous live choice retained and invalidated');
  assert(owner().textContent.includes('Mug Campaign 1')&&owner().textContent.includes('Mug Campaign 2'),'original affected member labels retained');
  checked($('replace-targets'),true);$('save').click();
  await until(()=>settled()&&$('message').textContent.includes('Saved owner reviews require explicit removal and current reselection.'),'owner-specific save refusal');
  assert(!$('editor').hidden&&inputPosts===0,'blocked owner save has zero input POSTs');
  transition={complete_catalog:completeCatalog,complete_discovery:completeDiscovery,partial_catalog:structuredClone(catalog),partial_discovery:structuredClone(discovery),blocked_input_posts:inputPosts};
  role(owner(),'owner-remove').click();$('save').click();
  await until(()=>settled()&&$('editor').hidden&&revision!==null,'explicit removal after partial recovery');
  assert(inputPosts===1&&revision.input_revision===2,'only explicit removal commits one revision');
  const old=await json(await native(plan+'/versions/1'));
  const oldExport=await json(await native(plan+'/export?version=1'));
  assert(old.document_digest===originalDigest&&oldExport.document_digest===originalDigest,'historical digest immutable');
  assert(canonical(old.document)===originalDocument&&canonical(oldExport.document)===originalDocument,'original complete V1 document immutable');
  transition.historical=old;transition.historical_export=oldExport;transition.final_input_posts=inputPosts;
 }
 assert(document.cookie===sessionCookies,'original browser session retained');
 await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',document:documentValue,export:downloaded,create_posts:createPosts,generate_posts:generatePosts,fresh_reads:freshReads,transition})});
}catch(error){await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:String(error.message)})});}
