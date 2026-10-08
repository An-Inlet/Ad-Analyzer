// Display-only V2 catalog renderer. Server-side ownership checks remain authoritative.
const platforms={google_ads:'Google Ads',meta_ads:'Meta Ads',tiktok_ads:'TikTok Ads'};
const kinds={campaign:'Campaign',adset:'Ad Set',adgroup:'Ad Group'};
const scopes={provider_campaigns:'Provider Campaigns',provider_adgroups:'Provider Ad Groups',sdk_known_effective_statuses:'Known Effective Statuses Only',regular_campaign_families:'Regular Campaign Families Only',not_collected:'Not Collected'};
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const id=value=>typeof value==='string'&&/^[0-9]{1,32}$/.test(value);
const stamp=value=>new Date(value).toLocaleString(undefined,{timeZone:'UTC'})+' UTC';
const fail=()=>{throw new Error('The native target response could not be verified. Read again when ready.');};
const text=(doc,tag,value)=>{const node=doc.createElement(tag);node.textContent=String(value);return node;};
export function clearNativeTargets(host){host.replaceChildren();host.hidden=true;}
export function renderNativeTargets(host,result,{workspaceId,account,period},now=Date.now()){
  clearNativeTargets(host);
  const n=result?.native_observation,m=result?.metadata_observation,targets=result?.targets;
  if(result?.schema_version!=='inlet.planning-target-catalog.v2'||result.advertising_writes_enabled!==false||result.spending_authority!=='none'||result.atomic_snapshot!==false||!digest(result.composite_digest)||!n||!m||!Array.isArray(targets)||targets.length>400||!Object.hasOwn(platforms,account.platform))fail();
  for(const observation of [n,m]){
    if(observation.workspace_id!==Number(workspaceId)||observation.account_id!==account.id||observation.platform!==account.platform||!Number.isSafeInteger(observation.connection_id)||observation.connection_id<=0||typeof observation.connection_version!=='string'||!observation.connection_version.length||observation.connection_version.length>100||!digest(observation.source_binding_digest)||observation.atomic_snapshot!==false)fail();
    const start=Date.parse(observation.observation_started_at),observed=Date.parse(observation.observed_at),expires=Date.parse(observation.expires_at);
    if(![start,observed,expires].every(Number.isFinite)||start>observed||observed>now||now>=expires||Date.parse(observation.reporting_starts_at)!==Date.parse(period.starts_at)||Date.parse(observation.reporting_ends_at)!==Date.parse(period.ends_at)||Date.parse(period.ends_at)>start)fail();
  }
  if(n.schema_version!=='inlet.planning-target-catalog.v1'||m.schema_version!=='inlet.planning-entity-metadata.v1'||n.connection_id!==m.connection_id||n.connection_version!==m.connection_version||n.source_binding_digest!==m.source_binding_digest||n.inventory_digest!==m.native_inventory_digest||Date.parse(m.observation_started_at)<Date.parse(n.observed_at)||!digest(n.inventory_digest)||!digest(m.request_digest)||Date.parse(result.expires_at)!==Math.min(Date.parse(n.expires_at),Date.parse(m.expires_at))||!Array.isArray(n.targets)||n.targets.length>400||!Array.isArray(m.entities)||m.entities.length!==targets.length)fail();
  const allowed=['campaign',account.platform==='meta_ads'?'adset':'adgroup'];
  const keys=new Set(),canonicalKeys=new Set(),nativeKeys=new Set(),entityKeys=new Set(),parents=new Set(),advertisers=new Set();
  for(const row of n.targets){if(!row||!allowed.includes(row.kind)||!digest(row.selection_key)||nativeKeys.has(row.selection_key))fail();nativeKeys.add(row.selection_key);}
  for(const row of targets){
    const e=row?.entity,r=e?.reference;
    if(!digest(row?.canonical_entity_key)||!digest(row.selection_key)||canonicalKeys.has(row.canonical_entity_key)||keys.has(row.selection_key)||!e||!r||!allowed.includes(e.kind)||r.platform!==account.platform||!id(r.advertiser_id)||!id(r.entity_id)||(r.platform==='google_ads'&&r.advertiser_id.length!==10)||((e.kind==='campaign')!==(r.parent_campaign_id===null))||(e.kind!=='campaign'&&!id(r.parent_campaign_id))||(row.native_settings_key!==null&&(!digest(row.native_settings_key)||!nativeKeys.has(row.native_settings_key))))fail();
    const observed=e.name_status==='observed';
    if(!['observed','missing','over_bound'].includes(e.name_status)||(observed?typeof e.name!=='string'||!e.name.length||e.name.length>160:e.name!==null))fail();
    for(const field of ['status','entity_type'])if(e[field]!==null&&(typeof e[field]!=='string'||!e[field].length||e[field].length>100))fail();
    const key=e.kind+':'+r.entity_id;if(entityKeys.has(key))fail();entityKeys.add(key);keys.add(row.selection_key);canonicalKeys.add(row.canonical_entity_key);advertisers.add(r.advertiser_id);if(e.kind==='campaign')parents.add(r.entity_id);
  }
  if(advertisers.size>1||targets.some(row=>row.entity.kind!=='campaign'&&!parents.has(row.entity.reference.parent_campaign_id))||JSON.stringify(targets.map(t=>t.entity))!==JSON.stringify(m.entities))fail();
  function coverage(observation,rows,metadata){
    if(!Array.isArray(observation.coverage)||observation.coverage.length!==2)fail();
    const seen=new Set();
    for(const c of observation.coverage){
      if(!c)fail();const count=metadata?c.count:c.observed_count;
      if(!allowed.includes(c.kind)||seen.has(c.kind)||!['complete','partial','unavailable'].includes(c.status)||!Object.hasOwn(scopes,c.scope)||!Number.isSafeInteger(count)||count<0||count>200||count!==rows.filter(r=>r.kind===c.kind).length||!Array.isArray(c.reasons)||c.reasons.length>20||c.reasons.some(reason=>typeof reason!=='string'||!(/^[a-z_]{1,100}$/).test(reason))||(c.status!=='complete'&&!c.reasons.length))fail();
      if(metadata){const expected=account.platform==='google_ads'?(c.kind==='campaign'?'provider_campaigns':'provider_adgroups'):account.platform==='meta_ads'?'sdk_known_effective_statuses':'regular_campaign_families';if(c.scope!==expected||c.status==='unavailable'||(account.platform!=='google_ads'&&c.status!=='partial'))fail();}
      else if(c.status==='complete'&&c.scope!=='provider_campaigns')fail();
      seen.add(c.kind);
    }
  }
  coverage(n,n.targets,false);coverage(m,m.entities,true);
  const doc=host.ownerDocument,fragment=doc.createDocumentFragment();
  fragment.append(text(doc,'h2','Native Targets'),text(doc,'p',`${account.name} · ${platforms[account.platform]}. Read-only observations; no ads or budgets were changed.`));
  const summary=doc.createElement('dl');
  for(const [label,value] of [['Requested Reporting Period',`${stamp(period.starts_at)} to ${stamp(period.ends_at)}`],['Native Settings Read',`${stamp(n.observation_started_at)} to ${stamp(n.observed_at)}`],['Names And Hierarchy Read',`${stamp(m.observation_started_at)} to ${stamp(m.observed_at)}`],['Expires At',stamp(result.expires_at)]])summary.append(text(doc,'dt',label),text(doc,'dd',value));
  fragment.append(summary,text(doc,'p','These separate reads are not an atomic snapshot. IDs identify your provider objects; they do not grant spending authority.'));
  for(const [label,observation,metadata] of [['Native Settings Coverage',n,false],['Names And Hierarchy Coverage',m,true]]){
    fragment.append(text(doc,'h3',label));const list=doc.createElement('ul');
    for(const c of observation.coverage)list.append(text(doc,'li',`${kinds[c.kind]}: ${c.status} · ${metadata?c.count:c.observed_count} found · ${scopes[c.scope]}${c.reasons.length?' · '+c.reasons.map(r=>r.replaceAll('_',' ')).join('; '):''}`));
    fragment.append(list);
  }
  const table=doc.createElement('table'),head=doc.createElement('thead'),header=doc.createElement('tr'),body=doc.createElement('tbody');
  for(const label of ['Name','Kind','Provider Account ID','Entity ID','Parent Campaign ID','Metadata Status / Type']){const th=text(doc,'th',label);th.scope='col';header.append(th);}head.append(header);
  for(const {entity:e} of targets){const row=doc.createElement('tr');for(const value of [e.name??(e.name_status==='over_bound'?'Name Unavailable — Exceeds Display Limit':'Name Unavailable — Not Returned'),kinds[e.kind],e.reference.advertiser_id,e.reference.entity_id,e.reference.parent_campaign_id??'—',[e.status,e.entity_type].filter(Boolean).join(' / ')||'Not Returned In Metadata'])row.append(text(doc,'td',value));body.append(row);}
  table.append(head,body);fragment.append(table);
  if(!targets.length)fragment.append(text(doc,'p','No targets were returned within the reported coverage. This does not establish zero spending.'));
  host.replaceChildren(fragment);host.hidden=false;return Date.parse(result.expires_at);
}
