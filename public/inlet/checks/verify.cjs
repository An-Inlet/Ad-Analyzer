const {chromium}=require('playwright');
const fs=require('fs');const assert=require('node:assert/strict');
const path=require('node:path');const http=require('node:http');const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const block=fs.readFileSync(path.join(root,'Inlet-Squarespace-Code-v2.txt'),'utf8');
const html=fs.readFileSync(path.join(root,'Inlet-Page-Preview-v2.html'),'utf8');
assert(html.includes(block),'Preview must embed the identical block');
assert(!/salesforce/i.test(block),'No outdated Salesforce reference');
assert(!/<(?:html|head|body)(?:\s|>)/i.test(block),'Code Block must be a fragment');
for(const script of block.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(script[1]);
let browser, server;
(async()=>{
 server=http.createServer((req,res)=>{if(req.url==='/preview'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);}else{res.statusCode=404;res.end();}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port;
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,headless:true});
 const context=await browser.newContext({ignoreHTTPSErrors:true,reducedMotion:'reduce'});
 if(process.env.CHECK_EXTERNAL_ASSETS!=='1')await context.route('**/*',route=>route.request().url().startsWith('http://127.0.0.1:')?route.continue():route.abort());
 const page=await context.newPage();const errors=[],failed=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure().errorText}));page.on('request',r=>requests.push({url:r.url(),type:r.resourceType()}));
 const url=`http://127.0.0.1:${port}/preview`;
 await page.goto(url,{waitUntil:'networkidle'});
 const results={viewports:[],checks:[],externalImages:[]};
 for(const width of [320,390,768,1024,1440,1920]){
  await page.setViewportSize({width,height:1000});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow ${width}`);
  assert.equal(await page.locator('#inlet-page').count(),1);
  results.viewports.push({width,horizontalOverflow:false});

 }
 await page.setViewportSize({width:1440,height:1000});
 const initial=await page.locator('#inlet-goal-input').inputValue();
 const attack='<img src=x onerror="window.inletInjected=true">';
 await page.locator('#inlet-goal-input').fill(attack);
 assert.equal(await page.locator('[data-inl-goal-output]').textContent(),attack);
 assert.equal(await page.locator('[data-inl-goal-output] img').count(),0);
 assert.equal(await page.evaluate(()=>Boolean(window.inletInjected)),false);
 results.checks.push('Goal updates as inert text; injected HTML does not execute');
 for(const amount of ['500','15000','50000']){
  await page.locator('#inlet-budget-input').fill(amount);await page.locator('#inlet-budget-input').dispatchEvent('input');
  const expected=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(+amount);
  for(const mode of ['conservative','balanced','aggressive']){
   await page.locator(`input[name="inlet-pace"][value="${mode}"]`).check({force:true});
   assert.equal(await page.locator('[data-inl-cap-output]').textContent(),expected);
   assert.equal(await page.locator('#inlet-budget-value').textContent(),expected);
   assert.match(await page.locator('[data-inl-pace-title]').textContent(),new RegExp(mode,'i'));
  }
 }
 results.checks.push('All three modes retain selected $500/$15,000/$50,000 limits');
 await page.locator('[data-inl-reset]').click();
 assert.equal(await page.locator('#inlet-goal-input').inputValue(),initial);
 assert.equal(await page.locator('#inlet-budget-input').inputValue(),'10000');
 assert.equal(await page.locator('input[name="inlet-pace"]:checked').inputValue(),'balanced');
 results.checks.push('Reset restores original goal, $10,000 limit and Balanced');
 await page.locator('summary').filter({hasText:'Which platforms are planned?'}).click();
 assert.equal(await page.locator('details[open]').filter({hasText:'Omnisend'}).count(),1);
 const body=await page.locator('body').innerText();assert(!/Salesforce|final providers are not yet confirmed/.test(body));
 assert(body.includes('Integrations are not live'));
 await page.locator('summary').filter({hasText:'Do I need to create all-new ads?'}).click();
 assert((await page.locator('body').innerText()).includes('New campaigns and creative will require your review'));
 results.checks.push('FAQ opens and discloses current plan, early development and customer review');
 assert.match(await page.locator('.inl-access-action a').getAttribute('href'),/^mailto:Konner@aninlet.com\?/);
 assert.equal(await page.locator('form').count(),0);
 assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
 assert.equal(requests.filter(r=>['xhr','fetch','websocket'].includes(r.type)).length,0);
 results.checks.push('Email-only CTA; no forms, storage or fetch/XHR/WebSocket activity');
 await page.locator('a[href="#inlet-how"]').first().click();
 assert.equal(await page.evaluate(()=>document.activeElement.id),'inlet-how');
 results.checks.push('Reduced-motion in-page navigation moves keyboard focus');
 results.externalImages=await page.locator('img').evaluateAll(xs=>xs.map(x=>({alt:x.alt,loaded:x.complete&&x.naturalWidth>0,src:x.src})));
 // Deterministically verify failed-logo fallback, then recovery after a successful load.
 const logo=page.locator('.inl-logo-omnisend img');
 await logo.evaluate(image=>image.dispatchEvent(new Event('error')));
 const fallback=page.locator('.inl-logo-omnisend .inl-image-fallback');
 assert.equal(await fallback.innerText(),'Omnisend');
 assert.equal(await fallback.isVisible(),true);
 await logo.evaluate(image=>image.dispatchEvent(new Event('load')));
 assert.equal(await fallback.isVisible(),false);
 await logo.evaluate(image=>image.dispatchEvent(new Event('error')));
 results.checks.push('Failed images show readable names; load recovery restores real image');
 // Embed the identical block in a synthetic Squarespace parent to test font/logo inheritance.

 await page.setContent('<!doctype html><html><head><style>h1{font-family:Georgia;font-weight:500}p{font-family:Verdana;font-weight:400}</style></head><body><header id="header" class="header"><div class="header-title-logo"><img alt="An Inlet" src="/existing-owner-logo.png"></div></header><div class="sqs-block">'+block+'</div></body></html>');
 assert.match(await page.locator('#inlet-page').evaluate(e=>getComputedStyle(e).getPropertyValue('--inl-display')),/Georgia/);
 assert.match(await page.locator('#inlet-page').evaluate(e=>getComputedStyle(e).getPropertyValue('--inl-sans')),/Verdana/);
 assert.equal(await page.locator('.inl-parent-logo').evaluateAll(xs=>xs.every(x=>x.getAttribute('src')==='/existing-owner-logo.png')),true);
 results.checks.push('Squarespace harness inherits parent heading/body fonts and existing owner logo URL');
 const nojs=await browser.newContext({javaScriptEnabled:false,ignoreHTTPSErrors:true});await nojs.route('**/*',route=>route.request().url().startsWith('http://127.0.0.1:')?route.continue():route.abort());const staticPage=await nojs.newPage();await staticPage.goto(url,{waitUntil:'domcontentloaded'});
 assert.equal(await staticPage.locator('h1').count(),1);assert.equal(await staticPage.locator('details').count(),4);assert.match(await staticPage.locator('.inl-access-action a').getAttribute('href'),/^mailto:/);
 results.checks.push('JavaScript-disabled content, FAQs and email CTA remain available');
 assert.equal(errors.length,0);results.scriptErrors=errors;results.failedRequests=failed;

 console.log(JSON.stringify({viewports:results.viewports,checks:results.checks,scriptErrors:errors,imagesLoaded:results.externalImages.filter(x=>x.loaded).length,totalImages:results.externalImages.length},null,2));
 await browser.close();server.close();
})().catch(async e=>{console.error(e);if(browser)await browser.close();if(server)server.close();process.exitCode=1;});
