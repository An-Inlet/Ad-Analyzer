// Reporting periods are exact customer inputs, not provider-local date guesses.
const shape=/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(\d{1,6}))?(?:Z|[+-]\d{2}:\d{2})$/;
export function instantMicros(value){
  const match=typeof value==='string'&&shape.exec(value),milliseconds=Date.parse(value);
  if(!match||!Number.isSafeInteger(milliseconds)||value.startsWith('0000-')||new Date(value.slice(0,19)+'Z').toISOString().slice(0,19)!==value.slice(0,19))throw Error('The saved reporting time could not be verified.');
  return BigInt(milliseconds)*1000n+BigInt((match[1]??'').padEnd(6,'0').slice(3)||'0');
}
export function minuteValue(value){instantMicros(value);return new Date(value).toISOString().slice(0,16);}
function entered(value){
  if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)||value.startsWith('0000-'))throw Error('Enter reporting times in UTC.');
  const date=new Date(value+':00Z');
  if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,16)!==value)throw Error('Enter valid reporting times.');
  return date.toISOString();
}
function windowValue(start,end,saved,now){
  const starts_at=saved&&start===minuteValue(saved.starts_at)?saved.starts_at:entered(start);
  const ends_at_exclusive=saved&&end===minuteValue(saved.ends_at_exclusive)?saved.ends_at_exclusive:entered(end);
  if(instantMicros(starts_at)>=instantMicros(ends_at_exclusive)||instantMicros(ends_at_exclusive)>now)throw Error('Choose a completed past reporting period.');
  return{starts_at,ends_at_exclusive};
}
export function reportingPeriods({start,end,comparisonEnabled,comparisonStart,comparisonEnd,savedPrimary=null,savedComparison=null,now=Date.now()}){
  if(typeof comparisonEnabled!=='boolean'||!Number.isSafeInteger(now))throw Error('The reporting choices could not be verified.');
  const current=BigInt(now)*1000n,reporting_window=windowValue(start,end,savedPrimary,current);
  const comparison_window=comparisonEnabled?windowValue(comparisonStart,comparisonEnd,savedComparison,current):null;
  if(comparison_window&&instantMicros(comparison_window.ends_at_exclusive)>instantMicros(reporting_window.starts_at))throw Error('End the comparison period at or before the primary period starts.');
  return{reporting_window,comparison_window};
}
