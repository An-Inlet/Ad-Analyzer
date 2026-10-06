import test from 'node:test';
import assert from 'node:assert/strict';
import {micros, monthWindow, definitionFrom, billingDestination, request, baselineWarnings, goalSummary, amount, shopifyDestination, googleDestination} from '../../app/portal/static/portal.mjs';
const store = {id: 'a'.repeat(32), currency: 'USD', time_zone: 'America/New_York'};
test('currency conversion is exact and rejects malformed or unsafe values', () => {
  assert.equal(micros('100.10'), 100100000);
  assert.equal(micros('0'), 0);
  for (const value of ['-1', '1e9', '1.001', 'Infinity', '1000000001']) assert.throws(() => micros(value));
});
test('monthly goal preserves store currency/time zone and uses exclusive ends', () => {
  assert.deepEqual(monthWindow('2026-12', store), {start:'2026-12-01', end:'2027-01-01', time_basis:'calendar_month', currency:'USD', time_zone:'America/New_York'});
  const definition = definitionFrom({target_month:'2028-02', baseline_month:'2027-02', target:'500.01', budget:'100', budget_start:'2028-02-01', budget_end:'2028-03-01', aggressiveness:'balanced'}, store);
  assert.equal(definition.deadline, '2028-02-29');
  assert.equal(definition.target_micros, 500010000);
  assert.equal(definition.budget_micros, 100000000);
  assert.throws(() => monthWindow('2026-13', store));
  assert.throws(() => definitionFrom({}, null));
});
test('billing redirects reject fixtures, hostile origins, credentials and live modes', () => {
  assert.equal(billingDestination({mode:'stripe_test', url:'https://checkout.stripe.com/c/pay/test_123'}, 'checkout'), 'https://checkout.stripe.com/c/pay/test_123');
  for (const url of ['http://checkout.stripe.com/x','https://checkout.stripe.com.evil.test/x','javascript:alert(1)','https://evil@checkout.stripe.com/x','https://checkout.stripe.com:444/x','https://billing.stripe.com/x']) assert.throws(() => billingDestination({mode:'stripe_test',url}, 'checkout'));
  for (const mode of ['fixture','live','unavailable']) assert.throws(() => billingDestination({mode,url:'https://checkout.stripe.com/x'}, 'checkout'));
});
test('mutations attach CSRF and same-origin cookies, and refuse missing CSRF without calling fetch', async () => {
  let called = 0;
  const fetcher = async (path, options) => { called++; assert.equal(path, '/api/customer/v1/workspaces'); assert.equal(options.credentials, 'same-origin'); assert.equal(options.redirect,'error'); assert.equal(options.headers['X-CSRF-Token'], 'a'.repeat(43)); assert.equal(options.headers['Idempotency-Key'],'same-retry'); return {ok:true,status:201,json:async()=>({id:1})}; };
  await assert.rejects(request('/api/customer/v1/workspaces','POST',{}, {},fetcher,''));
  assert.equal(called,0);
  assert.deepEqual(await request('/api/customer/v1/workspaces','POST',{name:'Store'}, {'Idempotency-Key':'same-retry'}, fetcher, '__Host-inlet_csrf='+'a'.repeat(43)),{id:1});
  assert.equal(called,1);
});
test('API errors do not display provider payloads and conflicts stay conflicts', async () => {
  const fetcher = async () => ({ok:false,status:409,json:async()=>({detail:'secret-provider-payload'})});
  await assert.rejects(request('/api/customer/v1/workspaces','GET',undefined,{},fetcher), error => error.status === 409 && !error.message.includes('secret-provider'));
  await assert.rejects(request('//evil.test/api/customer/v1/workspaces','GET',undefined,{},fetcher));
});

test('summaries distinguish missing amounts and baseline history from zero sales', async () => {
  assert.equal(amount(null, 'USD'), 'Not Available');
  assert.match(amount(0, 'USD'), /0\.00/);
  assert.match(baselineWarnings(['missing_history'])[0], /missing.*baseline month/);
  assert.match(baselineWarnings(['incomplete_window'])[0], /not been fully imported/);
  assert.deepEqual(goalSummary(null), [['Goal', 'No Goal Definition Yet']]);
  const fetcher = async () => ({ok:false,status:409,json:async()=>({detail:{code:'baseline_unavailable',reasons:['missing_history','stale_source']}})});
  await assert.rejects(request('/api/customer/v1/workspaces','GET',undefined,{},fetcher), error => error.message.includes('Historical data is missing') && error.message.includes('too old') && !error.message.includes('stale_source'));
});

test('Shopify authorization destination stays at the exact merchant HTTPS consent endpoint', () => {
  const shop = 'store.myshopify.com';
  assert.equal(shopifyDestination({authorization_url:'https://store.myshopify.com/admin/oauth/authorize?state=fixture'}, shop), 'https://store.myshopify.com/admin/oauth/authorize?state=fixture');
  for (const url of ['http://store.myshopify.com/admin/oauth/authorize', 'https://other.myshopify.com/admin/oauth/authorize', 'https://store.myshopify.com.evil.test/admin/oauth/authorize', 'https://store.myshopify.com:444/admin/oauth/authorize', 'https://user@store.myshopify.com/admin/oauth/authorize', 'https://store.myshopify.com/other']) assert.throws(() => shopifyDestination({authorization_url:url}, shop));
  assert.throws(() => shopifyDestination({authorization_url:'https://evil.test/admin/oauth/authorize'}, 'https://evil.test'));
});

 test('Google consent destination requires exact configured client callback scope and query', () => {
  const origin = 'https://inlet.example';
  const config = {client_id:'fixture-client', redirect_uri:origin+'/api/customer/v1/google/callback'};
  const params = new URLSearchParams({client_id:config.client_id,redirect_uri:config.redirect_uri,response_type:'code',scope:'https://www.googleapis.com/auth/adwords',access_type:'offline',prompt:'consent',state:'a'.repeat(43)});
  const url = 'https://accounts.google.com/o/oauth2/v2/auth?'+params;
  assert.equal(googleDestination({authorization_url:url},config,origin),url);
  for (const altered of [url.replace('accounts.google.com','evil.example'),url.replace('fixture-client','other-client'),url+'&state=duplicate',url+'&extra=unapproved',url+'&constructor=unapproved',url.replace('adwords','userinfo'),url.replace('https%3A%2F%2Finlet.example','https%3A%2F%2Fevil.example')]) assert.throws(()=>googleDestination({authorization_url:altered},config,origin));
 });
