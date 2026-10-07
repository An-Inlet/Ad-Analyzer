// Exact display values from owned server projections; never client-derived authority.
export const reportedBasis='operational_reported_efficiency_rule';
const reject=()=>{throw Error('Reported rule information could not be verified. Reload the available choices.');};
const decimal=v=>typeof v==='string'&&v.length<=150&&/^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$/.test(v);
const integer=v=>Number.isSafeInteger(v)&&v>0&&v<=1e15;
const seconds=v=>Number.isSafeInteger(v)&&v>0&&v<=86400;
const id=v=>typeof v==='string'&&/^[a-f0-9]{32}$/.test(v);
const direction=v=>['increase','decrease'].includes(v);
const hash=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const date=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v;
export function checkedRuleParameters(p){
 if(p?.schema_version!=='inlet.reported-rule-parameters-view.v1'||!direction(p.original_change)||!direction(p.favorable_direction)||!direction(p.unfavorable_direction)||!['neutral_band','weight','contribution_clamp','aggregate_clamp'].every(k=>decimal(p[k])&&Number(p[k])<=1)||!integer(p.maximum_nominal_adjustment_micros)||p.minimum_distinct_original_attempts!==1||!seconds(p.evidence_lifetime_seconds))reject();
 return p;
}
export function checkedRuleOption(p){
 if(p?.schema_version!=='inlet.reported-rule-automatic-option.v1'||!id(p.policy?.policy_id)||!Number.isSafeInteger(p.policy.revision)||p.policy.revision<1||typeof p.label!=='string'||!p.label.length||p.label.length>100||p.decision_basis!==reportedBasis||!hash(p.policy_digest)||!['contract_test','live'].includes(p.environment)||p.session_bound!==true||p.causal_lift!=='unavailable'||p.financial_qualification!=='checked_separately_before_each_change'||!seconds(p.lifetime_seconds)||!seconds(p.cadence_seconds))reject();
 checkedRuleParameters(p.rule_parameters);return p;
}
export function exactMicros(value,currency=''){
 if(!decimal(String(value)))reject();
 const [whole,fraction='']=String(value).split('.');
 const units=BigInt(whole)/1000000n;
 const tail=((BigInt(whole)%1000000n).toString().padStart(6,'0')+fraction).replace(/0+$/,'');
 return `${currency?currency+' ':''}${units}${tail?'.'+tail:''}`;
}
export function ruleParameterLines(p,currency=''){
 checkedRuleParameters(p);
 return [`Original Budget Change: ${p.original_change}`,`Favorable Direction: ${p.favorable_direction}; Unfavorable Direction: ${p.unfavorable_direction}`,`Neutral Band (Ratio): ${p.neutral_band}; Weight: ${p.weight}`,`Per-Observation Contribution Limit (Ratio): ${p.contribution_clamp}; Combined Limit (Ratio): ${p.aggregate_clamp}`,`Maximum Nominal Budget Adjustment: ${exactMicros(p.maximum_nominal_adjustment_micros,currency)}${currency?'':' currency units'}. This is not remaining spend or a new spending cap.`,`Minimum Distinct Original Attempts: ${p.minimum_distinct_original_attempts}; Evidence Lifetime: ${p.evidence_lifetime_seconds} seconds`];
}
export function checkedRuleBasis(b,d){
 if(b?.schema_version!=='inlet.reported-rule-basis-view.v1'||b.basis!==reportedBasis||b.label!=='Reported-efficiency rule'||b.spending_authority!=='none'||b.correction_status!=='as_observed_unsettled'||b.interpretation!=='configuration_associated_reported_efficiency_not_causal'||b.delivery_time!=='unavailable'||b.causal_lift!=='unavailable'||!['contract_test','live'].includes(b.environment)||!/^[A-Z]{3}$/.test(b.currency)||typeof b.account_timezone!=='string'||!b.account_timezone.length||b.account_timezone.length>64||b.original_attempt_count!==1||!Number.isSafeInteger(b.reported_completion_count)||b.reported_completion_count<4||b.reported_completion_count>16||!integer(b.nominal_before_micros)||!(b.nominal_after_micros===null||integer(b.nominal_after_micros))||b.proposed_delta_micros!==(b.nominal_after_micros===null?null:b.nominal_after_micros-b.nominal_before_micros)||!Number.isFinite(Date.parse(b.observed_at))||!(Date.parse(b.expires_at)>Date.parse(b.observed_at)))reject();
 checkedRuleParameters(b.rule_parameters);
 for(const w of [b.before,b.after])if(!w||!date(w.starts_on)||!date(w.ends_on)||w.ends_on<w.starts_on||(Date.parse(w.ends_on)-Date.parse(w.starts_on))/86400000>=56||!Array.isArray(w.missing_dates)||w.missing_dates.length>56||new Set(w.missing_dates).size!==w.missing_dates.length||!w.missing_dates.every(v=>date(v)&&v>=w.starts_on&&v<=w.ends_on)||typeof w.revisions_within_tolerance!=='boolean'||![w.spend_micros,w.conversions,w.reported_cpa_micros].every(v=>v===null||decimal(v)))reject();
 if(b.before.ends_on>=b.after.starts_on||d.evidence?.basis!==reportedBasis||d.evidence.correction_status!==b.correction_status||d.evidence.causal_lift!=='unavailable'||d.evidence.original_attempt_count!==b.original_attempt_count||d.evidence.reported_completion_count!==b.reported_completion_count||d.nominal_before_micros!==b.nominal_before_micros||d.nominal_after_micros!==b.nominal_after_micros||d.observed_at!==b.observed_at||d.expires_at!==b.expires_at)reject();
 return b;
}
export function ruleBasisLines(b){
 const window=(label,w)=>`${label}: ${w.starts_on} to ${w.ends_on}, inclusive (${b.account_timezone}). Reported Spend: ${w.spend_micros===null?'Unknown':exactMicros(w.spend_micros,b.currency)}; Conversions: ${w.conversions??'Unknown'}; Reported CPA: ${w.reported_cpa_micros===null?'Unknown':exactMicros(w.reported_cpa_micros,b.currency)}. Missing Dates: ${w.missing_dates.join(', ')||'None'}; Revisions Within Tolerance: ${w.revisions_within_tolerance?'Yes':'No'}.`;
 return ['Reported-Efficiency Rule',b.environment==='contract_test'?'Offline Contract Test — No Live Evidence':'Live Environment',`${b.reported_completion_count} Actual Report Completions From ${b.original_attempt_count} Original Attempt. These are not independent original experiments.`,window('Before',b.before),window('After',b.after),'As Observed And Unsettled: Later Corrections Can Change These Reports. Configuration-Associated Efficiency Does Not Establish Causal Lift. Delivery Time And Causal Lift Are Unavailable.',`Nominal Budget: ${exactMicros(b.nominal_before_micros,b.currency)} → ${b.nominal_after_micros===null?'No Proposed Change':exactMicros(b.nominal_after_micros,b.currency)}. Proposed Delta: ${b.proposed_delta_micros===null?'None':(b.proposed_delta_micros<0?'-':'+')+exactMicros(Math.abs(b.proposed_delta_micros),b.currency)}.`,...ruleParameterLines(b.rule_parameters,b.currency),`Observed: ${b.observed_at}; Expires: ${b.expires_at}. Fresh evidence and separate spending checks are required before any change.`];
}
