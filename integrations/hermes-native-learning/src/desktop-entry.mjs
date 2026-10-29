// SPDX-License-Identifier: AGPL-3.0-only
import { host, MessageTextContent } from '@hermes/plugin-sdk';
import * as React from 'react';
import { registerHermesLearning, verifyProjectionBytes } from './inline/hermes-contribution.mjs';
import { connectLessonExport } from './connect-export.mjs';
const canonical = value => typeof value === 'string' && value && value === value.trim() && value !== 'new';
export default {
  id: 'learnharness-native', name: 'LearnHarness Native', defaultEnabled: false,
  description: 'Inline learning controls over a configured local lesson store; existing Hermes agent remains the teacher.',
  register(ctx) {
    let remove = () => {},active=true;
    ctx.onDispose(()=>{active=false;remove();});
    const style = document.createElement('style');
    style.textContent = __LH_STYLE__; // Build-time static CSS only, never model HTML.
    document.head.append(style); ctx.onDispose(() => style.remove());
    function install(rows) {
      if(!active)return false;
      remove();
      if(!active)return false;
      const registration=registerHermesLearning(ctx, {host,React,MessageTextContent,bindings:rows,onUnbound:props => React.createElement(Connect,{props})});
      if(!active){registration();return false;}
      remove=registration;return true;
    }
    function Connect({props}) {
      const [status,setStatus] = React.useState('This conversation has not been connected to its redacted lesson exports.');
      const [busy,setBusy] = React.useState(false);
      const lifetime=React.useRef({mounted:false,epoch:0,busy:false});
      const owner = props.sessionId, chatId = props.attrs.lesson, snapshot = props.attrs.snapshot;
      const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot ?? '');
      React.useEffect(()=>{
        const state=lifetime.current;state.mounted=true;state.epoch++;state.busy=false;setBusy(false);
        return()=>{state.mounted=false;state.epoch++;state.busy=false;};
      },[owner,chatId,snapshot]);
      async function connect() {
        const state=lifetime.current;
        if (!active||!state.mounted||state.busy||!canonical(owner) || !/^[A-Za-z0-9_-]{1,80}$/.test(chatId ?? '') || !match) return;
        state.busy=true;const epoch=state.epoch;
        const isCurrent=()=>active&&state.mounted&&state.epoch===epoch;
        setBusy(true);
        try {
          // Explicit user gesture invokes the supported picker/grant. Never
          // auto-grant, read raw state, inspect other chats or choose a path.
          const result=await connectLessonExport(ctx,{owner,chatId,snapshot},{isCurrent,verifyBytes:verifyProjectionBytes,install});
          if(isCurrent()&&!result.connected&&!result.cancelled)setStatus('No folder connected.');
        } catch {if(isCurrent())setStatus('The export could not be connected. Check its folder, lesson and revision; no answer was sent.');}
        finally {if(isCurrent()){state.busy=false;setBusy(false);}}
      }
      return React.createElement('section',{className:'lh-native-lesson'},
        React.createElement('p',null,status),React.createElement('button',{type:'button',disabled:busy||!canonical(owner)||!match,onClick:connect},'Connect lesson exports'));
    }
    install(ctx.storage.get('bindings',[]));
  },
};
