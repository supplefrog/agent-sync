// SPDX-License-Identifier: AGPL-3.0-only
// Single-purpose stdio MCP adapter using an explicitly selected existing SDK.
// Starting/configuring this process is a separate activation action.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
// Boundary loading is deferred until the opted-in entry observation is available.

export const APP_URI='ui://learnharness/lesson-v6.html';
const LEGACY_APP_URIS=new Set(['ui://learnharness/lesson.html','ui://learnharness/lesson-v2.html','ui://learnharness/lesson-v3.html','ui://learnharness/lesson-v4.html','ui://learnharness/lesson-v5.html']);
const schema=properties=>({type:'object',properties,additionalProperties:false,required:Object.keys(properties)});
const chat={type:'string',pattern:'^[A-Za-z0-9_-]{1,80}$'};
const genericObject={type:'object'};
const tool=(name,description,inputSchema,readOnly,visibility,app=false)=>({name,description,inputSchema,
  annotations:{readOnlyHint:readOnly,destructiveHint:false,idempotentHint:readOnly,openWorldHint:false},
  _meta:{ui:{visibility,...(app?{resourceUri:APP_URI}:{})}}});
export const TOOLS=[
  tool('learning_identity','Read the host-written native Codex thread ID for explicit private enrollment. No model-supplied identity.',schema({}),true,['model']),
  tool('learning_catalogue','Find enrolled lessons when the learner asks what they started or wants to continue a topic. Summarize the relevant results in chat.',schema({}),true,['model']),
  tool('learning_view','Show the current lesson card when the learner starts or continues learning. For a recap, use learning_command with op:view and answer in chat. In Codex, use nativePresentation.path when the app view is unavailable or to show a relevant interactive visual.',schema({chatId:chat}),true,['model','app'],true),
  tool('learning_input','Persist the exact genuine lh.t3 learner event, using host-written caller metadata. Never invent an answer.',
    schema({chatId:chat,kind:{enum:['teach','practice']},expectedRevision:{type:'integer',minimum:0},action:genericObject}),false,['model']),
  tool('learning_command','Run the bound lesson protocol. Use op:view to check progress without opening a card. Keep question details focused on information needed to answer. Put prior feedback in its own teacher reaction. Save teacher visuals with op:visual, id,title,format:html-fragment|svg,source,reveal:now|after-question,expectedRevision,authorship:host-agent. Context/commitments are teacher-only. Show the new question or feedback with learning_view.',
    schema({command:genericObject}),false,['model']),
  tool('learning_draft','Save the current unsent draft only after explicit app-user confirmation. Does not submit an answer.',
    schema({chatId:chat,key:{type:'string',maxLength:300},expectedVersion:{type:'integer',minimum:-1},baseRevision:{type:'integer',minimum:0},
      payload:{anyOf:[genericObject,{type:'null'}]}}),false,['app']),
  tool('learning_asset','Read a digest-bound artifact already attached to this owning lesson. No arbitrary file paths.',
    schema({chatId:chat,file:{type:'string',maxLength:200}}),true,['app']),
  tool('learning_artifact_source','Read one saved artifact for the existing T3 native visual publisher. No execution or model call is launched.',
    schema({chatId:chat,file:{type:'string',maxLength:200}}),true,['model']),
  tool('learning_drawing','View the learner drawing from a saved answer or practice response by message ID.',
    schema({chatId:chat,messageId:{type:'string',maxLength:100}}),true,['model']),
  tool('learning_practice_history','Read the preceding page of saved responses for this practice problem.',
    schema({chatId:chat,problemId:{type:'string',maxLength:100},before:{type:'string',maxLength:100},
      expectedRevision:{type:'integer',minimum:0}}),true,['app']),
  tool('learning_notation','Render authored SMILES, ABC or TikZ in an isolated local renderer.',
    schema({chatId:chat,family:{enum:['smiles','abc','tikz']},source:{type:'string',maxLength:16384}}),true,['app']),
  tool('learning_flashcards_view','Read flashcard decks and reveal a flashcard in the owning lesson.',
    schema({chatId:chat,request:genericObject}),true,['app']),
  tool('learning_flashcards','Save a deck, card or scheduled review for the learner.',
    schema({chatId:chat,request:genericObject}),false,['app']),
  tool('learning_coding_test','Run the current coding exercise’s tests with the learner’s submitted code.',
    schema({chatId:chat,promptId:{type:'string',maxLength:100},expectedRevision:{type:'integer',minimum:0},code:{type:'string',maxLength:8192}}),false,['app']),
];
const textResult=value=>({content:[{type:'text',text:JSON.stringify(value)}]});
function t3Result(value,showLesson=true) {
  const {directive,snapshot,...rest}=value;
  return {...rest,...(snapshot?{snapshot:{revision:snapshot.revision,projectionSha256:snapshot.projectionSha256}}:{}),
    ...(showLesson?{nextPresentationTool:'learning_view'}:{})};
}
export function handleLearningTool(boundary,request) {
  const {name,arguments:args={},_meta:meta}=request.params;
  if(name==='learning_identity') {
    if(args===null||typeof args!=='object'||Array.isArray(args)||Object.keys(args).length)throw new Error('Identity accepts no arguments.');
    return textResult({nativeThreadId:boundary.owner(meta)});
  }
  if(name==='learning_view') {
    const result=boundary.view(meta,args);
    return {...result,content:[{type:'text',text:JSON.stringify({nativePresentation:result.nativePresentation,
      instruction:'Use the lesson card in the existing conversation. Open a saved interactive demo when requested through the host’s native renderer. In Codex desktop, use nativePresentation.path when the app view is unavailable or for the requested interactive HTML visual. Call learning_view when the next question or feedback is ready.'})}]};
  }
  if(name==='learning_catalogue')return textResult({lessons:boundary.catalogue(meta,args)});
  if(name==='learning_input')return textResult(t3Result(boundary.input(meta,args)));
  if(name==='learning_command')return textResult(t3Result(boundary.command(meta,args),args.command?.op!=='view'));
  if(name==='learning_draft')return {...textResult({saved:true}),structuredContent:boundary.draft(meta,args)};
  if(name==='learning_asset') {
    const result={content:[{type:'text',text:'Verified saved artifact.'}],_meta:boundary.asset(meta,args)};
    if(Buffer.byteLength(JSON.stringify(result))>240*1024)throw Object.assign(new Error('Artifact exceeds app bridge limit.'),{code:'asset_too_large'});
    return result;
  }
  if(name==='learning_artifact_source')return textResult(boundary.asset(meta,args));
  if(name==='learning_drawing')return {content:[{type:'image',mimeType:'image/png',data:boundary.drawing(meta,args).toString('base64')}]};
  if(name==='learning_practice_history')return {...textResult('Earlier practice responses.'),structuredContent:boundary.practiceHistory(meta,args)};
  if(name==='learning_notation')return boundary.notation(meta,args).then(result=>({...textResult('Rendered notation.'),structuredContent:result}));
  if(name==='learning_coding_test')return boundary.codingTest(meta,args).then(result=>({...textResult('Coding test results.'),structuredContent:result}));
  if(name==='learning_flashcards_view'||name==='learning_flashcards') {
    const result=boundary.flashcards(meta,args,name==='learning_flashcards');
    return {...textResult('Flashcard result.'),structuredContent:result};
  }
  throw Object.assign(new Error('Unknown learning tool.'),{code:'unknown_tool'});
}
// Opt-in startup observation: fixed sibling receipt, no error messages, paths or payloads.
let startupPhase='not-entered';
let startupReceiptFd;
const startupErrorCodes=new Set(['ENOENT','EACCES','EPERM','ENOTDIR','EISDIR','EEXIST','ELOOP','EMFILE','ENFILE','ENOSPC','EIO','EBADF','ERR_MODULE_NOT_FOUND','MODULE_NOT_FOUND','ERR_PACKAGE_PATH_NOT_EXPORTED','ERR_INVALID_PACKAGE_CONFIG','ERR_INVALID_MODULE_SPECIFIER','ERR_UNKNOWN_FILE_EXTENSION','ERR_REQUIRE_ESM']);
function startupObservation(configFile,stage,error) {
  if(stage!=='failed')startupPhase=stage;
  if(process.env.LEARNHARNESS_STARTUP_DIAGNOSTIC!=='1')return;
  const safeCode=startupErrorCodes.has(error?.code)?error.code:null;
  const safeType=error instanceof Error&&['Error','TypeError','RangeError','SyntaxError','ReferenceError','StateError'].includes(error.name)?error.name:null;
  const record={stage,phase:startupPhase,code:safeCode,errorType:safeType};
  try {
    if(startupReceiptFd===undefined) {
      // O_EXCL rejects every existing leaf, including links; never truncate or reopen it.
      startupReceiptFd=null;
      startupReceiptFd=fs.openSync(path.join(path.dirname(fs.realpathSync(configFile)),
        'mcp-startup-diagnostic.ndjson'),'wx',0o600);
    }
    if(startupReceiptFd===null)return;
    // Keep the exclusively owned handle for this one process; append bounded stage records.
    fs.writeSync(startupReceiptFd,JSON.stringify(record)+'\n',null,'utf8');
  } catch {console.error('LearnHarness startup diagnostic receipt unavailable.');}
}
export async function start(configFile,sdkRoot) {
  startupObservation(configFile,'entry');
  const { T3LearningBoundary }=await import('./boundary.mjs');
  startupObservation(configFile,'boundary-module-loaded');
  if(!configFile||!sdkRoot)throw new Error('Pass --config <private enrollment> --sdk-root <existing SDK runtime>. No automatic installation.');
  const require=createRequire(path.join(fs.realpathSync(sdkRoot),'package.json'));
  const sdkDirectory=path.resolve(path.dirname(require.resolve('@modelcontextprotocol/sdk/server/index.js')),'../../..');
  const sdkPackage=JSON.parse(fs.readFileSync(path.join(sdkDirectory,'package.json'),'utf8'));
  if(sdkPackage.version!=='1.32.0')throw new Error('This source adapter selects MCP SDK1.32.0; review another version before activation.');
  const load=specifier=>import(pathToFileURL(path.join(sdkDirectory,'dist/esm',specifier)).href);
  const [{Server},{StdioServerTransport},types]=await Promise.all([
    load('server/index.js'),load('server/stdio.js'),load('types.js')]);
  startupObservation(configFile,'sdk-loaded');
  const boundary=new T3LearningBoundary(configFile);
  startupObservation(configFile,'boundary-loaded');
  const server=new Server({name:'learnharness-native',version:'0.1.0-dev'},{capabilities:{tools:{},resources:{}},
    instructions:'Existing agent remains teacher. Handle natural requests to find, resume or recap a lesson. Use learning_catalogue to find it. For a list or recap, use learning_command op:view as needed and answer in chat. Use learning_view when continuing the lesson or showing new feedback, in the existing conversation. Open a saved demo when requested. On a genuine lh.t3 message, call learning_input with those exact fields, then context/continue/teach/question through learning_command; return learning_view. Never copy an owner into env/arguments. No automatic provider or worker is part of this server.'});
  server.setRequestHandler(types.ListToolsRequestSchema,async()=>({tools:TOOLS}));
  server.setRequestHandler(types.CallToolRequestSchema,async request=>{
    try {return await handleLearningTool(boundary,request);}
    catch(error){return {isError:true,...textResult({ok:false,code:typeof error.code==='string'?error.code:'operation_failed',
      error:error.name==='StateError'?error.message:'Operation failed; preserve outcome and inspect before any repeat.'})};}
  });
  server.setRequestHandler(types.ListResourcesRequestSchema,async()=>({resources:[{uri:APP_URI,name:'LearnHarness learning controls',mimeType:'text/html;profile=mcp-app'}]}));
  server.setRequestHandler(types.ReadResourceRequestSchema,async request=>{
    if(request.params.uri!==APP_URI&&!LEGACY_APP_URIS.has(request.params.uri))throw new Error('Unknown static app resource.');
    const file=fileURLToPath(new URL('../../t3/app.html',import.meta.url)),stat=fs.statSync(file);
    if(!stat.isFile()||stat.size>5*1024*1024)throw new Error('Build the bounded static app resource before activation.');
    return {contents:[{uri:request.params.uri,mimeType:'text/html;profile=mcp-app',text:fs.readFileSync(file,'utf8'),
      _meta:{ui:{prefersBorder:true,csp:{connectDomains:[],resourceDomains:[],frameDomains:[]}}}}]};
  });
  startupObservation(configFile,'connecting');
  await server.connect(new StdioServerTransport());
  startupObservation(configFile,'connected');
  return server;
}
const cliArgs=process.argv.slice(2);
const hasStartupArguments=cliArgs.length===4&&cliArgs[0]==='--config'&&cliArgs[2]==='--sdk-root';
if(hasStartupArguments)startupObservation(cliArgs[1],'module-loaded');
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  if(!hasStartupArguments)throw new Error('Use --config <private file> --sdk-root <existing runtime>.');
  startupObservation(cliArgs[1],'entry-matched');
  start(cliArgs[1],cliArgs[3]).catch(error=>{startupObservation(cliArgs[1],'failed',error);console.error('Learning MCP startup failed; no automatic retry, installation or fallback.');process.exitCode=1;});
} else if(hasStartupArguments)startupObservation(cliArgs[1],'entry-mismatch');
