// SPDX-License-Identifier: AGPL-3.0-only
// Source-only SDK contribution. Not installed, enabled, bundled or registered.
import { createHermesLessonPort } from './hermes-native-port.mjs';
import { mountInline } from './inline-client.mjs';
import { renderLessonProse } from './lesson-prose.mjs';
import { createJobArtifacts } from './artifacts.mjs';
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
export function registerHermesLearning(ctx, { host, React, MessageTextContent, bindings, onUnbound }) {
  const JobArtifacts=createJobArtifacts(React);
  const owned = bindings.map(binding => Object.freeze({ ...binding }));
  if (owned.some(b => typeof b.ownerSessionId !== 'string' || !b.ownerSessionId || b.ownerSessionId !== b.ownerSessionId.trim() || b.ownerSessionId === 'new' ||
      !['teach','practice'].includes(b.kind) || !b.chatId || !b.folder)) throw new Error('Explicit owner/lesson/export-folder bindings required.');
  function LessonLeaf({ binding, snapshot, revision }) {
    const ref = React.useRef(null);
    const [view,setView]=React.useState(null);
    const [presentation,setPresentation]=React.useState({open:true});
    const rich=typeof MessageTextContent==='function';
    React.useEffect(() => {
      let disposed = false, controller;
      const root = ref.current;
      setView(null);
      root.textContent = 'Loading saved lesson.';
      (async () => {
        const result = await ctx.files.readText(binding.folder, snapshot);
        if (disposed) return;
        if (!result.ok || typeof result.text !== 'string' || result.size > 262144 || new TextEncoder().encode(result.text).length > 262144)
          throw new Error('The approved redacted lesson export is unavailable.');
        await verifyProjectionBytes(snapshot, result.text);
        if (disposed) return;
        const view = JSON.parse(result.text);
        if (view.chatId !== binding.chatId || (view.kind === 'practice' ? 'practice' : 'teach') !== binding.kind || view.revision !== revision)
          throw new Error('Snapshot owner/lesson/revision differs; ask the owner to return a fresh card.');
        if (view.question && ['committedAnswer','correctIndices','explanation'].some(k => k in view.question))
          throw new Error('An active question export exposed its commitment.');
        if (view.activeProblem && Object.keys(view.activeProblem).some(k => !['toolCallId','statement'].includes(k)))
          throw new Error('An active problem export contains teacher-only fields.');
        setPresentation({open:view.question?.open??true});
        setView(view);
        const ports=createHermesLessonPort(binding.ownerSessionId,view,{composer:host.composer,storage:ctx.storage});
        controller=mountInline(root,view,{...ports,richProse:rich,
          onPresentation:next=>{if(!disposed)setPresentation(old=>old.open===next.open?old:next);}});
      })().catch(error => { if (!disposed) root.textContent = error.message; });
      return () => { disposed = true; controller?.destroy(); };
    }, [binding, snapshot, revision, rich]);
    return React.createElement('section',{className:'lh-native-lesson'},
      rich&&view?renderLessonProse(React,MessageTextContent,view,presentation):null,
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
      return React.createElement(LessonLeaf, { binding, snapshot: props.attrs.snapshot, revision: Number(match[2]) });
    },
  } });
}
