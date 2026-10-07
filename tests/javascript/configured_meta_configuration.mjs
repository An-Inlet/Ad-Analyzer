const $ = id => document.getElementById(id);
const pause = ms => new Promise(resolve => setTimeout(resolve,ms));
const assert = (ok, message) => { if (!ok) throw new Error(message); };
async function until(check, label) { for (let i=0;i<500;i++) { if (check()) return; await pause(40); } throw new Error(label + ': ' + $('social-message').textContent); }
const change = id => $(id).dispatchEvent(new Event('change'));
try {
  const login = await fetch('/api/customer/v1/session', {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'configured-meta:browser'})});
  assert(login.ok,'login');
  await import('/app/assets/social-configuration.mjs');
  await until(() => !$('social-select').hidden, 'session');
  $('social-workspace').value='__WORKSPACE__'; change('social-workspace');
  await until(() => [...$('social-draft').options].some(x=>x.value==='__DRAFT__'), 'owned drafts');
  assert(!document.querySelector('#social-workspace img'), 'workspace rendered literally');
  $('social-draft').value='__DRAFT__'; change('social-draft'); $('social-load').click();
  await until(() => !$('social-settings').hidden && !$('social-option').disabled, 'configuration');
  $('social-option').selectedIndex=1; change('social-option');
  if ('meta_ads' === 'meta_ads') {
    assert($('social-category').value === '', 'no inferred declaration');
    $('social-category').value='none_applicable'; change('social-category');
  } else {
    $('social-cover').selectedIndex=1; change('social-cover');
  }
  await until(() => !$('social-save').disabled, 'actual media decoded');
  if ('meta_ads' === 'tiktok_ads') {
    assert($('social-video').readyState>=2 && !$('social-video').error, 'actual video playable');
    assert($('social-cover-image').complete && $('social-cover-image').naturalWidth>0, 'actual cover decoded');
  }
  $('social-save').click();
  await until(() => !$('social-review').hidden && !$('social-ack').disabled, 'saved review');
  assert($('social-confirm').disabled, 'exact acknowledgement required');
  assert($('social-summary').textContent.includes('Modeled Lifetime Budget'), 'readable budget');
  assert($('social-summary').textContent.includes('Countries'), 'readable targeting');
  assert($('social-summary').textContent.includes('Campaign Period'), 'readable period');
  assert($('social-summary').textContent.includes('Contract Test'), 'honest environment');
  $('social-ack').checked=true; change('social-ack'); $('social-confirm').click();
  await until(() => $('social-message').textContent.includes('Confirmation Recorded'), 'exact confirmation');
  assert($('social-message').textContent.includes('No Ads Were Published'), 'no publication claim');
  location.assign('/__fixture__/execution');
} catch(error) { await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message})}); }
