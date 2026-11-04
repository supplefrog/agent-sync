// SPDX-License-Identifier: AGPL-3.0-only
// Source-only SDK contribution. Not installed, enabled, bundled or registered.
import { createHermesLessonPort } from './hermes-native-port.mjs';
import { mountInline } from './inline-client.mjs';
import { renderLessonProse } from './lesson-prose.mjs';
import { createJobArtifacts } from './artifacts.mjs';
import { loadCurrentProjection } from './lesson-identity.mjs';
export async function verifyProjectionBytes(snapshot, text) {
  const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot);
  if (!match || !globalThis.crypto?.subtle) throw new Error('Snapshot content verification is unavailable.');
  const bytes = new TextEncoder().encode(text);
  const sum = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
  const actual = Array.from(sum, byte => byte.toString(16).padStart(2, '0')).join('');
  if (actual !== match[3]) throw new Error('Snapshot bytes differ from their projection identity.');
}

// bindings are explicit approved host configuration, NEVER directive attributes.
// Each folder is a ctx.files grant for REDACTED exports, not the state directory.
export function registerHermesLearning(ctx, { host, React, MessageTextContent, bindings, onUnbound, onReconnect }) {
  const JobArtifacts=createJobArtifacts(React);
  const owned = bindings.map(binding => Object.freeze({ ...binding }));
  if (owned.some(b => typeof b.ownerSessionId !== 'string' || !b.ownerSessionId || b.ownerSessionId !== b.ownerSessionId.trim() || b.ownerSessionId === 'new' ||
      !['teach','practice'].includes(b.kind) || !b.chatId || !b.folder ||
      (b.minimumRevision!==undefined&&(!Number.isSafeInteger(b.minimumRevision)||b.minimumRevision<0)))) throw new Error('Explicit owner/lesson/export-folder bindings required.');
  function LessonLeaf({ binding, snapshot, revision, reconnect }) {
    const ref = React.useRef(null);
    const control = React.useRef(null);
    const highestRevision=React.useRef(Math.max(revision,binding.minimumRevision??0));
    const [view,setView]=React.useState(null);
    const [reload,setReload]=React.useState(0);
    const [busy,setBusy]=React.useState(true);
    const [error,setError]=React.useState('');
    const [presentation,setPresentation]=React.useState({open:true});
    const rich=typeof MessageTextContent==='function';
    React.useEffect(() => {
      let disposed = false, controller;
      const root = ref.current;
      root.inert=true;
      setView(null);
      setBusy(true);setError('');
      root.textContent = 'Loading saved lesson.';
      (async () => {
        // The directive grants no raw paths and is only a lower revision bound.
        // Reopen resolves the latest redacted index within the approved folder.
        const view = await loadCurrentProjection(ctx.files,binding,Math.max(revision,highestRevision.current,binding.minimumRevision??0),verifyProjectionBytes);
        if (disposed) return;
        highestRevision.current=view.revision;
        setPresentation({open:view.question?.open??true});
        setView(view);
        const ports=createHermesLessonPort(binding.ownerSessionId,view,{composer:host.composer,storage:ctx.storage});
        controller=mountInline(root,view,{...ports,richProse:rich,externalChoices:rich,
          onResume:refresh,
          onPresentation:next=>{if(!disposed)setPresentation(old=>old.open===next.open&&old.questionId===next.questionId&&
            old.pending===next.pending&&JSON.stringify(old.selected)===JSON.stringify(next.selected)?old:next);}});
        control.current=controller;
        root.inert=false;setBusy(false);
      })().catch(error => { if (!disposed){root.textContent='';setError(error.message);setBusy(false);} });
      return () => { disposed = true;if(control.current===controller)control.current=null;controller?.destroy(); };
    }, [binding, snapshot, revision, rich, reload]);
    function refresh() {
      if(ref.current)ref.current.inert=true;
      setView(null);setBusy(true);setReload(value=>value+1);
    }
    return React.createElement('section',{className:'lh-native-lesson'},
      React.createElement('button',{type:'button',disabled:busy,onClick:refresh},'Refresh saved lesson'),
      reconnect?.(Math.max(revision,highestRevision.current)),
      error?React.createElement('p',{role:'alert'},error):null,
      rich&&view?renderLessonProse(React,MessageTextContent,view,presentation,{...presentation,
        select:(index,questionId)=>control.current?.selectOption(index,questionId)}):null,
      React.createElement('div', { ref }),
      view?React.createElement(JobArtifacts,{ctx,binding,view,port:createHermesLessonPort(binding.ownerSessionId,view,{composer:host.composer,storage:ctx.storage})}):null);
  }
  return ctx.register({ id: 'learning-inline', area: 'transcript.directives', data: {
    name: 'lh-lesson', render(props) {
      const binding = owned.find(b => b.ownerSessionId === props.sessionId && b.chatId === props.attrs.lesson);
      const match = /^(teach|practice)-r([0-9]+)-[a-f0-9]{64}\.json$/.exec(props.attrs.snapshot ?? '');
      if (!match || !Number.isSafeInteger(Number(match[2])) ||
          Object.keys(props.attrs).some(k => !['lesson','snapshot'].includes(k)))
        return React.createElement('p', null, 'This learning card has no approved owning-session binding.');
      if (props.streaming) return React.createElement('p', null, 'Waiting for the saved lesson export.');
      if (!binding) return onUnbound ? onUnbound(props) : React.createElement('p', null, 'Connect this lesson to its export folder first.');
      if (match[1] !== binding.kind) return React.createElement('p', null, 'Snapshot mode differs from its configured lesson.');
      return React.createElement(LessonLeaf, { key:JSON.stringify([binding.ownerSessionId,binding.kind,binding.chatId]),
        binding, snapshot: props.attrs.snapshot, revision: Number(match[2]),
        reconnect:onReconnect?minimumRevision=>onReconnect({...props,minimumRevision}):undefined });
    },
  } });
}
