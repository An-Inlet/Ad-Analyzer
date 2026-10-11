// Literal campaign labels retain the actual native identity when names collide.
export function ownerCampaignLabel(member){
 const id=member?.provider_reference?.entity_id;
 if(typeof id!=='string'||!/^[0-9]{1,32}$/.test(id))throw Error('Campaign reference unavailable.');
 const name=member.display_name;
 if(name!==null&&name!==undefined&&typeof name!=='string')throw Error('Campaign name unavailable.');
 return `${name??'Campaign Name Unavailable'} · Campaign ${id}`;
}
