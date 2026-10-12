import {renderPlanDocument} from './plan-document.mjs';
const assert=(ok,message)=>{if(!ok)throw Error(message);};
try{
 const documents=await(await fetch('/constraint-documents.json')).json(),host=document.querySelector('#host');
 for(const [index,doc] of documents.entries()){
   const options={workspaceId:doc.inputs.workspace_id,planId:doc.inputs.plan_id,freshness:'current'};
   renderPlanDocument(host,doc,options,Date.parse(doc.generated_at));
   const section=host.querySelector('#planning-constraint-interpretation');
   assert(section?.textContent.includes(index?'Clarify Unresolved Restrictions':'Listed Restrictions Recognized'),'interpretation status');
   assert(section.textContent.includes('Global Instruction 1')&&section.textContent.includes('Product Restriction 1'),'distinct original sources');
   assert(section.textContent.includes('No discount claims.'),'original instruction');
   assert(host.textContent.includes('50% OFF! BUY NOW'),'retained original product provenance');
   assert(host.textContent.includes('Fixed Allocations And Unallocated Budget'),'fixed alternatives');
   assert(!host.querySelector('a,button,input,img,script'),'read-only safe text');
   assert(section.textContent.includes('not approved copy'),'explicit copy limitation');
   if(index)assert(host.textContent.includes('Do not use this image until rights are cleared.'),'unknown exact original');
   else assert(host.textContent.includes('Explore the product.'),'neutral hook');
   for(const change of [
     d=>{d.schema_version='inlet.plan-version.v3';},
     d=>{delete d.constraint_interpretation;},
     d=>{d.constraint_interpretation.entries[0].source_index=2;},
     d=>{d.constraint_interpretation.original_constraints=[];},
     d=>{d.constraint_interpretation.product_entries[0].original_text='Allowed';},
     d=>{d.constraint_interpretation.obligations=[];},
     d=>{d.constraint_interpretation.spending_authority='approved';},
     d=>{d.constraint_interpretation.disposition='no_constraints';},
     d=>{d.generator_version='inlet.descriptive-planning.v5';},
   ]){
     const bad=structuredClone(doc);change(bad);
     try{renderPlanDocument(host,bad,options);throw Error('accepted corrupt constraints');}
     catch(error){assert(error.message!=='accepted corrupt constraints','rejected corrupt constraints');}
     assert(host.hidden&&!host.childNodes.length,'entire document cleared');
   }
 }
 const literal=structuredClone(documents[1]),p=literal.constraint_interpretation;
 const unsafe='<img src=x onerror="window.injected=true">';
 literal.inputs.constraints[1]=unsafe;p.original_constraints[1]=unsafe;p.entries[1].original_text=unsafe;
 renderPlanDocument(host,literal,{workspaceId:literal.inputs.workspace_id,planId:literal.inputs.plan_id,freshness:'current'});
 assert(host.textContent.includes(unsafe)&&!host.querySelector('img,script')&&!window.injected,'literal unknown safely rendered');
 document.querySelector('#result').textContent='PASS';
}catch(error){document.querySelector('#result').textContent='FAIL '+error.stack;}
await fetch('/result',{method:'POST',body:document.querySelector('#result').textContent});
