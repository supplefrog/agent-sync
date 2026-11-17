// SPDX-License-Identifier: AGPL-3.0-only
// Host-native presentation projection; no Markdown parser or HTML execution.
const codeLanguages=new Set(['','text','txt','plaintext','python','py','javascript','js','typescript','ts','json','css','bash','sh','shell','powershell','ps1','sql','java','c','cpp','c++','csharp','c#','go','rust','ruby','rb','r','matlab','latex','tex']);
const richLanguages=new Set([...codeLanguages,'mermaid','smiles','abc','tikz']);

// Like LearnHarness #401, recover one escaped layer only when a complete
// fenced example provides structural evidence. Never repair mixed layouts
// or turn an escaped example into a diagram, notation, or resource.
function recoverEscapedCode(text) {
  if(typeof text!=='string'||text.length>65536||/[\r\n]/.test(text)||!text.includes('\\n'))return text;
  const decoded=text.replace(/\\\\|\\r\\n|\\n/g,token=>token==='\\\\'?'\\':'\n');
  let open=null,complete=false;
  for(const line of decoded.split('\n')){
    const fence=/^[ \t]{0,3}(`{3,}|~{3,})[ \t]*(.*)$/.exec(line);
    if(!fence)continue;
    const [,marker,info]=fence,language=info.trim().toLowerCase();
    if(open===null){
      if(!codeLanguages.has(language))return text;
      open=marker;
    }else{
      if(language||marker[0]!==open[0]||marker.length<open.length)return text;
      open=null;
      complete=true;
    }
  }
  return complete&&open===null?decoded:text;
}

export function prepareRichText(text) {
  const prepared=recoverEscapedCode(text);
  const languages=prepared===text?richLanguages:codeLanguages;
  return richTextAllowedFor(prepared,languages)?prepared:null;
}

export function richTextAllowed(text) {
  return richTextAllowedFor(text,richLanguages);
}

function richTextAllowedFor(text,languages) {
  if(typeof text!=='string'||text.length>65536)return false;
  for(const match of text.matchAll(/(?:`{3,}|~{3,})[ \t]*([^\s`~]*)/g))
    if(!languages.has(match[1].toLowerCase()))return false;
  return !/(?:https?:|file:|data:|MEDIA:|!\s*\[|\]\s*\(|^\s{0,3}\[[^\]]+\]:|<\/?[a-z][^>]*>)/im.test(text);
}
export function planDiagram(plan) {
  if(!plan || !Array.isArray(plan.nodes) || !Array.isArray(plan.edges)) return null;
  const ids=new Set(plan.nodes.map(n=>n.id));
  if(plan.nodes.some(n=>!/^[a-z0-9]+([_-][a-z0-9]+)*$/.test(n.id)) || plan.edges.some(e=>!ids.has(e.from)||!ids.has(e.to))) return null;
  const label=s=>String(s).replace(/["\\\r\n<>&]/g,' ');
  return '```mermaid\nflowchart TD\n'+plan.nodes.map(n=>` ${n.id}["${label(n.title)}"]`).join('\n')+'\n'+
    plan.edges.map(e=>` ${e.from} --> ${e.to}`).join('\n')+'\n```';
}
export function lessonProse(view,{open=true}={}) {
  const result=[],add=(id,text)=>{if(typeof text==='string'&&text)result.push({id,text});};
  if(view.kind==='practice') {
    if(view.conclusion){add('review-statement',view.conclusion.statement);add('review-verdict',view.conclusion.verdict);add('review-solution','### Committed solution\n\n'+view.conclusion.modelSolution);}
    for(const entry of view.discussion??[])add('discussion-'+entry.id,entry.role==='user'?'Your question: '+entry.text:entry.text);
    if(view.activeProblem&&open){add('problem',view.activeProblem.statement);for(const f of view.feedback??[])add('feedback-'+f.id,f.text);}
    return result;
  }
  if(view.teachingText)add('teaching',view.teachingText);
  if(view.question&&open){add('question',view.question.question);add('context',view.question.context);
    for(const [index,option] of (view.question.options??[]).entries())add('option-'+index,`**Choice ${index+1}**\n\n${typeof option==='string'?option:option.text??option.label??''}`);}
  if(!view.question){const answer=view.answers?.at(-1);if(answer){add('answered-question',answer.questionText);add('revealed-answer',answer.committed);}}
  const diagram=planDiagram(view.plan);if(diagram)add('plan',diagram);
  const knowledge=view.knowledge?.nodes?.length?planDiagram(view.knowledge.diagram):null;
  if(knowledge)add('knowledge-map','### Propositions from this lesson\n\n'+knowledge);
  return result;
}
export function renderSettledExplanation(React,MessageTextContent,answer) {
  if(answer?.kind!=='quiz'||typeof answer.explanation!=='string'||!answer.explanation)return null;
  const text=answer.explanation;
  const prepared=prepareRichText(text);
  return React.createElement('details',{key:'why-'+answer.toolCallId,'data-learning-answer-why':''},
    React.createElement('summary',null,'Why'),
    prepared!==null&&typeof MessageTextContent==='function'
      ?React.createElement(MessageTextContent,{text:prepared,media:false,decorateText:children=>React.createElement('span',null,children)})
      :React.createElement('pre',{style:{whiteSpace:'pre-wrap'}},text));
}
export function renderLessonProse(React,MessageTextContent,view,state,choices) {
  const textContent=text=>{
    const prepared=prepareRichText(text);
    return prepared!==null
      ?React.createElement(MessageTextContent,{text:prepared,media:false,
        // Wrapping paragraphs prevents nested transcript directives.
        decorateText:children=>React.createElement('span',null,children)})
      :React.createElement('pre',{style:{whiteSpace:'pre-wrap'}},text);
  };
  const q=view.question,external=typeof choices?.select==='function'&&q&&q.mode!=='text';
  return React.createElement('div',{'data-learning-prose':'',className:'lh-native-prose'},
    ...lessonProse(view,state).map(entry=>{
      if(external&&/^option-\d+$/.test(entry.id)) {
        const index=Number(entry.id.slice(7)),option=q.options[index];
        const current=choices.questionId===q.toolCallId,disabled=!current||choices.pending===true;
        // The host renderer can contain its own code-copy/diagram controls.
        // A role-button keeps that valid DOM; child controls never select an answer.
        const select=()=>{if(!disabled)choices.select(index,q.toolCallId);};
        return React.createElement('div',{key:entry.id,role:'button',className:'lh-option',tabIndex:disabled?-1:0,
          'data-option':option.value,'data-learning-rich-choice':'','aria-pressed':current&&choices.selected?.includes(index)===true,
          'aria-disabled':disabled,onClick:event=>{
            const nested=event.target?.closest?.('button,a,input,textarea,select,summary,[role="button"]');
            if(nested&&nested!==event.currentTarget)return;select();
          },onKeyDown:event=>{
            if(event.target!==event.currentTarget||event.altKey||event.ctrlKey||event.metaKey||!['Enter',' '].includes(event.key))return;
            event.preventDefault();event.stopPropagation();select();
          }},
          textContent(entry.text),q.kind!=='quiz'&&typeof option.description==='string'&&option.description?React.createElement('span',{className:'lh-secondary'},textContent(option.description)):null);
      }
      return React.createElement('section',{key:entry.id,'data-learning-prose-part':entry.id},textContent(entry.text));}),
    view.kind==='practice'?null:renderSettledExplanation(React,MessageTextContent,view.answers?.at(-1)));
}
