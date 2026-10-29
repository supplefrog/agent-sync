// SPDX-License-Identifier: AGPL-3.0-only
// JSON stdin only. No server, provider dispatch, shell evaluation or auto-retry.
import fs from 'node:fs';
import { loadConfiguration, bindingForCaller } from './config.mjs';
import { executeLearningCommand } from './commands.mjs';
import { lessonCatalogue } from './catalogue.mjs';
try {
  const config=loadConfiguration(process.argv[2]);
  const raw=fs.readFileSync(0,'utf8').trim();
  if(Buffer.byteLength(raw)>65536) throw new Error('Input exceeds64KiB.');
  const command=raw.startsWith('lh.native ')?(()=>{const envelope=JSON.parse(raw.slice(10));return{op:'learner',chatId:envelope.chatId,envelope};})():JSON.parse(raw);
  if(command?.op==='list') {
    if(Object.keys(command).some(key=>key!=='op'))throw new Error('Lesson list accepts no paths, owner or transcript input.');
    console.log(JSON.stringify(lessonCatalogue(config,process.env)));
  } else {
    const binding=bindingForCaller(config,command.chatId,process.env);
    console.log(JSON.stringify(executeLearningCommand(binding,command)));
  }
}catch(error){console.log(JSON.stringify({ok:false,code:error.code??'invalid_input',error:error.message}));process.exitCode=1;}
