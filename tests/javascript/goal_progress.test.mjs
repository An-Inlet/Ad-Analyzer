import test from 'node:test';
import assert from 'node:assert/strict';
import {goalProgressRows, goalProgressReasons} from '../../app/portal/static/portal.mjs';
const window = {start:'2026-10-01',end:'2026-11-01',time_basis:'calendar_month',currency:'USD',time_zone:'America/New_York'};
const goal={id:'a'.repeat(32),revision:2,definition:{target_window:window,target_micros:100000000,store_id:'b'.repeat(32)}};
const value={schema_version:'inlet.goal-sales-progress.v1',workspace_id:1,goal_id:goal.id,revision:2,metric:'shopify_merchandise_net_sales_v1',status:'available_as_of',target_window:window,target_micros:100000000,store_id:'b'.repeat(32),currency:'USD',time_zone:'America/New_York',coverage:{starts_on:'2026-10-01',ends_on_exclusive:'2026-10-03',closed_day_count:2,extent:'partial_period'},net_sales_micros:-12500000,source_watermark:'2026-10-03T12:00:00Z',as_of:'2026-10-03T13:00:00Z',reasons:[],goal_achievement:'not_assessed',attribution:'unavailable',spending_authorized:false};
test('signed actual amounts and complete zero are preserved without achievement claims',()=>{
  let rows=Object.fromEntries(goalProgressRows(value,goal,1));
  assert.match(rows['Imported Net Sales'],/^-USD\s12\.50/);
  assert.match(rows['Measured Closed Days'],/end excluded.*America\/New_York/);
  assert.equal(rows['Goal Achievement'],'Not Assessed');
  rows=Object.fromEntries(goalProgressRows({...value,net_sales_micros:0},goal,1));
  assert.match(rows['Imported Net Sales'],/0\.00/);
  assert.equal(rows['Spending Permission'],'None');
});
test('unknown has no invented amount or day count',()=>{
  const rows=Object.fromEntries(goalProgressRows({...value,status:'unavailable',net_sales_micros:null,reasons:['stale_source']},goal,1));
  assert.equal(rows['Imported Net Sales'],'Unavailable');
  assert.equal(rows['Closed Day Count'],undefined);
  assert.match(goalProgressReasons(['stale_source']),/too old/);
  assert.doesNotMatch(goalProgressReasons(['<secret>']),/secret/);
});
test('other goal/revision/workspace, changed target, malformed numeric authority fail closed',()=>{
  for(const change of [{revision:3},{workspace_id:2},{goal_id:'c'.repeat(32)},{target_micros:1},{spending_authorized:true},{net_sales_micros:null},{net_sales_micros:Infinity},{net_sales_micros:2**54}]) assert.throws(()=>goalProgressRows({...value,...change},goal,1));
  assert.throws(()=>goalProgressRows({...value,status:'unavailable'},goal,1));
});
