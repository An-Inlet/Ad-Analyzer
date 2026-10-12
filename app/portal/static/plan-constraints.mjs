// Exact finite instruction display; server checks bind the input digest and production template.
const literal='No discount claims.';
const unresolved='Clarify this restriction; its meaning is not covered by the exact supported rule.';
const obligations=[
 'Use fixed neutral public copy; do not interpolate product names or asserted facts.',
 'Omit price, savings, discount and promotional offers from suggested public copy.',
 'Inspect image pixels, video, audio and destinations separately before customer approval.',
];
const fail=()=>{throw Error('The saved constraint interpretation could not be verified.');};
const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const text=v=>typeof v==='string'&&v.length>0&&v.length<=2000;
export function appendConstraintInterpretation(host,plan){
 const candidate=plan.policy_version==='inlet.descriptive-review.v7'&&plan.generator_version==='inlet.descriptive-planning.v7';
 const q=plan.constraint_interpretation;
 if(!candidate){if(plan.schema_version==='inlet.plan-version.v4'||q!==undefined||plan.policy_version==='inlet.descriptive-review.v7'||plan.generator_version==='inlet.descriptive-planning.v7')fail();return;}
 if(plan.schema_version!=='inlet.plan-version.v4'||!exact(q,['schema_version','advertising_writes_enabled','spending_authority','input_digest','original_constraints','entries','original_product_restrictions','product_entries','disposition','obligations','provenance'])||q.schema_version!=='inlet.constraint-interpretation.v1'||q.advertising_writes_enabled!==false||q.spending_authority!=='none'||q.provenance!=='customer_instruction_only'||typeof q.input_digest!=='string'||!/^[a-f0-9]{64}$/.test(q.input_digest))fail();
 let recognized=0,unknown=0;
 for(const [original,entries,expected,max] of [
   [q.original_constraints,q.entries,plan.inputs.constraints,30],
   [q.original_product_restrictions,q.product_entries,plan.inputs.creative?.product?.restrictions??[],20],
 ]){
   if(!Array.isArray(original)||original.length>max||!Array.isArray(entries)||entries.length!==original.length||JSON.stringify(original)!==JSON.stringify(expected))fail();
   original.forEach((value,i)=>{
     const e=entries[i];if(!text(value)||!exact(e,['source_index','original_text','rule','unresolved_reason'])||e.source_index!==i||e.original_text!==value)fail();
     if(value===literal){if(e.rule!=='exclude_discount_claims'||e.unresolved_reason!==null)fail();recognized++;}
     else{if(e.rule!==null||e.unresolved_reason!==unresolved)fail();unknown++;}
   });
 }
 const expected=unknown?'unresolved':recognized?'fully_recognized':'no_constraints';
 if(q.disposition!==expected||JSON.stringify(q.obligations)!==JSON.stringify(recognized?obligations:[])||!Array.isArray(plan.creative_composition?.proposals)||(unknown&&plan.creative_composition.proposals.length))fail();
 const doc=host.ownerDocument,section=doc.createElement('section');section.id='planning-constraint-interpretation';
 const add=(tag,value)=>{const n=doc.createElement(tag);n.textContent=value;section.append(n);};
 add('h3','Constraint Interpretation');
 add('p',unknown?'Creative Deferred — Clarify Unresolved Restrictions':recognized?'Listed Restrictions Recognized — Customer Review Still Required':'No Listed Restrictions — Customer Review Still Required');
 add('p','Exact finite rules for the listed global and product restrictions only. This does not assess image pixels, audio, rights or external asset compliance. Original product facts remain provenance, not approved copy.');
 for(const [label,entries] of [['Global Instruction',q.entries],['Product Restriction',q.product_entries]])for(const e of entries){add('h4',`${label} ${e.source_index+1}`);add('p',e.original_text);add('p',e.rule?'Recognized: Exclude Discount Claims':`Unresolved: ${e.unresolved_reason}`);}
 for(const obligation of q.obligations)add('p',obligation);
 add('p','No budget, excluded channel or asset, fixed allocation or production capacity was relaxed. Changes require an explicit customer input revision. Publication and spending are not authorized.');
 host.append(section);
}
