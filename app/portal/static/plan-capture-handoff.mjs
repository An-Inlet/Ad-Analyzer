// Navigation hints are not reporting evidence or authority. The server validates saves.
export function parseCaptureHint(fragment){
  if(typeof fragment!=='string'||fragment.length>128)return null;
  const match=/^#inlet-capture-v1=([1-9][0-9]*):([1-9][0-9]*):([a-f0-9]{32})$/.exec(fragment);
  if(!match)return null;
  const workspaceId=Number(match[1]),accountId=Number(match[2]);
  return Number.isSafeInteger(workspaceId)&&Number.isSafeInteger(accountId)?Object.freeze({workspaceId,accountId,captureId:match[3]}):null;
}
export function captureHintPath(workspaceId,accountId,captureId){
  const fragment=`#inlet-capture-v1=${workspaceId}:${accountId}:${captureId}`;
  if(!parseCaptureHint(fragment))throw Error('The capture reference could not be verified.');
  return '/app/planning'+fragment;
}
export function captureHandoff(fragment,cookies){
  let hint=parseCaptureHint(fragment),bound=false,selected=false;
  const revoke=()=>{hint=null;};
  return{
    revoke,
    bind(workspaces,currentCookies){if(currentCookies!==cookies||!workspaces.some(w=>w.id===hint?.workspaceId&&w.role==='owner'))revoke();bound=true;},
    choose(workspaceId,currentCookies){if(!bound||selected||currentCookies!==cookies||workspaceId!==hint?.workspaceId)revoke();selected=true;},
    offered(workspaceId,currentCookies){if(currentCookies!==cookies)revoke();return bound&&selected&&hint?.workspaceId===workspaceId?hint:null;},
  };
}
