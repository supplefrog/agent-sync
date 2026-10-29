// SPDX-License-Identifier: AGPL-3.0-only
// Granted content-addressed exports only. No preview capability, network client,
// worker dispatcher or raw SVG insertion into the host document.
import { buildDemoSrcDoc, reduceDemoBridgeState, INITIAL_DEMO_BRIDGE_STATE } from '../vendor/runtime/demo-pure.ts';
export function demoDocument(html) {
  const policy='<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; script-src &#39;unsafe-inline&#39;; style-src &#39;unsafe-inline&#39;; img-src data: blob:; font-src data:; connect-src &#39;none&#39;; frame-src &#39;none&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">';
  // The policy precedes ALL untrusted markup, including comments or fake head
  // tags inside scripts. Later CSP elements can only add restrictions.
  return '<!doctype html><html><head>'+policy+'</head><body>'+buildDemoSrcDoc(html)+'</body></html>';
}
export async function readArtifact(files,binding,descriptor) {
  if(!descriptor||!['demo','visual'].includes(descriptor.kind)||!/^[a-f0-9]{64}$/.test(descriptor.sha256??'')||
    descriptor.file!==`asset-${descriptor.kind}-${descriptor.sha256}.${descriptor.kind==='demo'?'html':'svg'}`||
    !Number.isSafeInteger(descriptor.size)||descriptor.size<1||descriptor.size>1048576)throw new Error('Invalid saved artifact identity.');
  const result=await files.readText(binding.folder,descriptor.file);
  if(!result.ok||typeof result.text!=='string')throw new Error('The granted artifact is unavailable.');
  const bytes=new TextEncoder().encode(result.text);
  if(bytes.length!==descriptor.size)throw new Error('Artifact size changed.');
  const sum=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),value=>value.toString(16).padStart(2,'0')).join('');
  if(sum!==descriptor.sha256)throw new Error('Artifact differs from its saved identity.');
  return result.text;
}
export function createJobArtifacts(React) {
  const h=React.createElement;
  function Artifact({job,ctx,binding,view,port}) {
    const [source,setSource]=React.useState(null),[error,setError]=React.useState(''),[bridge,setBridge]=React.useState(INITIAL_DEMO_BRIDGE_STATE);
    const frame=React.useRef(null),mounted=React.useRef(false);
    React.useEffect(()=>{let disposed=false;mounted.current=true;setSource(null);setError('');setBridge(INITIAL_DEMO_BRIDGE_STATE);
      readArtifact(ctx.files,binding,job.artifact).then(text=>{if(!disposed)setSource(text);}).catch(()=>{if(!disposed)setError('Saved artifact could not be verified; no alternate path was read.');});
      return()=>{disposed=true;mounted.current=false;};},[job.artifact.file]);
    React.useEffect(()=>{if(job.kind!=='demo')return;
      const receive=event=>{if(event.source===frame.current?.contentWindow){const data=event.data;
        const bounded=data?.type==='demo-error'?{type:'demo-error',message:typeof data.message==='string'?data.message.slice(0,2000):'unknown error'}:data;
        setBridge(old=>reduceDemoBridgeState(old,bounded));}};
      window.addEventListener('message',receive);return()=>window.removeEventListener('message',receive);},[job.kind]);
    const report=async()=>{if(!mounted.current||!bridge.error)return;
      try{await port.send({type:'job-error',chatId:view.chatId,jobId:job.id,artifactSha256:job.artifact.sha256,error:bridge.error.slice(0,2000)});
        if(mounted.current)setError('Report sent to the owning teacher; this is not an automatic repair or saved-feedback claim.');}
      catch{if(mounted.current)setError('Owning conversation unavailable; report was not sent.');}};
    return h('section',null,h('h4',null,job.artifact.title),error?h('p',{role:'status'},error):null,
      source?(job.kind==='demo'?h('iframe',{ref:frame,title:job.artifact.title,sandbox:'allow-scripts',referrerPolicy:'no-referrer',srcDoc:demoDocument(source),style:{width:'100%',height:bridge.height??320,border:0}}):
        h('img',{alt:job.artifact.title,src:'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source),style:{maxWidth:'100%'}})):h('p',null,'Loading verified artifact.'),
      bridge.error?h('div',null,h('pre',null,bridge.error),h('button',{type:'button',onClick:report},'Send error to teacher')):null);
  }
  return function JobArtifacts({ctx,binding,view,port}) {
  const rows=view.jobs?.jobs??[];
  return h('section',{'aria-label':'Materials and supporting work'},
    view.materials?.length?h('section',null,h('h3',null,'Attached materials'),h('ul',null,...view.materials.map(item=>h('li',{key:item.id},`${item.label} (${item.kind}) — attached source; raw contents stay private.`)))):null,
    rows.length?h('h3',null,'Supporting work'):null,
    ...rows.map(job=>h('article',{key:job.id},h('p',null,`${job.kind}: ${job.activity} (${job.execution})`),
      job.error?h('pre',null,job.error):null,
      job.research?h('section',null,h('p',null,job.research.brief),h('ul',null,...job.research.sources.map((source,index)=>h('li',{key:index},h('a',{href:source.url,target:'_blank',rel:'noopener noreferrer'},source.title))))):null,
      job.pdf?h('section',null,h('p',null,job.pdf.brief),h('p',null,`Reader-reported pages read: ${job.pdf.pagesRead.join(', ')}. Consulted: ${job.pdf.pagesConsulted.join(', ')}.`)):null,
      job.artifact?h(Artifact,{job,ctx,binding,view,port}):null)),
    view.jobs?.nextOffset!==null&&view.jobs?.nextOffset!==undefined?h('p',null,`Showing ${rows.length} of ${view.jobs.total}; the teacher can retrieve further job pages.`):null);
  };
}
