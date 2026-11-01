// SPDX-License-Identifier: AGPL-3.0-only
import { lessonProse } from '../inline/lesson-prose.mjs';
import { requirePublicView } from './fixed-local.mjs';
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function localPresentation(input) {
  const view=requirePublicView(input);
  const prose=lessonProse(view,{open:true});
  if(view.kind==='practice')for(const [i,text] of (view.activeProblem?view.thinking??[]:view.conclusion?.thinking??[]).entries())
    prose.push({id:'learner-thinking-'+i,text:'Your thinking: '+text});
  if(view.kind!=='practice'&&!view.question) {
    const answer=view.answers?.at(-1),saved=[];
    const add=(id,text)=>saved.push({id,text});
    if(answer) {
      if(typeof answer.text==='string'&&answer.text)add('saved-text','Your response: '+answer.text);
      if(Array.isArray(answer.answers)&&answer.answers.length)
        add('saved-choices','Your choices: '+answer.answers.map(a=>`${a.index}. ${a.label}`).join(', '));
      if(typeof answer.other==='string'&&answer.other)add('saved-other','Your additional response: '+answer.other);
      if(answer.dontKnow===true)add('saved-uncertainty',"Your response: I don't know");
      if(typeof answer.thinking==='string'&&answer.thinking)add('saved-thinking','Your thinking: '+answer.thinking);
      if(typeof answer.readingThinking==='string'&&answer.readingThinking)add('saved-reading','Thinking while reading: '+answer.readingThinking);
      if(typeof answer.confidence==='number'&&Number.isFinite(answer.confidence))
        add('saved-confidence','Confidence: '+answer.confidence+'%');
      if(typeof answer.correct==='boolean')add('saved-verdict',answer.correct?'Correct':'Review this step');
      if(Array.isArray(answer.correctIndices))add('saved-correct-choices','Revealed correct choices: '+
        (answer.correctIndices.length?answer.correctIndices.map(index=>{
          const option=answer.options?.find(o=>o.index===index);
          return `${index}. ${option?.label??'[label unavailable]'}`;
        }).join(', '):'[none recorded]'));
      const questionIndex=prose.findIndex(p=>p.id==='answered-question');
      prose.splice(questionIndex<0?prose.length:questionIndex+1,0,...saved);
    }
  }
  const parts=prose.map(p=>'<section><pre>'+escape(p.text)+'</pre></section>').join('');
  const heading=view.kind==='practice'?'Practice':'Learning';
  const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
    '<style>body{margin:0;color:var(--foreground);font-family:var(--font-sans,system-ui);line-height:1.55}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}section{margin:16px 0}small{color:var(--muted-foreground)}h2{font-size:1.15rem}</style></head><body>'+
    '<h2>'+heading+'</h2><small>Saved revision '+view.revision+' · '+escape(view.phase??view.kind??'teach')+'</small>'+parts+
    '<p>Answer in this conversation. This saved card does not submit answers.</p></body></html>';
  return {revision:view.revision,pendingQuestionId:view.question?.toolCallId??view.activeProblem?.toolCallId??null,
    prose,html,title:heading+' — saved revision '+view.revision,
    instruction:'Publish html with the actual T3 html_render tool in this conversation. Use native Markdown for math/diagrams from prose. Ask the pending question through native user input if available, otherwise wait for the genuine composer answer. No automatic answer or advancement.'};
}
