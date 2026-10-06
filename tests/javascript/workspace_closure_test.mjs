import assert from 'node:assert/strict';
import {receiptPath,localReceiptConfirmed} from '../../app/portal/static/workspace-closure.mjs';
assert.deepEqual(receiptPath('/app/workspace-closure/12/'+'a'.repeat(32)),{workspace_id:12,request_id:'a'.repeat(32)});
for (const path of ['/app/workspace-closure/0/'+'a'.repeat(32),'/app/workspace-closure/12/evil','https://foreign.invalid/app/workspace-closure/12/'+'a'.repeat(32),'/app/workspace-closure/9007199254740992/'+'a'.repeat(32)]) assert.equal(receiptPath(path),null);
const row={schema_version:'inlet.lifecycle.request.v1',state:'blocked',revision:2,closed:false,data_erased:false,provider_actions_verified:false};
assert(localReceiptConfirmed(row));
for (const delta of [{revision:1},{revision:3},{schema_version:'unknown'},{state:'requested'},{closed:true},{data_erased:true},{provider_actions_verified:true}]) assert(!localReceiptConfirmed({...row,...delta}));
