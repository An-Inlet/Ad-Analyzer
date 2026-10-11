import {imageMetadata} from './plan-creative-inputs.mjs';
// Render the saved observation, never substitute today's media metadata or bytes.
export function appendCreativeBasis(host,plan){
 const v5=plan.policy_version==='inlet.descriptive-review.v5'&&plan.generator_version==='inlet.descriptive-planning.v5';
 if(!v5){if(plan.creative_proof!=null||plan.creative_composition!=null)throw Error('Creative basis does not match the planning policy.');return;}
 const basis=plan.creative_proof?.basis,input=plan.inputs.creative;
 if(!basis||!input||!plan.creative_composition||basis.workspace_id!==plan.inputs.workspace_id||JSON.stringify(basis.requested)!==JSON.stringify(input)||!Array.isArray(basis.images)||basis.images.length>30||basis.images.length!==input.media_selections.length)throw Error('The saved creative basis could not be verified.');
 const doc=host.ownerDocument,section=doc.createElement('section');section.id='planning-creative-basis';const add=(tag,value)=>{const n=doc.createElement(tag);n.textContent=value;section.append(n);};
 add('h3','Saved Product And Image Basis');add('p','Customer-Supplied Statements — Claim Review Required. Images Are Not Visually Assessed. Workspace Ownership Does Not Establish Usage Rights.');
 const product=basis.requested.product;
 if(product){add('h4',product.name);if(product.list_price){const p=product.list_price;if(!Number.isSafeInteger(p.micros)||p.micros<0||p.micros>1e15||!/^[A-Z]{3}$/.test(p.currency))throw Error('Invalid saved list price.');add('p',`List Price: ${p.currency} ${Math.floor(p.micros/1e6)}.${String(p.micros%1e6).padStart(6,'0')}`);}for(const[heading,key]of[['Customer-Asserted Facts','customer_asserted_facts'],['Product Restrictions','restrictions']]){if(!Array.isArray(product[key])||product[key].length>20)throw Error('Invalid saved product details.');add('h4',heading);for(const item of product[key])add('p',item);}}
 else add('p','No Structured Product Details Supplied.');
 add('p',`Supplied Images: ${basis.images.length}`);
 basis.images.forEach((image,index)=>{const requested=input.media_selections[index];if(!imageMetadata(image)||image.workspace_id!==basis.workspace_id||image.media_id!==requested.media_id||image.sha256!==requested.expected_sha256||image.visual_assessment!=='not_assessed'||!Number.isFinite(Date.parse(image.observed_at)))throw Error('Invalid saved image observation.');add('p',`Image ${index+1}: ${image.mime} · ${image.width} × ${image.height} · Observed ${image.observed_at} · Visual Content Not Assessed.`);});
 host.append(section);
}
