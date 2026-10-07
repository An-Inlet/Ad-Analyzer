const realFetch=globalThis.fetch;
let signed=false, lost=false, exchanges=0;
const sleep=()=>new Promise(r=>setTimeout(r,20));
async function until(check){for(let n=0;n<150;n++){if(check())return;await sleep();}throw Error('DOM state timed out');}
const assert=(v,m)=>{if(!v)throw Error(m);};
globalThis.fetch=async(path,options={})=>{
 if(path.endsWith('auth-config'))return Response.json({enabled:true,providers:['google.com'],firebase:{projectId:'inlet-test',authDomain:'inlet-test.firebaseapp.com'}});
 if(path.endsWith('/session')){
   if(options.method==='POST'){exchanges++;assert(JSON.parse(options.body).id_token==='fixture-token','wrong exchange');signed=true;if(lost)throw Error('lost');return Response.json({user_id:'new-user'});}
   if(options.method==='DELETE'){signed=false;return new Response(null,{status:204});}
   return Response.json({user_id:'new-user'}, {status:signed?200:401});
 }
 if(path.endsWith('/workspaces'))return Response.json([]);
 throw Error('Unexpected request '+path);
};
try{
 await import('/app/assets/portal.mjs');
 const $=id=>document.getElementById(id);
 await until(()=>!$('signin').hidden && !$('signin').disabled);
 $('signin').click();await until(()=>!$('application').hidden);
 assert(exchanges===1,'one exchange');assert(globalThis.sdkClears===1,'SDK cleared');
 assert(localStorage.length===0 && sessionStorage.length===0,'identity was persisted');
 document.cookie='__Host-inlet_csrf='+'a'.repeat(43); // browser rejects insecure __Host; mocked logout ignores header.
 // Provide a cookie getter for the offline fixture; production cookies remain server-owned.
 Object.defineProperty(document,'cookie',{configurable:true,get:()=>'__Host-inlet_csrf='+'a'.repeat(43)});
 $('logout').click();await until(()=>!$('logout').disabled&&$('application').hidden);
 lost=true;$('signin').click();await until(()=>!$('signin').disabled && $('message').textContent.includes('outcome'));
 assert($('application').hidden,'lost exchange must not expose customer DOM');
 assert(exchanges===2&&globalThis.sdkClears===2,'lost exchange replay or uncleared SDK');
 $('retry').click();await until(()=>!$('application').hidden);
 assert(exchanges===2,'explicit session check must not replay exchange');
 // Exercise the actual shipped SDK initialization without a provider or credentials.
 const realSDK=await import('/app/assets/firebase-bundle.mjs');
 const app=realSDK.initializeApp({projectId:'inlet-test',apiKey:'fixture-public-key',appId:'1:123:web:abc'},'offline-persistence-check');
 const auth=realSDK.initializeAuth(app,{persistence:realSDK.inMemoryPersistence});
 await auth.authStateReady();
 assert(auth.currentUser===null,'unexpected persisted SDK identity');
 assert(auth.persistenceManager.persistence.type==='NONE','SDK persistence is not in-memory');
 await realSDK.signOut(auth);await realSDK.deleteApp(app);
 await realFetch('/__result__',{method:'POST',body:'passed'});
}catch(error){await realFetch('/__result__',{method:'POST',body:String(error.stack)});}
