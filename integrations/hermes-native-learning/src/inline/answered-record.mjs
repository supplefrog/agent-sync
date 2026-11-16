// SPDX-License-Identifier: AGPL-3.0-only
// DOM port of LearnHarness v0.3.4 AnsweredCard/ConfidenceRail behavior.
// Settled answer projections only; no pending commitments or state writes.
import {confidenceRailStyle} from './confidence-style.mjs';
import {savedDrawing} from './drawing-client.mjs';
export function answeredRecord(doc,answer,{richProse=false,externalRichExplanation=false,renderProse}={}) {
  const node=(tag,text,attrs={})=>{const e=doc.createElement(tag);if(text!==null)e.textContent=text;for(const[k,v]of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
  const box=node('article',null,{class:'lh-answer-record','data-answer-record':answer.toolCallId});
  const prose=(tag,text)=>{const element=node(tag,text);if(renderProse)renderProse(element,text);return element;};
  const quiz=answer.kind==='quiz',selected=new Set((answer.answers??[]).map(a=>a.index)),correct=new Set(answer.correctIndices??[]);
  if(!richProse)box.append(prose('div',answer.questionText));
  if(quiz)box.append(node('p',answer.dismissed?'Skipped':answer.dontKnow?"Answered: I don't know":answer.correct?'Correct':'Incorrect',{'data-answer-verdict':''}));
  for(const option of answer.options??[]) {
    const chosen=selected.has(option.index),right=quiz&&correct.has(option.index);
    const row=node('div',null,{class:'lh-answer-option','data-selected':chosen,'data-correct':right,'data-graded':quiz});
    row.append(node('span',`${chosen?'Selected: ':''}${right?'Correct answer: ':''}`),prose('span',option.label));box.append(row);
  }
  if(answer.coding)box.append(codingRecord(doc,answer.coding));
  else if(answer.text)box.append(node('p',answer.text));
  if(answer.other)box.append(node('p',`Other: ${answer.other}`));
  const drawing=savedDrawing(doc,answer.drawing);if(drawing)box.append(drawing);
  if(quiz&&!answer.dontKnow&&Number.isFinite(answer.confidence)) {
    const confidence=node('div',null,{class:'lh-answered-confidence','data-answered-confidence':''});
    const rail=node('span',null,{class:'lh-static-confidence-rail','aria-hidden':'true'});
    Object.assign(rail.style,confidenceRailStyle(answer.confidence));
    confidence.append(rail,node('span',`Confidence: ${answer.confidence}%`));box.append(confidence);
  }
  for(const [label,text]of [['Your thinking',answer.thinking??answer.note],['Thinking while reading',answer.readingThinking]])if(text){
    const details=node('details',null);details.append(node('summary',label),node('p',text));box.append(details);
  }
  if(quiz&&answer.explanation&&!externalRichExplanation) {
    const why=node('details',null,{'data-answer-why':''});why.append(node('summary','Why'),prose('div',answer.explanation));box.append(why);
  }
  // Explain/recall is evaluated by the teacher, never an invented client verdict.
  if(answer.coding?.solution) {
    const solution=node('details',null);
    solution.append(node('summary','Model solution'),node('pre',answer.coding.solution));
    box.append(solution);
  } else if(answer.kind==='explain'&&answer.committed&&!richProse)box.append(prose('div',`The answer: ${answer.committed}`));
  return box;
}

export function codingRecord(doc,coding) {
  const box=doc.createElement('details'), label=doc.createElement('summary'), code=doc.createElement('pre');
  label.textContent='Your code';code.textContent=coding.code;
  code.style.overflow='auto';
  box.append(label,code);
  if(coding.observations?.length) {
    const tests=doc.createElement('ul');
    for(const test of coding.observations) {
      const item=doc.createElement('li');
      item.textContent=`${test.name}: ${test.status??(test.passed?'passed':'failed')}${test.detail?' — '+test.detail:''}`;
      tests.append(item);
    }
    box.append(tests);
  }
  return box;
}
