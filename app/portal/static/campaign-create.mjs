// Browser draft composition only. Server-side mandate, membership and media checks remain authoritative.
export function draftDefinition(mandate, account, values, media) {
  if (!mandate || mandate.state !== 'approved' || mandate.paused || !account) throw new Error('Choose an approved, active simulation mandate and account.');
  if (!/^\d+(\.\d{1,6})?$/.test(values.budget)) throw new Error('Enter a budget with up to six decimal places.');
  const [whole, part = ''] = values.budget.split('.');
  const budget = Number(whole) * 1e6 + Number(part.padEnd(6, '0'));
  if (!Number.isSafeInteger(budget) || budget <= 0 || budget > 1e15) throw new Error('Enter a valid modeled exposure.');
  const starts = new Date(values.starts), ends = new Date(values.ends);
  if (!Number.isFinite(starts.getTime()) || !Number.isFinite(ends.getTime()) || starts >= ends) throw new Error('Choose an ordered start and end date.');
  const kinds = {google_ads: 'google_search_v1', meta_ads: 'meta_website_sales_image_v1', tiktok_ads: 'tiktok_website_conversion_video_v1'};
  if (!kinds[account.platform]) throw new Error('This advertising tool is unavailable.');
  const content = {kind: kinds[account.platform], objective: account.platform === 'tiktok_ads' ? 'website_conversion' : 'website_sales', name: values.name, landing_page: values.landing_page,
    audience: {countries: values.countries.split(',').map(x => x.trim()).filter(Boolean), languages: values.languages.split(',').map(x => x.trim()).filter(Boolean)}};
  if (account.platform === 'google_ads') {
    for (const name of ['headlines', 'descriptions', 'exact_keywords']) content[name] = values[name].split('\n');
  } else {
    if (!media || !(account.platform === 'tiktok_ads' ? media.mime === 'video/mp4' : ['image/jpeg','image/png'].includes(media.mime))) throw new Error('Choose validated media for this campaign type.');
    content.media = {media_id: media.media_id, sha256: media.sha256}; content.text = values.text; content.call_to_action = 'SHOP_NOW';
    if (account.platform === 'meta_ads') content.headline = values.headline;
  }
  return {account: structuredClone(account), mandate_id: mandate.id, mandate_revision: mandate.revision,
    currency: mandate.definition.currency, budget_micros: budget, starts_at: starts.toISOString(), ends_at: ends.toISOString(), content};
}

export async function boundedVideo(response) {
  if (!response.ok || response.headers.get('content-type')?.split(';')[0] !== 'video/mp4') throw new Error('Video unavailable');
  const reader = response.body.getReader(), chunks = []; let size = 0;
  try {
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      size += value.byteLength; if (size > 64 * 1024 * 1024) throw new Error('Video exceeds limit');
      chunks.push(value);
    }
    if (!size) throw new Error('Empty video');
    return new Blob(chunks, {type:'video/mp4'});
  } finally { await reader.cancel(); reader.releaseLock(); }
}
