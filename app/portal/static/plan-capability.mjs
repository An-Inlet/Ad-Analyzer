// Descriptive server configuration only; never browser-selected authority.
export function planningCapability(value,workspaceId){
 const version=[1,2,3,4,5,6,7].find(v=>value?.policy_version===`inlet.descriptive-review.v${v}`&&value?.generator_version===`inlet.descriptive-planning.v${v}`);
 if(!version||value.schema_version!=='inlet.planning-capabilities.v1'||value.workspace_id!==workspaceId||value.advertising_writes_enabled!==false||value.spending_authority!=='none'||typeof value.selected_reporting_available!=='boolean'||value.selected_reporting_available!==(version>=4))throw Error('Planning availability could not be verified.');
 return version===7?{selected:true,creative:true,constraints:true}:version===6?{selected:true,creative:true,ownerReview:true}:{selected:version>=4,creative:version===5};
}
