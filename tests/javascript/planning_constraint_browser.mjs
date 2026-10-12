const cfg=__CONFIG__,$=id=>document.getElementById('planning-'+id),native=window.fetch.bind(window);
const assert=(v,m)=>{if(!v)throw Error(m);};
const json=async r=>{assert(r.ok,'HTTP '+r.status);return r.json();};
const until=async(f,m)=>{const end=Date.now()+35000;while(!f()){if(Date.now()>end)throw Error(m+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('change'));};
const check=(n,v)=>{n.checked=v;n.dispatchEvent(new Event('change'));};
const settled=()=>!$('list-refresh').disabled;
const root=`/api/customer/v1/workspaces/${cfg.workspace_id}/planning/plans`,media=`/api/customer/v1/workspaces/${cfg.workspace_id}/media`;
const mutations=[],exports=[],catalogs=[];let droppedCreate=false,droppedGenerate=false,path='',holdLibrary=false,held=false,released=false,release;
let rotateExport=false,rotated=false,blobCount=0,downloadCount=0;
const realBlob=URL.createObjectURL.bind(URL),realClick=HTMLAnchorElement.prototype.click;
URL.createObjectURL=value=>{blobCount++;return realBlob(value);};
HTMLAnchorElement.prototype.click=function(){if(this.download)downloadCount++;return realClick.call(this);};
const gate=new Promise(r=>{release=r;});
window.fetch=async(...args)=>{
 const url=String(args[0]),method=args[1]?.method??'GET';
 if(method==='POST'&&(url===root||url.endsWith('/inputs')||url.endsWith('/generate')||url.endsWith('/decisions')))mutations.push({url,body:JSON.parse(args[1].body)});
 const response=await native(...args);
 if(url.endsWith('/target-catalog-v2')&&response.ok)catalogs.push(await response.clone().json());
 if(url===media&&method==='GET'&&holdLibrary){holdLibrary=false;held=true;await gate;released=true;}
 if(url===root&&method==='POST'&&!droppedCreate){assert(response.status===201,'create committed');droppedCreate=true;throw TypeError('lost committed input response');}
 if(url.endsWith('/generate')&&method==='POST'&&!droppedGenerate){assert(response.ok,'generation committed');droppedGenerate=true;throw TypeError('lost committed generation response');}
 if(url.includes('/export?')&&response.ok){exports.push(await response.clone().json());if(rotateExport){rotateExport=false;await json(await native('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'q16-owner:constraint-replacement'})}));rotated=true;}}
 return response;
};
async function recover(label){await until(()=>settled()&&!$('pending').hidden,label+' unknown outcome');$('recover').click();await until(()=>settled()&&$('pending').hidden&&$('editor').hidden,label+' recovery');}
function submitTwice(){ $('save').click();$('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})); }
async function targets(replace=false){
 const before=catalogs.length;$('targets-read').click();await until(()=>settled()&&catalogs.length===before+1,'fresh target receipt');
 const catalog=catalogs.at(-1);
 for(const [nativeId,mode] of [['5','exclude'],['7','fixed']]){
  const target=catalog.targets.find(t=>t.entity.kind==='campaign'&&t.entity.reference.entity_id===nativeId);assert(target,'owned target '+nativeId);
  const field=[...$('targets').querySelectorAll('fieldset')].find(f=>f.dataset.targetKey===target.canonical_entity_key);assert(field,'target field');
  const choice=field.querySelector('[data-role=target-choice]');choice.value=mode;choice.dispatchEvent(new Event('change'));
  if(mode==='fixed'){const amount=field.querySelector('[data-role=target-amount]');amount.value='200';amount.dispatchEvent(new Event('input'));}
 }
 if(replace)check($('replace-targets'),true);
}
function preserved(doc){
 assert(doc.policy_version==='inlet.descriptive-review.v7'&&doc.generator_version==='inlet.descriptive-planning.v7'&&doc.schema_version==='inlet.plan-version.v4','exact configured version');
 assert(doc.inputs.total_ceiling_micros===1000000000&&doc.inputs.fixed_allocations.length===1&&doc.inputs.fixed_allocations[0].amount_micros===200000000,'ceiling and fixed allocation');
 const catalog=catalogs.at(-1),excluded=catalog.targets.find(t=>t.entity.kind==='campaign'&&t.entity.reference.entity_id==='5'),fixed=catalog.targets.find(t=>t.entity.kind==='campaign'&&t.entity.reference.entity_id==='7');
 assert(JSON.stringify(doc.inputs.fixed_allocations[0].target.provider_reference)===JSON.stringify(fixed.entity.reference)&&doc.inputs.fixed_allocations[0].target.selection_key===fixed.selection_key&&doc.inputs.excluded_entity_keys[0]===excluded.canonical_entity_key,'exact owned target references');
 assert(doc.inputs.creative.media_selections[0].media_id===cfg.media_id,'exact owned media identifier');
 assert(doc.inputs.accounts.length===1&&doc.inputs.accounts[0].account_id===cfg.account_id&&doc.inputs.excluded_entity_keys.length===1,'selected account and excluded campaign');
 assert(doc.inputs.maximum_creative_assets===1&&doc.inputs.creative.media_selections.length===1&&doc.inputs.creative.media_selections[0].expected_sha256===cfg.media_sha256,'capacity and exact selected asset');
 assert(doc.advertising_writes_enabled===false&&doc.spending_authority==='none'&&doc.actions.every(a=>a.native_budget===null&&a.proposed_fields.length===0),'manual only');
 assert(doc.actions.every(a=>!a.target.provider_reference||a.target.provider_reference.entity_id!=='5'&&a.target.provider_reference.parent_campaign_id!=='5'),'excluded campaign and children');
}
try{
 await json(await native('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'q16-owner:constraint-browser'})}));
 await import('/app/assets/planning.mjs');await until(()=>settled()&&$('workspace').options.length>1,'workspaces');
 change('workspace',String(cfg.workspace_id));await until(()=>settled()&&!$('new').hidden,'owned workspace');
 // A genuine owned library response arrives after the user leaves its workspace.
 holdLibrary=true;$('new').click();await until(()=>held,'library response held');change('workspace','');release();await until(()=>released&&settled(),'old response returned');await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
 assert($('editor').hidden&&$('creative-inputs').hidden&&$('constraint-help').hidden&&!$('accounts').children.length,'old workspace response cannot repopulate editor');
 change('workspace',String(cfg.workspace_id));await until(()=>settled()&&!$('new').hidden,'return owned workspace');$('new').click();await until(()=>settled()&&!$('editor').hidden,'candidate editor');
 assert(!$('creative-inputs').hidden&&document.getElementById('google-owner-inputs').hidden,'v7 creative without owner controls');
 assert(!$('constraint-help').hidden&&$('constraint-help').textContent.includes('Other wording stays saved and defers creative'),'honest finite instruction guidance');
 const input=cfg.body.inputs;change('goal',input.goal_id);check($('accounts').querySelector(`input[value="${cfg.account_id}"]`),true);
 $('milestone').value=input.milestone;$('product').value=input.product_offer;$('creative').value='1';
 change('start',new Date(input.reporting_window.starts_at).toISOString().slice(0,16));change('end',new Date(input.reporting_window.ends_at_exclusive).toISOString().slice(0,16));
 check($('comparison-enabled'),true);change('comparison-start',new Date(input.comparison_window.starts_at).toISOString().slice(0,16));change('comparison-end',new Date(input.comparison_window.ends_at_exclusive).toISOString().slice(0,16));
 check($('include-product'),true);$('product-name').value='Reusable travel mug';$('list-price').value='25';$('price-currency').value='USD';$('product-facts').value='SAVE 20 USD TODAY';$('product-restrictions').value='No discount claims.';
 const image=$('image-library').querySelector(`[data-planning-media-id="${cfg.media_id}"] input[type=checkbox]`);assert(image&&!image.checked,'no implicit image selection');check(image,true);
 $('constraints').value=Array(31).fill('Keep this instruction').join('\n');submitTwice();await until(()=>settled()&&$('message').textContent.includes('at most 30 entries'),'clear constraint validation');assert(mutations.length===0&&!$('editor').hidden,'invalid constraints never saved');
 $('constraints').value='No discount claims.';await targets();submitTwice();await recover('input');assert(mutations.filter(x=>x.url===root).length===1,'repeated create sent once');
 const listing=await json(await native(root));path=root+'/'+listing.items[0].plan_id;
 $('generate').click();$('generate').click();await recover('generation');assert(mutations.filter(x=>x.url.endsWith('/generate')).length===1,'repeated generate sent once');
 assert($('document').textContent.includes('Plan Version 1')&&$('document').textContent.includes('Listed Restrictions Recognized'),'recognized saved plan');
 let count=exports.length;$('export').click();await until(()=>settled()&&exports.length===count+1,'v1 portal export');const first=exports.at(-1);preserved(first.document);
 assert(first.document.constraint_interpretation.disposition==='fully_recognized'&&first.document.briefs.length===1&&first.document.briefs[0].hooks[0]==='Explore the product.','neutral supported copy');
 const creative=first.document.creative_composition.proposals[0].action;change('action',creative.key);change('record-type','deferred');$('statement').value='Review image rights before publication';check($('confirm-review'),true);$('record').click();$('review-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await until(()=>settled()&&$('message').textContent.includes('customer record was saved'),'exact action review');assert(mutations.filter(x=>x.url.endsWith('/decisions')).length===1,'single repeated review');
 $('edit').click();await until(()=>settled()&&!$('editor').hidden,'edit retained inputs');assert($('constraints').value==='No discount claims.'&&$('product-restrictions').value==='No discount claims.'&&$('product-facts').value==='SAVE 20 USD TODAY','original constraints and facts survive edit');
 assert($('generate').disabled&&$('review').hidden,'unsaved edit cannot generate or record');
 $('constraints').value+='\nDo not use images until rights are confirmed.';$('product-restrictions').value+='\nNo testimonials.';
 const before=mutations.length;submitTwice();await until(()=>settled()&&$('message').textContent.includes('explicitly confirm'),'target replacement required');assert(mutations.length===before,'old choices not silently removed');
 await targets(true);submitTwice();await until(()=>settled()&&$('editor').hidden,'revised inputs');assert(mutations.filter(x=>x.url.endsWith('/inputs')).length===1,'single revision');
 $('generate').click();$('generate').click();await until(()=>settled()&&$('document').textContent.includes('Plan Version 2'),'revised generation');assert(mutations.filter(x=>x.url.endsWith('/generate')).length===2,'single new version');
 assert($('document').textContent.includes('Clarify Unresolved Restrictions')&&$('document').textContent.includes('No testimonials.'),'clear preserved unknown deferrals');
 count=exports.length;$('export').click();await until(()=>settled()&&exports.length===count+1,'v2 portal export');const second=exports.at(-1);preserved(second.document);assert(second.document.parent_digest===first.document_digest&&second.document.constraint_interpretation.disposition==='unresolved'&&!second.document.briefs.length,'immutable lineage and deferred output');
 assert(second.document.inputs.creative.product.restrictions.join('\n')==='No discount claims.\nNo testimonials.','product unknown retained');
 change('version','1');await until(()=>settled()&&$('document').textContent.includes('Plan Version 1'),'historical selector');count=exports.length;$('export').click();await until(()=>settled()&&exports.length===count+1,'old portal export');assert(JSON.stringify(exports.at(-1).document)===JSON.stringify(first.document)&&exports.at(-1).document_digest===first.document_digest,'exact immutable history');
 $('events-refresh').click();await until(()=>settled()&&$('events').textContent.includes('Review image rights before publication'),'review history');
 // Delay a real export until a real replacement session has completed.
 const beforeBlob=blobCount,beforeDownload=downloadCount;rotateExport=true;$('export').click();await until(()=>rotated&&settled()&&$('selection').hidden,'stale export session refused');assert($('document').hidden&&!$('document').childNodes.length&&$('editor').hidden&&/session changed/i.test($('message').textContent),'session replacement clears prior display');
 assert(blobCount===beforeBlob&&downloadCount===beforeDownload,'stale export creates no blob or download');
 await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',journey:cfg.journey,exported:exports,mutations,stale_workspace_rejected:true,stale_session_rejected:true,stale_export_not_downloaded:true})});
}catch(error){await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack,mutations,exported:exports})});}
