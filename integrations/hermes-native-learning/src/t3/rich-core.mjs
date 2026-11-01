// SPDX-License-Identifier: AGPL-3.0-only
// Narrow port of LearnHarness MessageResponse/MermaidInline, not its app shell.
// Library bindings live in rich-fragment.mjs, allowing checks with real libraries
// without invoking a browser builder or accessing a live host/lesson.
import {richTextAllowed} from '../inline/lesson-prose.mjs';
import {repairMathForDisplay,transformMathDelimiters} from '../vendor/runtime/math-delims.ts';

export function createRichRenderer({React,createRoot,Streamdown,cjk,createMathPlugin,createMermaidPlugin,remarkBreaks}) {
  const h=React.createElement,roots=new WeakMap();
  const plugins={cjk:{...cjk,remarkPluginsAfter:[...cjk.remarkPluginsAfter,remarkBreaks]},math:createMathPlugin({singleDollarTextMath:true})};
  const diagram=createMermaidPlugin();let sequence=0;
  const mermaidTheme={fontFamily:'ui-sans-serif, system-ui, sans-serif',fontSize:16,securityLevel:'strict',theme:'dark',startOnLoad:false,suppressErrorRendering:true,flowchart:{htmlLabels:false},maxTextSize:65536};
  class RenderBoundary extends React.Component {
    state={failed:false};
    static getDerivedStateFromError(){return{failed:true};}
    render(){return this.state.failed?h('span',{'data-rich-fallback':'render',style:{whiteSpace:'pre-wrap'}},this.props.source):this.props.children;}
  }
  function Diagram({source}) {
    const [svg,setSvg]=React.useState(null),[failed,setFailed]=React.useState(false);
    React.useEffect(()=>{
      let alive=true;setSvg(null);setFailed(false);
      const id=`lh-native-mermaid-${++sequence}`;
      Promise.resolve().then(()=>diagram.getMermaid(mermaidTheme).render(id,source)).then(result=>{
        if(!alive)return;
        if(typeof result?.svg!=='string'||new TextEncoder().encode(result.svg).length>524288)throw new Error('Diagram exceeds bound.');
        setSvg(result.svg);
      }).catch(()=>{if(alive)setFailed(true);});
      return()=>{alive=false;};
    },[source]);
    if(failed)return h('pre',{'data-rich-fallback':'diagram'},source);
    if(svg===null)return h('span',{role:'status'},'Rendering diagram.');
    // Browser image mode, not inline SVG/HTML. No script or active link surface.
    return h('img',{alt:'Lesson diagram',src:'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg),style:{display:'block',maxWidth:'100%',height:'auto'}});
  }
  function textOf(children) {
    if(typeof children==='string'||typeof children==='number')return String(children);
    if(Array.isArray(children))return children.map(textOf).join('');
    return React.isValidElement(children)?textOf(children.props.children):'';
  }
  function Code({children,className,...props}) {
    const language=/language-([^\s]+)/.exec(className??'')?.[1]??'';
    if('data-block' in props&&language==='mermaid')return h(Diagram,{source:textOf(children)});
    return h('code',{className},children);
  }
  // Streamdown's default emphasis uses Tailwind spans. Semantic tags use the
  // reused scoped prose CSS without importing a second Tailwind app shell.
  const components={code:Code,strong:({children})=>h('strong',null,children),em:({children})=>h('em',null,children),
    a:({children})=>h('span',null,children),img:({alt})=>h('span',null,alt??'')};
  function Content({source}) {
    const content=typeof source==='string'?source:'';
    if(!richTextAllowed(content))return h('span',{'data-rich-fallback':'literal',style:{whiteSpace:'pre-wrap'}},content);
    return h(RenderBoundary,{key:content,source:content},h(Streamdown,{mode:'static',parseIncompleteMarkdown:false,
      className:'lh-prose',skipHtml:true,controls:false,plugins,components,urlTransform:()=>''},
      transformMathDelimiters(repairMathForDisplay(content))));
  }
  function mount(element,text) {
    let row=roots.get(element);
    if(!row){row={root:createRoot(element),token:null};roots.set(element,row);}
    const token={};row.token=token;
    try{row.root.render(h(Content,{source:text}));}
    catch {row.root.unmount();roots.delete(element);element.textContent=typeof text==='string'?text:'';return()=>{};}
    return()=>{if(roots.get(element)!==row||row.token!==token)return;roots.delete(element);row.root.unmount();};
  }
  return{mount,Content};
}
