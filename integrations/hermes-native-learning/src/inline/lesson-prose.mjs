// SPDX-License-Identifier: AGPL-3.0-only
// Host-native presentation projection; no Markdown parser or HTML execution.
export function richTextAllowed(text) {
  if(typeof text!=='string'||text.length>65536)return false;
  const ordinary=new Set(['','mermaid','text','txt','plaintext','python','py','javascript','js','typescript','ts','json','css','bash','sh','shell','powershell','ps1','sql','java','c','cpp','c++','csharp','c#','go','rust','ruby','rb','r','matlab','latex','tex']);
  for(const match of text.matchAll(/(?:`{3,}|~{3,})[ \t]*([^\s`~]*)/g))
    if(!ordinary.has(match[1].toLowerCase()))return false;
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
  if(!view.question){const answer=view.answers?.at(-1);if(answer){add('answered-question',answer.questionText);add('revealed-answer',answer.committed);add('revealed-explanation',answer.explanation);}}
  const diagram=planDiagram(view.plan);if(diagram)add('plan',diagram);
  const knowledge=view.knowledge?.nodes?.length?planDiagram(view.knowledge.diagram):null;
  if(knowledge)add('knowledge-map','### Propositions from this lesson\n\n'+knowledge);
  return result;
}
export function renderLessonProse(React,MessageTextContent,view,state) {
  return React.createElement('div',{'data-learning-prose':'',className:'lh-native-prose'},
    ...lessonProse(view,state).map(entry=>React.createElement('section',{key:entry.id,'data-learning-prose-part':entry.id},
      richTextAllowed(entry.text)
        ? React.createElement(MessageTextContent,{text:entry.text,media:false,
          // Core paragraphPlainText accepts only string children. Wrapping
          // every paragraph prevents nested transcript directives in prose.
          decorateText:children=>React.createElement('span',null,children)})
        : React.createElement('pre',{style:{whiteSpace:'pre-wrap'}},entry.text))));
}
