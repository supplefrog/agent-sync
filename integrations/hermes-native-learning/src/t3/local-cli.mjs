// SPDX-License-Identifier: AGPL-3.0-only
// Fixed local operation only. No MCP/server, provider dispatch, shell or caller attestation.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadConfiguration } from '../config.mjs';
import { executeLearningCommand } from '../commands.mjs';
import { readNativeView } from '../inline/host/native-session.mjs';
import { fixedLocalBinding,runFixedLocal,localCheck } from './fixed-local.mjs';
import { localPresentation } from './local-presentation.mjs';
const ENROLLMENT=fileURLToPath(new URL('../../t3/local-enrollment.json',import.meta.url));
function readBounded(fd) {
  const bytes=Buffer.alloc(65537);let count=0;
  while(count<bytes.length){const n=fs.readSync(fd,bytes,count,bytes.length-count,null);if(!n)break;count+=n;}
  localCheck(count<=65536,'local_input_too_large','Command exceeds64KiB; nothing executed.');
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(0,count)));
}
try {
  localCheck(process.argv.length===2,'invalid_local_input','No owner, path, config or lesson arguments accepted.');
  const enrollment=JSON.parse(fs.readFileSync(ENROLLMENT,'utf8'));
  localCheck(path.isAbsolute(enrollment.configFile??''),'invalid_local_enrollment','Operator enrollment must select an absolute configuration file.');
  const config=loadConfiguration(enrollment.configFile,{allowEmptyLessons:true});
  const binding=fixedLocalBinding(enrollment,config,process.env);
  const payload=readBounded(0);
  const result=runFixedLocal(binding,payload,executeLearningCommand);
  const {directive,...response}=result;
  if(payload.present) {
    try {response.nativePresentation=localPresentation(readNativeView(binding,{includeAnswerHistory:true}).view);}
    catch {response.nativePresentation={available:false,instruction:'State operation outcome is retained. Presentation failed; do not repeat a committed mutation. Read current view.'};}
  }
  response.localScope='One explicitly enrolled local lesson. CODEX labels are consistency only; authority is user command admission and filesystem permissions. No hostile same-user-shell isolation.';
  console.log(JSON.stringify(response));
}catch(error) {
  const safe=error.name==='FixedLocalError'||error.name==='StateError';
  console.log(JSON.stringify({ok:false,code:safe?error.code:'local_operation_failed',
    error:safe?error.message:'Local operation failed; preserve outcome and inspect before repeating.'}));
  process.exitCode=1;
}
