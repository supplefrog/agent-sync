// SPDX-License-Identifier: AGPL-3.0-only
// Projection/port contracts only; actual Hermes Markdown rendering is unqualified.
import test from 'node:test';
import assert from 'node:assert/strict';
import { lessonProse, planDiagram, renderLessonProse, richTextAllowed } from '../src/inline/lesson-prose.mjs';
import { learningWorkflow } from '../src/workflow.mjs';
test('rich prose preserves reveal gate while teaching remains readable',()=>{
  const view={teachingText:'Use $r=\\frac{y}{x}$ before checking.',question:{question:'HIDDEN-CHECK',context:'CHECK-CONTEXT'},answers:[]};
  const closed=lessonProse(view,{open:false});assert.deepEqual(closed.map(x=>x.id),['teaching']);
  assert.ok(!JSON.stringify(closed).includes('HIDDEN-CHECK'));
  assert.deepEqual(lessonProse(view,{open:true}).map(x=>x.id),['teaching','question','context']);
});
test('practice presentation cannot manufacture a hidden solution and respects problem closure',()=>{
  const view={kind:'practice',activeProblem:{toolCallId:'p1',statement:'Solve $x^2=4$'},feedback:[{id:'hint1',text:'Factor the polynomial.'}]};
  assert.deepEqual(lessonProse(view,{open:false}),[]);
  assert.equal(lessonProse(view,{open:true}).length,2);
  const revealed={...view,activeProblem:null,conclusion:{statement:'Review',verdict:'Synthetic verdict',modelSolution:'$x=\\pm2$'}};
  assert.match(lessonProse(revealed).at(-1).text,/Committed solution/);
});
test('host Markdown port has no active transcript directive child or implicit media promotion',()=>{
  const React={createElement:(type,props,...children)=>({type,props,children})},Markdown=()=>{};
  const tree=renderLessonProse(React,Markdown,{teachingText:'**Reasoning** with $x^2$ and ::lh-lesson{lesson="x"}',answers:[]});
  const rendered=tree.children[0].children[0];
  assert.equal(rendered.type,Markdown);assert.equal(rendered.props.media,false);
  assert.equal(rendered.props.decorateText('::lh-lesson').type,'span');
  for(const text of ['![image](private.png)','[file](private.txt)','<img src=x>','https://example.com','MEDIA: private.png','[ref]: private.txt']) {
    assert.equal(richTextAllowed(text),false);
    assert.equal(renderLessonProse(React,Markdown,{teachingText:text,answers:[]}).children[0].children[0].type,'pre');
  }
  assert.equal(richTextAllowed('$x<y$ and **bold**'),true);
  const listing='```listing\n{"address":"Synthetic control","images":["https\\u003a//example.invalid/pixel.png"]}\n```';
  for(const candidate of [listing,listing.replaceAll('```','~~~'),listing.replace('listing','LiStInG'),'> '+listing,'```svg\n{}\n```']) {
    assert.equal(richTextAllowed(candidate),false);
    assert.equal(renderLessonProse(React,Markdown,{teachingText:candidate,answers:[]}).children[0].children[0].type,'pre');
  }
  assert.equal(richTextAllowed('```mermaid\ngraph TD\n a --> b\n```'),true);
  assert.equal(richTextAllowed('```python\nprint(2)\n```'),true);
});
test('plan diagram reuses only validated IDs/edges and escaped labels; it is not mastery',()=>{
  const plan={nodes:[{id:'ratio',title:'Ratio "label"'},{id:'secant',title:'Secant'}],edges:[{from:'ratio',to:'secant'}]};
  assert.match(planDiagram(plan),/ratio --> secant/);
  assert.ok(!planDiagram(plan).includes('"label"'));
  assert.equal(planDiagram({...plan,edges:[{from:'ratio',to:'missing'}]}),null);
  assert.equal(planDiagram({...plan,nodes:[{id:'evil-->node',title:'Bad'}]}),null);
  assert.match(planDiagram({nodes:[{id:'chain-rule',title:'Chain rule'},{id:'rate_2',title:'Rate'}],edges:[{from:'chain-rule',to:'rate_2'}]}),/chain-rule --> rate_2/);
});
test('workflow supplies stage gates without synthesizing answers or automatic mastery',()=>{
  assert.equal(learningWorkflow('teach',{phase:'probe',question:{toolCallId:'probe1'}},[]).stage,'await-answer');
  assert.deepEqual(learningWorkflow('teach',{phase:'probe',question:{toolCallId:'probe1'}},[]).allowed,[]);
  assert.equal(learningWorkflow('teach',{phase:'probe'},[]).stage,'diagnose');
  assert.equal(learningWorkflow('teach',{phase:'teach',plan:null},[]).stage,'plan');
  assert.equal(learningWorkflow('teach',{phase:'teach',plan:{approved:false}},[]).stage,'await-plan-approval');
  const messages=[{role:'assistant',content:[{type:'toolCall',name:'quiz',arguments:{type:'check'}}]}];
  const result=learningWorkflow('teach',{plan:{approved:true},continuationOwed:true},messages);
  assert.equal(result.stage,'react-to-check');assert.deepEqual(result.allowed,['continue']);assert.match(result.instruction,/repair/);
});
