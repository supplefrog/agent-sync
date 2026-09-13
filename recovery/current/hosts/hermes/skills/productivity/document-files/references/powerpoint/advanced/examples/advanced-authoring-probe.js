const path = require('path');
const fs = require('node:fs');
const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Hermes staged PowerPoint probe';
pptx.subject = 'PptxGenJS advanced feature verification';
pptx.title = 'Advanced authoring probe';
pptx.company = 'Nous Research';
pptx.lang = 'en-US';
pptx.theme = {
  headFontFace: 'Aptos Display', bodyFontFace: 'Aptos', lang: 'en-US'
};

const C = { ink: '17212B', teal: '007C83', mint: 'DDF4F1', coral: 'EE6C4D', paper: 'F7F3EA', white: 'FFFFFF', gray: '52606D' };
const shadow = { type: 'outer', color: '17212B', opacity: 0.18, blur: 2, angle: 45, offset: 2 };
function title(slide, text) {
  slide.addText(text, { x:0.65, y:0.55, w:12.03, h:0.55, margin:0, fontFace:'Aptos Display', fontSize:26, bold:true, color:C.ink });
}

// Slide 1 rich text, character spacing, margins, bullets, shapes, shadows.
{
  const slide = pptx.addSlide();
  slide.background = { color: C.paper };
  title(slide, 'Text hierarchy and deliberate spacing');
  slide.addText([
    { text:'RICH ', options:{ bold:true, color:C.teal, charSpacing:2.5 } },
    { text:'text runs', options:{ italic:true, color:C.coral } },
    { text:' stay editable.', options:{ color:C.ink } }
  ], { x:0.7, y:1.45, w:7.2, h:0.65, margin:[4,8,4,8], fontSize:24, fill:{color:C.white}, line:{color:'D2D8DC', width:1} });
  slide.addText([
    { text:'One clear claim', options:{ bullet:{code:'25CF'}, breakLine:true, bold:true, color:C.ink } },
    { text:'Supporting detail with breathing room', options:{ bullet:{code:'25CF'}, breakLine:true, color:C.gray } },
    { text:'Nested evidence', options:{ bullet:{code:'2013'}, indentLevel:1, color:C.teal } }
  ], { x:0.75, y:2.45, w:6.8, h:2.0, margin:[8,12,8,18], fontSize:17, breakLine:true, paraSpaceAfterPt:10, fill:{color:C.white} });
  slide.addShape(pptx.ShapeType.roundRect, { x:8.45, y:1.5, w:3.85, h:2.5, rectRadius:0.08, fill:{color:C.teal}, line:{color:C.teal}, shadow });
  slide.addText('64%', { x:8.75, y:2.0, w:3.25, h:0.8, margin:0, align:'center', fontSize:46, bold:true, color:C.white });
  slide.addText('visual emphasis', { x:8.75, y:2.95, w:3.25, h:0.35, margin:0, align:'center', fontSize:15, color:C.mint, charSpacing:1.2 });
}

// Slide 2: raster image and native SVG.
{
  const slide = pptx.addSlide();
  slide.background = { color: C.white };
  title(slide, 'Raster reliability, SVG precision');
  const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFUlEQVR4nGNkqGn+z4AHMOGTHD4KABDZAg5B0aYfAAAAAElFTkSuQmCC';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360"><rect width="640" height="360" rx="28" fill="#DDF4F1"/><circle cx="170" cy="180" r="92" fill="#007C83"/><path d="M310 115h245v34H310zm0 74h190v28H310zm0 65h225v28H310z" fill="#17212B"/><path d="M120 180l35 35 70-82" fill="none" stroke="#fff" stroke-width="25" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const svgData = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
  slide.addShape(pptx.ShapeType.roundRect, { x:0.75, y:1.5, w:3.0, h:3.8, fill:{color:C.paper}, line:{color:'D9D3C7'}, shadow });
  slide.addImage({ data:png, x:1.2, y:2.0, w:2.1, h:2.1, altText:'Embedded eight-pixel raster compatibility probe' });
  slide.addText('PNG/JPEG: broad viewer support', { x:0.95, y:4.55, w:2.6, h:0.4, margin:0, align:'center', fontSize:13, bold:true, color:C.ink });
  slide.addImage({ data:svgData, x:4.35, y:1.5, w:7.9, h:4.45, altText:'Native SVG compatibility probe with check mark' });
  slide.addText('Native SVG needs a modern PowerPoint/Microsoft 365 viewer; rasterize for older or mixed environments.', { x:4.45, y:6.15, w:7.7, h:0.45, margin:0, fontSize:13, color:C.gray });
}

// Slide 3: merged, styled table including rich text in a cell.
{
  const slide = pptx.addSlide();
  slide.background = { color: C.paper };
  title(slide, 'Merged cells can still carry hierarchy');
  const rows = [
    [{ text:'Advanced feature matrix', options:{ colspan:3, fill:C.teal, color:C.white, bold:true, align:'center', margin:[8,10,8,10] } }],
    [
      { text:'Area', options:{ fill:C.ink, color:C.white, bold:true } },
      { text:'Technique', options:{ fill:C.ink, color:C.white, bold:true } },
      { text:'Verification', options:{ fill:C.ink, color:C.white, bold:true } }
    ],
    [
      { text:'Text', options:{ rowspan:2, fill:C.mint, bold:true, valign:'mid' } },
      { text:[{text:'Runs + ',options:{bold:true,color:C.teal}},{text:'spacing',options:{italic:true}}], options:{ fill:C.white } },
      { text:'OOXML runs / spc', options:{ fill:C.white } }
    ],
    [
      { text:'Bullets + margins', options:{ fill:'EEF7F6' } },
      { text:'buChar / bodyPr', options:{ fill:'EEF7F6' } }
    ],
    [
      { text:'Visuals', options:{ fill:'FBE9E4', bold:true } },
      { text:'Shapes, shadow, PNG, SVG', options:{ fill:C.white } },
      { text:'effects + media parts', options:{ fill:C.white } }
    ]
  ];
  slide.addTable(rows, { x:0.75, y:1.55, w:11.85, colW:[2.15,5.0,4.7], rowH:[0.6,0.55,0.72,0.72,0.72], fontFace:'Aptos', fontSize:15, color:C.ink, margin:[6,9,6,9], border:{type:'solid', pt:1, color:'C9D1D6'}, valign:'mid', breakLine:false });
  slide.addText('Layout guardrails: 0.5″+ edge clearance • 0.3–0.5″ gaps • explicit widths • render before delivery', { x:0.8, y:6.25, w:11.75, h:0.4, margin:0, align:'center', fontSize:13, color:C.gray, charSpacing:0.5 });
}

const output = process.argv[2] || path.join(__dirname, '..', 'output', 'advanced-authoring-probe.pptx');
fs.mkdirSync(path.dirname(output), { recursive: true });
pptx.writeFile({ fileName: output, compression: true })
  .then(() => console.log(JSON.stringify({ ok:true, output, slides:3, pptxgenjs:'4.0.1' })))
  .catch((error) => { console.error(error); process.exit(1); });
