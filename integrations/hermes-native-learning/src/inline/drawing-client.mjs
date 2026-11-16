// SPDX-License-Identifier: AGPL-3.0-only
import { DRAWING_HEIGHT, DRAWING_WIDTH, MAX_POINTS, MAX_STROKES, validDrawing } from '../drawing.mjs';

const SVG = 'http://www.w3.org/2000/svg';
function svgElement(doc, name, attributes) {
  const element = doc.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function board(doc, label) {
  const svg = svgElement(doc, 'svg', {
    viewBox: `0 0 ${DRAWING_WIDTH} ${DRAWING_HEIGHT}`, role: 'img', 'aria-label': label, class: 'lh-drawing-board',
  });
  svg.style.width = '100%';
  svg.style.maxWidth = '540px';
  svg.style.display = 'block';
  svg.style.aspectRatio = '5 / 3';
  svg.style.border = '1px solid var(--lh-border, currentColor)';
  svg.style.borderRadius = '8px';
  return svg;
}

function paint(svg, strokes) {
  const doc = svg.ownerDocument;
  const layers = strokes.flatMap(stroke => {
    const [x, y, pressure] = stroke[0];
    return [svgElement(doc, 'circle', {cx: x, cy: y, r: (2 + pressure) / 2, fill: 'currentColor'}),
      ...stroke.slice(1).map(([x2, y2, p2], i) => svgElement(doc, 'line', {
        x1: stroke[i][0], y1: stroke[i][1], x2, y2, stroke: 'currentColor',
        'stroke-width': 2 + (stroke[i][2] + p2) / 2, 'stroke-linecap': 'round',
      }))];
  });
  svg.replaceChildren(...layers);
}

export function savedDrawing(doc, drawing) {
  if (!validDrawing(drawing)) return null;
  const details = doc.createElement('details');
  const label = doc.createElement('summary');
  label.textContent = 'Your drawing';
  const svg = board(doc, 'Saved learner drawing');
  paint(svg, drawing);
  details.append(label, svg);
  return details;
}

function segmentDistance([x,y], [x1,y1], [x2,y2]) {
  const dx = x2 - x1, dy = y2 - y1;
  const scale = dx || dy ? Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy))) : 0;
  return Math.hypot(x - x1 - dx * scale, y - y1 - dy * scale);
}

export function drawingPad(doc, {value, onChange, disabled = false, isOpen, history = []}) {
  let strokes = validDrawing(value) ? value : [];
  let gesture = null;
  let erasing = false;
  const details = doc.createElement('details');
  details.className = 'lh-drawing';
  details.open = isOpen ?? strokes.length > 0;
  const summary = doc.createElement('summary');
  summary.textContent = 'Draw';
  const tools = doc.createElement('div');
  tools.style.display = 'flex';
  tools.style.flexWrap = 'wrap';
  tools.style.gap = '6px';
  tools.style.marginBlock = '8px';
  const svg = board(doc, 'Draw your reasoning with a pen, mouse or touch');
  svg.style.touchAction = 'none';
  function button(label, action) {
    const control = doc.createElement('button');
    control.type = 'button';
    control.textContent = label;
    control.style.padding = '.4rem .65rem';
    control.style.background = 'var(--card, Canvas)';
    control.style.border = '1px solid var(--border, GrayText)';
    control.style.borderRadius = '.5rem';
    control.addEventListener('click', action);
    return control;
  }
  function refresh() {
    paint(svg, strokes);
    pen.setAttribute('aria-pressed', String(!erasing));
    eraser.setAttribute('aria-pressed', String(erasing));
    pen.style.background = erasing ? 'var(--card, Canvas)' : 'var(--accent, Canvas)';
    eraser.style.background = erasing ? 'var(--accent, Canvas)' : 'var(--card, Canvas)';
    pen.disabled = eraser.disabled = disabled || Boolean(gesture);
    undo.disabled = disabled || Boolean(gesture) || !history.length;
    clear.disabled = disabled || Boolean(gesture) || !strokes.length;
  }
  function commit(before) {
    if (before !== strokes) {
      history.push(before);
      if (history.length > 20) history.shift();
      onChange(strokes);
    }
    refresh();
  }
  const pen = button('Pen', () => { erasing = false; refresh(); });
  const eraser = button('Eraser', () => { erasing = true; refresh(); });
  const undo = button('Undo', () => { if (history.length) { strokes = history.pop(); onChange(strokes); refresh(); } });
  const clear = button('Clear', () => { const before = strokes; strokes = []; commit(before); });
  function point(event) {
    const bounds = svg.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return null;
    const scaled = (value, maximum) => Math.max(0, Math.min(maximum, Math.round(value * maximum)));
    return [scaled((event.clientX - bounds.left) / bounds.width, DRAWING_WIDTH),
      scaled((event.clientY - bounds.top) / bounds.height, DRAWING_HEIGHT),
      event.pointerType === 'pen' ? Math.max(1, scaled(event.pressure, 10)) : 5];
  }
  function erase(at) {
    const remaining = strokes.filter(stroke => !stroke.some((p, i) => segmentDistance(at, stroke[i - 1] ?? p, p) < 22));
    if (remaining.length !== strokes.length) strokes = remaining;
  }
  svg.addEventListener('pointerdown', event => {
    if (disabled || gesture || (event.button !== 0 && event.button !== 5)) return;
    const start = point(event);
    if (!start) return;
    const eraseMode = erasing || event.button === 5;
    const points = strokes.reduce((sum, stroke) => sum + stroke.length, 0);
    if (!eraseMode && (strokes.length >= MAX_STROKES || points >= MAX_POINTS)) return;
    gesture = {id: event.pointerId, before: strokes, erase: eraseMode, points};
    svg.setPointerCapture?.(event.pointerId);
    if (eraseMode) erase(start);
    else strokes = [...strokes, [start]];
    refresh();
  });
  svg.addEventListener('pointermove', event => {
    if (gesture?.id !== event.pointerId) return;
    const next = point(event);
    if (!next) return;
    if (gesture.erase) erase(next);
    else {
      const active = strokes.at(-1);
      if (gesture.points + active.length >= MAX_POINTS || segmentDistance(next, active.at(-1), active.at(-1)) < 4) return;
      strokes = [...strokes.slice(0, -1), [...active, next]];
    }
    paint(svg, strokes);
  });
  function finish(event, accept) {
    if (gesture?.id !== event.pointerId) return;
    const {before} = gesture;
    gesture = null;
    if (accept) commit(before);
    else { strokes = before; refresh(); }
  }
  svg.addEventListener('pointerup', event => finish(event, true));
  svg.addEventListener('pointercancel', event => finish(event, false));
  svg.addEventListener('lostpointercapture', event => finish(event, false));
  tools.append(pen, eraser, undo, clear);
  details.append(summary, tools, svg);
  refresh();
  return details;
}
