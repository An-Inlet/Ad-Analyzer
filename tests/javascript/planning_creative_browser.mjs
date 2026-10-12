const cfg=__CONFIG__, $=id=>document.getElementById('planning-'+id);
const assert=(value,message)=>{if(!value)throw Error(message);};
const native=window.fetch.bind(window);
const json=async response=>{assert(response.ok,'HTTP '+response.status);return response.json();};
const until=async(fn,message)=>{const end=Date.now()+35000;while(!fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(name,value)=>{$(name).value=value;$(name).dispatchEvent(new Event('change'));};
const checked=(node,value)=>{node.checked=value;node.dispatchEvent(new Event('change'));};
const settled=()=>!$('list-refresh').disabled;
const mediaPath=`/api/customer/v1/workspaces/${cfg.workspace_id}/media`;
const root=`/api/customer/v1/workspaces/${cfg.workspace_id}/planning/plans`;
let uploadPosts=0,creates=0;const exported=[];
const selected=()=>[...$('image-library').querySelectorAll('input[type=checkbox]:checked')];
const uploadFile=bytes=>{const transfer=new DataTransfer();transfer.items.add(new File([bytes],'mug.png',{type:'image/png'}));$('image-file').files=transfer.files;$('image-file').dispatchEvent(new Event('change'));};
try{
 await json(await native('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'q16-owner:creative-browser'})}));
 const originalCookies=document.cookie;
 window.fetch=async(...args)=>{if(String(args[0])===mediaPath&&args[1]?.method==='POST')uploadPosts++;return native(...args);};
 await import('/app/assets/planning.mjs');await until(()=>settled()&&$('workspace').options.length>1,'workspace list');
 assert(![...$('workspace').options].some(x=>Number(x.value)===cfg.foreign_workspace_id),'foreign workspace never offered');
 change('workspace',String(cfg.workspace_id));await until(()=>settled()&&!$('new').hidden,'owned plans');
 $('new').click();await until(()=>settled()&&!$('editor').hidden,'creative editor');
 assert(!$('creative-inputs').hidden,'private creative controls available');
 if(cfg.journey==='safety'){
  const foreign=await native(`/api/customer/v1/workspaces/${cfg.foreign_workspace_id}/media`);assert(foreign.status===404,'foreign media denied');
  assert(selected().length===0,'no image selected implicitly');
  uploadFile(new Uint8Array([1,2,3]));await new Promise(r=>setTimeout(r,50));assert(uploadPosts===0,'file choice alone sends nothing');
  $('image-upload').click();await until(()=>uploadPosts===1&&!$('image-upload').disabled&&$('image-status').textContent.length>0,'invalid image response');
  assert(selected().length===0,'failed upload cannot invent selection');assert(!$('image-preview').querySelector('img'),'failed upload no image preview');
  $('cancel').click();await until(()=>settled()&&$('editor').hidden,'cancel editor');
  let rotationStarted=false,replacementCompleted=false,libraryDelivered=false;
  window.fetch=async(...args)=>{
   const response=await native(...args);
   if(String(args[0])===mediaPath&&(args[1]?.method??'GET')==='GET'&&!rotationStarted){
    rotationStarted=true;assert(!settled(),'library request belongs to busy controller');
    await json(await native('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'q16-owner:creative-replacement'})}));
    assert(document.cookie!==originalCookies,'actual replacement changes browser session');replacementCompleted=true;
    libraryDelivered=true;return response;
   }
   return response;
  };
  $('new').click();await until(()=>replacementCompleted&&libraryDelivered&&settled()&&$('editor').hidden&&$('creative-inputs').hidden&&/session changed/i.test($('message').textContent),'late library rejected after completed same-owner session replacement');
  assert(!$('image-library')||!$('image-library').textContent,'late library not retained');
  await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',journey:cfg.journey,upload_posts:uploadPosts})});
 }else{
  const inputs=cfg.body.inputs;
  change('goal',inputs.goal_id);const account=$('accounts').querySelector(`input[value="${cfg.account_id}"]`);assert(account,'same native account');checked(account,true);
  $('milestone').value=inputs.milestone;$('product').value=inputs.product_offer;$('creative').value='1';
  change('start',new Date(inputs.reporting_window.starts_at).toISOString().slice(0,16));change('end',new Date(inputs.reporting_window.ends_at_exclusive).toISOString().slice(0,16));
  checked($('comparison-enabled'),true);change('comparison-start',new Date(inputs.comparison_window.starts_at).toISOString().slice(0,16));change('comparison-end',new Date(inputs.comparison_window.ends_at_exclusive).toISOString().slice(0,16));
  if(inputs.selected_reporting.length){const field=$('selected-captures').querySelector('input');assert(Number(field.dataset.captureAccount)===cfg.account_id,'same capture account');field.value=inputs.selected_reporting[0].capture_id;}
  checked($('include-product'),true);$('product-name').value='Reusable travel mug';$('list-price').value='25';$('price-currency').value='USD';$('product-facts').value='';$('product-restrictions').value='No approved health claims or testimonials.';
  const raw=await (await native('/__fixture__/mug.png')).arrayBuffer();uploadFile(raw);await new Promise(r=>setTimeout(r,50));assert(uploadPosts===0,'file choice does not upload');
  $('image-upload').click();await until(()=>uploadPosts===1&&selected().length===1&&$('image-status').textContent.includes('Image Uploaded And Selected'),'actual upload selects owned image');
  const row=$('image-library').querySelector(`[data-planning-media-id="${cfg.media_id}"]`);assert(row,'exact upload receipt image');
  const preview=[...row.querySelectorAll('button')].find(x=>x.textContent==='Preview Image');assert(preview,'preview control');preview.click();
  await until(()=>{const image=$('image-preview').querySelector('img');return image?.complete&&image.naturalWidth>0;},'actual private image preview');
  window.fetch=async(...args)=>{const response=await native(...args);if(String(args[0])===root&&args[1]?.method==='POST'){creates++;const sent=JSON.parse(args[1].body);assert(sent.inputs.creative.product.list_price.micros===25000000,'exact retail price');assert(sent.inputs.creative.media_selections[0].expected_sha256===cfg.media_sha256,'exact image commitment');if(cfg.journey==='google'&&creates===1){assert(response.ok,'committed input before lost response');throw TypeError('lost committed input response');}}return response;};
  $('save').click();
  if(cfg.journey==='google'){await until(()=>settled()&&!$('pending').hidden,'unknown input outcome');$('recover').click();}
  await until(()=>settled()&&$('pending').hidden&&!$('current').hidden&&$('editor').hidden,'saved exact input');assert(creates===1,'single create including recovery');
  $('generate').click();await until(()=>settled()&&!$('document').hidden&&$('document').textContent.includes('Plan Version 1'),'genuine v5 generation');
  assert($('creative-basis')&&!$('creative-basis').hidden,'visible retained creative basis');
  assert($('creative-basis').textContent.includes('Reusable travel mug'),'visible declared product');
  assert(/not assessed/i.test($('creative-basis').textContent),'visible unassessed boundary');
  const list=await json(await native(root)),path=root+'/'+list.items[0].plan_id;
  let downloaded=null;window.fetch=async(...args)=>{const response=await native(...args);if(String(args[0])===path+'/export?version=1'&&response.ok)downloaded=await response.clone().json();return response;};
  $('export').click();await until(()=>settled()&&downloaded!==null,'actual portal version download');const first=downloaded;exported.push(first);
  assert(first.document.policy_version==='inlet.descriptive-review.v5','genuine private service');
  assert(first.document.creative_proof.basis.images[0].sha256===cfg.media_sha256,'genuine private image witness');
  assert($('creative-basis').textContent.includes(first.document.creative_proof.basis.images[0].observed_at),'original observation time displayed');
  assert($('creative-basis').textContent.includes('List Price: USD 25')&&$('creative-basis').textContent.includes('Supplied Images: 1'),'visible exact declared price and image count');
  assert(first.document.creative_proof.basis.requested.product.list_price.micros===25000000,'saved exact price');
  if(cfg.capture_enabled){$('creative-basis').scrollIntoView({block:'start'});await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));await json(await native('/__fixture__/capture',{method:'POST'}));}
  if(cfg.journey==='google'){
   const selectedCount=$('document').textContent.match(/selected count ([0-9.]+) \(/);assert(selectedCount&&/^10(?:\.0+)?$/.test(selectedCount[1]),'exact selected count ten displayed');
   $('edit').click();await until(()=>settled()&&!$('editor').hidden,'edit retained product');
   assert($('product-name').value==='Reusable travel mug'&&$('list-price').value==='25','exact retained product fields');
   assert(selected().length===1,'retained ordered selection');$('milestone').value='Review the same evidence and supplied image again';
   $('save').click();await until(()=>settled()&&$('editor').hidden,'saved input revision');$('generate').click();await until(()=>settled()&&$('document').textContent.includes('Plan Version 2'),'second version');
   const old=await json(await native(path+'/export?version=1'));assert(old.document_digest===first.document_digest,'immutable v1 export');
   await json(await native('/__fixture__/remove-bytes',{method:'POST'}));
   const historical=await json(await native(path+'/export?version=1'));exported.push(historical);assert(historical.document_digest===first.document_digest,'byte loss does not rewrite history');
   $('edit').click();await until(()=>settled()&&!$('editor').hidden,'metadata still editable separately from bytes');
   let missingReads=0;window.fetch=async(...args)=>{const response=await native(...args);if(String(args[0])===mediaPath+'/'+cfg.media_id&&!response.ok)missingReads++;return response;};
   const missingRow=$('image-library').querySelector(`[data-planning-media-id="${cfg.media_id}"]`),missingPreview=[...missingRow.querySelectorAll('button')].find(x=>x.textContent==='Preview Image');missingPreview.click();
   await until(()=>missingReads===1&&!missingPreview.disabled&&$('image-status').textContent.length>0&&!$('image-preview').querySelector('img'),'missing byte preview fails honestly');
  }else{
   const production=first.document.creative_composition.proposals[0].production;
   assert(production.deliverable_status==='production_required'&&production.visual_assessment==='not_assessed','production and visual boundaries');
   assert(production.storyboard.length===(cfg.journey==='tiktok'?3:0),'reviewable social production');
   if(cfg.journey!=='q08')assert(JSON.stringify(first.document).includes('unsupported_selected_mapping'),'social report gap retained');
   if(cfg.journey==='q08'){
    const doc=first.document,proposal=doc.creative_composition.proposals[0],proof=proposal.empty_catalog_witness;
    assert(doc.inputs.total_ceiling_micros===0,'confirmed zero ceiling retained');
    assert(doc.evidence.every(ref=>ref.kind!=='reported_metrics')&&doc.selected_reporting_proof.accounts.every(account=>account.capture_pin===null),'unavailable reporting is not measured zero');
    assert($('document').textContent.includes('Planning ceiling: USD 0'),'zero ceiling displayed');
    assert(doc.inputs.goal.revision===cfg.body.inputs.goal_revision,'actual confirmed goal revision');
    assert(proposal.target_basis==='observed_empty_account'&&proof,'retained empty query proof');
    assert(proof.catalog_evidence.catalog.targets.length===0&&proof.catalog_evidence.catalog.native_observation.targets.length===0&&proof.catalog_evidence.catalog.metadata_observation.entities.length===0,'all observed query arrays empty');
    const prerequisite=doc.actions.find(action=>action.key===proof.prerequisite_action_key);
    assert(prerequisite?.kind==='investigate'&&proposal.action.prerequisites.includes(prerequisite.key),'real measurement prerequisite');
    assert(proposal.action.target.scope==='account'&&proposal.action.target.account.account_id===cfg.account_id,'same owned account preparation');
    assert(doc.scenarios.every(s=>s.ceiling_micros===0&&s.unallocated_micros===0&&s.allocations.length===0&&s.forecast===null),'no paid allocation or forecast');
    assert(doc.actions.every(a=>a.native_budget===null&&a.proposed_fields.length===0),'no native mutation proposal');
    assert($('document').textContent.includes(proposal.action.title)&&$('document').textContent.includes(proposal.action.manual_steps[0]),'account preparation displayed');
    assert($('document').textContent.includes(prerequisite.title),'measurement prerequisite displayed');
    const historical=await json(await native(path+'/export?version=1'));exported.push(historical);assert(historical.document_digest===first.document_digest,'exact zero-ceiling history export');
   }
  }
  assert(document.cookie===originalCookies,'original browser session preserved');
  await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',journey:cfg.journey,upload_posts:uploadPosts,creates,exported})});
 }
}catch(error){await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message})});}
