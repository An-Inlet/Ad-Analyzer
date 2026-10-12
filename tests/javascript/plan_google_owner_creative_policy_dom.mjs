import {appendCreativeBasis} from './plan-creative-basis.mjs';
import {renderPlanDocument} from './plan-document.mjs';
const host=document.querySelector('#host'),assert=(v,m)=>{if(!v)throw Error(m);},reject=(fn,m)=>{let bad=false;try{fn();}catch{bad=true;}assert(bad,m);};
try{
 const v5=await (await fetch('/creative-v5.json')).json(),v6=await (await fetch('/creative-v6.json')).json(),empty=await (await fetch('/creative-v6-empty.json')).json();
 for(const [version,plan] of [[5,v5],[6,v6],[6,empty]]){
  assert(plan.policy_version===`inlet.descriptive-review.v${version}`&&plan.generator_version===`inlet.descriptive-planning.v${version}`,'genuine exact composed DTO');
  renderPlanDocument(host,plan,{workspaceId:plan.inputs.workspace_id,planId:plan.inputs.plan_id,freshness:'current'},Date.parse(plan.generated_at));
  const basis=host.querySelector('#planning-creative-basis');assert(basis&&basis.textContent.includes('Customer-Supplied Statements')&&basis.textContent.includes('Images Are Not Visually Assessed'),'saved basis rendered through whole document');
  assert(basis.textContent.includes(`Supplied Images: ${plan.creative_proof.basis.images.length}`),'exact retained image count');
  for(const image of plan.creative_proof.basis.images)assert(basis.textContent.includes(image.observed_at),'original image observation');
  if(plan.inputs.creative.product)assert(basis.textContent.includes(plan.inputs.creative.product.name),'saved product name preserved');
  assert(!host.textContent.includes('undefined'),'no absent DTO field rendering');
  if(version===6)assert(host.querySelector('#google-owner-review')&&host.textContent.includes(plan.google_budget_owner_review.reviews.length?'Not Qualified Against The Period Ceiling':'No shared daily setting reviews were included'),'owner and creative panels coexist');
 }
 for(const [policy,generator] of [[5,6],[6,5],[4,6],[6,4],[7,7],[7,6],[6,7],[8,8],[1,1],[2,2],[3,3],[4,4]]){const plan=structuredClone(v6);plan.policy_version=`inlet.descriptive-review.v${policy}`;plan.generator_version=`inlet.descriptive-planning.v${generator}`;const target=document.createElement('div');reject(()=>appendCreativeBasis(target,plan),'mixed/unknown/legacy proof rejected');assert(!target.children.length,'invalid pair renders no basis');}
 for(let version=1;version<=4;version++){const plan={...v5,policy_version:`inlet.descriptive-review.v${version}`,generator_version:`inlet.descriptive-planning.v${version}`,creative_proof:null,creative_composition:null},target=document.createElement('div');appendCreativeBasis(target,plan);assert(!target.children.length,'legacy absent proof unchanged');}
 for(const kind of ['missing','workspace','requested']){const plan=structuredClone(v6);if(kind==='missing')plan.creative_proof=null;if(kind==='workspace')plan.creative_proof.basis.workspace_id++;if(kind==='requested')plan.creative_proof.basis.requested.media_selections=[];reject(()=>appendCreativeBasis(document.createElement('div'),plan),`V6 ${kind} binding rejected`);}
 await fetch('/result',{method:'POST',body:'PASS'});
}catch(error){await fetch('/result',{method:'POST',body:error.stack||String(error)});}
