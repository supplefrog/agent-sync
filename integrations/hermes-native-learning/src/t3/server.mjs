// SPDX-License-Identifier: AGPL-3.0-only
// Single-purpose stdio MCP adapter using an explicitly selected existing SDK.
// Starting/configuring this process is a separate activation action.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { T3LearningBoundary } from './boundary.mjs';

export const APP_URI='ui://learnharness/lesson.html';
const schema=properties=>({type:'object',properties,additionalProperties:false,required:Object.keys(properties)});
const chat={type:'string',pattern:'^[A-Za-z0-9_-]{1,80}$'};
const genericObject={type:'object'};
const tool=(name,description,inputSchema,readOnly,visibility,app=false)=>({name,description,inputSchema,
  annotations:{readOnlyHint:readOnly,destructiveHint:false,idempotentHint:readOnly,openWorldHint:false},
  _meta:{ui:{visibility,...(app?{resourceUri:APP_URI}:{})}}});
export const TOOLS=[
  tool('learning_identity','Read the host-written native Codex thread ID for explicit private enrollment. No model-supplied identity.',schema({}),true,['model']),
  tool('learning_catalogue','List only lessons enrolled for this authenticated native Codex thread.',schema({}),true,['model']),
  tool('learning_view','Open/resume the current redacted learning card. No model turn or learner mutation.',schema({chatId:chat}),true,['model','app'],true),
  tool('learning_input','Persist the exact genuine lh.t3 learner event, using host-written caller metadata. Never invent an answer.',
    schema({chatId:chat,kind:{enum:['teach','practice']},expectedRevision:{type:'integer',minimum:0},action:genericObject}),false,['model']),
  tool('learning_command','Run the existing bound learning-state/tool protocol. Context/commitments are teacher-only. After writes call learning_view.',
    schema({command:genericObject}),false,['model']),
  tool('learning_draft','Save the current unsent draft only after explicit app-user confirmation. Does not submit an answer.',
    schema({chatId:chat,key:{type:'string',maxLength:300},expectedVersion:{type:'integer',minimum:-1},baseRevision:{type:'integer',minimum:0},
      payload:{anyOf:[genericObject,{type:'null'}]}}),false,['app']),
  tool('learning_asset','Read a digest-bound artifact already attached to this owning lesson. No arbitrary file paths.',
    schema({chatId:chat,file:{type:'string',maxLength:200}}),true,['app']),
  tool('learning_artifact_source','Read one saved artifact for the existing T3 native visual publisher. No execution or model call is launched.',
    schema({chatId:chat,file:{type:'string',maxLength:200}}),true,['model']),
];
const textResult=value=>({content:[{type:'text',text:JSON.stringify(value)}]});
function t3Result(value) {
  const {directive,snapshot,...rest}=value;
  return {...rest,...(snapshot?{snapshot:{revision:snapshot.revision,projectionSha256:snapshot.projectionSha256}}:{}),
    nextPresentationTool:'learning_view'};
}
export function handleLearningTool(boundary,request) {
  const {name,arguments:args={},_meta:meta}=request.params;
  if(name==='learning_identity') {
    if(args===null||typeof args!=='object'||Array.isArray(args)||Object.keys(args).length)throw new Error('Identity accepts no arguments.');
    return textResult({nativeThreadId:boundary.owner(meta)});
  }
  if(name==='learning_view')return {content:[{type:'text',text:'Current saved lesson; use the interactive card.'}],...boundary.view(meta,args)};
  if(name==='learning_catalogue')return textResult({lessons:boundary.catalogue(meta,args)});
  if(name==='learning_input')return textResult(t3Result(boundary.input(meta,args)));
  if(name==='learning_command')return textResult(t3Result(boundary.command(meta,args)));
  if(name==='learning_draft')return {...textResult({saved:true}),structuredContent:boundary.draft(meta,args)};
  if(name==='learning_asset') {
    const result={content:[{type:'text',text:'Verified saved artifact.'}],_meta:boundary.asset(meta,args)};
    if(Buffer.byteLength(JSON.stringify(result))>240*1024)throw Object.assign(new Error('Artifact exceeds app bridge limit.'),{code:'asset_too_large'});
    return result;
  }
  if(name==='learning_artifact_source')return textResult(boundary.asset(meta,args));
  throw Object.assign(new Error('Unknown learning tool.'),{code:'unknown_tool'});
}
export async function start(configFile,sdkRoot) {
  if(!configFile||!sdkRoot)throw new Error('Pass --config <private enrollment> --sdk-root <existing SDK runtime>. No automatic installation.');
  const require=createRequire(path.join(fs.realpathSync(sdkRoot),'package.json'));
  const sdkDirectory=path.resolve(path.dirname(require.resolve('@modelcontextprotocol/sdk/server/index.js')),'../../..');
  const sdkPackage=JSON.parse(fs.readFileSync(path.join(sdkDirectory,'package.json'),'utf8'));
  if(sdkPackage.version!=='1.32.0')throw new Error('This source adapter selects MCP SDK1.32.0; review another version before activation.');
  const load=specifier=>import(pathToFileURL(path.join(sdkDirectory,'dist/esm',specifier)).href);
  const [{Server},{StdioServerTransport},types]=await Promise.all([
    load('server/index.js'),load('server/stdio.js'),load('types.js')]);
  const boundary=new T3LearningBoundary(configFile);
  const server=new Server({name:'learnharness-native',version:'0.1.0-dev'},{capabilities:{tools:{},resources:{}},
    instructions:'Existing agent remains teacher. Use learning_catalogue/view. On a genuine lh.t3 message, call learning_input with those exact fields, then context/continue/teach/question through learning_command; return learning_view. Never copy an owner into env/arguments. No automatic provider or worker is part of this server.'});
  server.setRequestHandler(types.ListToolsRequestSchema,async()=>({tools:TOOLS}));
  server.setRequestHandler(types.CallToolRequestSchema,async request=>{
    try {return handleLearningTool(boundary,request);}
    catch(error){return {isError:true,...textResult({ok:false,code:typeof error.code==='string'?error.code:'operation_failed',
      error:error.name==='StateError'?error.message:'Operation failed; preserve outcome and inspect before any repeat.'})};}
  });
  server.setRequestHandler(types.ListResourcesRequestSchema,async()=>({resources:[{uri:APP_URI,name:'LearnHarness learning controls',mimeType:'text/html;profile=mcp-app'}]}));
  server.setRequestHandler(types.ReadResourceRequestSchema,async request=>{
    if(request.params.uri!==APP_URI)throw new Error('Unknown static app resource.');
    const file=fileURLToPath(new URL('../../t3/app.html',import.meta.url)),stat=fs.statSync(file);
    if(!stat.isFile()||stat.size>5*1024*1024)throw new Error('Build the bounded static app resource before activation.');
    return {contents:[{uri:APP_URI,mimeType:'text/html;profile=mcp-app',text:fs.readFileSync(file,'utf8'),
      _meta:{ui:{prefersBorder:true,csp:{connectDomains:[],resourceDomains:[],frameDomains:[]}}}}]};
  });
  await server.connect(new StdioServerTransport());
  return server;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const args=process.argv.slice(2);
  if(args.length!==4||args[0]!=='--config'||args[2]!=='--sdk-root')throw new Error('Use --config <private file> --sdk-root <existing runtime>.');
  start(args[1],args[3]).catch(()=>{console.error('Learning MCP startup failed; no automatic retry, installation or fallback.');process.exitCode=1;});
}
