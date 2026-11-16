// SPDX-License-Identifier: AGPL-3.0-only; LearnHarness native integration. See NOTICE.md.

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/desktop-entry.mjs
import { host, MessageTextContent } from "@hermes/plugin-sdk";
import * as React from "react";

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/lesson-layout.mjs
function lessonResponseArea(dock, { exploration, workbench }) {
  if (!exploration) return dock;
  exploration.hidden = false;
  if (!workbench) {
    dock.append(exploration);
    return dock;
  }
  const grid = dock.ownerDocument.createElement("div");
  grid.className = "lh-workbench";
  const response = dock.ownerDocument.createElement("div");
  response.className = "lh-workbench-response";
  grid.append(exploration, response);
  dock.append(grid);
  return response;
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/vendor/runtime/question-pure.ts
var CONFIDENCE_STOPS = [0, 30, 50, 70, 90, 100];
var DEFAULT_CONFIDENCE_INDEX = 2;
var emptyDockSelection = () => ({ selected: /* @__PURE__ */ new Set(), otherSelected: false, dontKnow: false });
function toggleOption(mode, sel, idx) {
  if (mode === "multi-select") {
    const selected = new Set(sel.selected);
    if (selected.has(idx)) selected.delete(idx);
    else selected.add(idx);
    return { selected, otherSelected: sel.otherSelected, dontKnow: false };
  }
  return { selected: /* @__PURE__ */ new Set([idx]), otherSelected: false, dontKnow: false };
}
function toggleOther(mode, sel) {
  if (mode === "multi-select") return { ...sel, otherSelected: !sel.otherSelected, dontKnow: false };
  return { selected: /* @__PURE__ */ new Set(), otherSelected: true, dontKnow: false };
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/rich-scope.mjs
function createRichScope(renderRich) {
  let cleanups = [];
  return {
    render(element, text) {
      element.textContent = typeof text === "string" ? text : "";
      if (typeof renderRich !== "function" || typeof text !== "string") return;
      try {
        const dispose = renderRich(element, text);
        if (typeof dispose === "function") cleanups.push(dispose);
      } catch {
        element.textContent = text;
      }
    },
    clear() {
      const previous = cleanups;
      cleanups = [];
      for (const dispose of previous) {
        try {
          dispose();
        } catch {
        }
      }
    }
  };
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/lesson-identity.mjs
var MAX_LESSON_DRAFT_BYTES = 64 * 1024;
var lessonKind = (view) => view.kind === "practice" ? "practice" : "teach";
var lessonDraftKey = (view) => lessonKind(view) === "practice" ? `${view.chatId}:practice:${view.activeProblem?.toolCallId ?? "between"}` : `${view.chatId}:${view.question?.toolCallId ?? "idle"}`;
function currentProjectionName(chatId) {
  if (typeof chatId !== "string" || !/^[A-Za-z0-9_-]{1,80}$/.test(chatId)) throw new Error("Invalid lesson identity.");
  return `current-${chatId}.json`;
}
function samePracticeSubmission(a, b) {
  if (!a || !b || a.code !== b.code) return false;
  const thinking = (value) => value.code !== void 0 && typeof value.text === "string" && !value.text.trim() ? "" : value.text;
  return thinking(a) === thinking(b) && JSON.stringify(a.drawing) === JSON.stringify(b.drawing);
}
function practiceSubmissionIn(view, entry, input) {
  if (!entry?.id) return false;
  return samePracticeSubmission({
    text: entry.text,
    code: view.codingAttempts?.find((row) => row.id === entry.id)?.code,
    drawing: view.drawings?.find((row) => row.id === entry.id)?.drawing
  }, input);
}
function isPublicCoding(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value) && Object.keys(value).every((key) => ["language", "starterCode", "testNames"].includes(key)) && value.language === "javascript" && typeof value.starterCode === "string" && new TextEncoder().encode(value.starterCode).length <= 8192 && Array.isArray(value.testNames) && value.testNames.length <= 8 && value.testNames.every((name) => typeof name === "string" && name.length <= 100);
}
function validateLessonView(view, { chatId, kind, minimumRevision = 0 }) {
  if (!view || view.chatId !== chatId || lessonKind(view) !== kind || view.kind !== void 0 && !["teach", "practice"].includes(view.kind) || !Number.isSafeInteger(view.revision) || view.revision < minimumRevision)
    throw new Error("Refusing a different lesson, mode or older saved revision.");
  if (view.question && ["committedAnswer", "correctIndices", "explanation"].some((k) => k in view.question))
    throw new Error("An active question exposed its commitment.");
  if (view.activeProblem && Object.keys(view.activeProblem).some((k) => !["toolCallId", "statement", "coding"].includes(k)))
    throw new Error("An active problem exposed teacher-only fields.");
  for (const prompt of [view.question, view.activeProblem]) if (prompt?.coding !== void 0 && !isPublicCoding(prompt.coding))
    throw new Error("An active exercise exposed private coding fields.");
  return view;
}
function parseCurrentProjection(text, binding, minimumRevision = 0) {
  if (typeof text !== "string" || new TextEncoder().encode(text).length > 4096)
    throw new Error("Current lesson index is unavailable or oversized.");
  const index = JSON.parse(text);
  const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(index?.snapshot ?? "");
  if (!index || index.v !== 1 || index.chatId !== binding.chatId || index.kind !== binding.kind || Object.keys(index).some((k) => !["v", "chatId", "kind", "revision", "snapshot"].includes(k)) || !Number.isSafeInteger(index.revision) || index.revision < minimumRevision || typeof index.snapshot !== "string" || !match || match[1] !== binding.kind || match[2] !== String(index.revision))
    throw new Error("Current lesson index differs from this lesson or saved revision.");
  return index;
}
async function loadCurrentProjection(files, binding, minimumRevision, verifyBytes) {
  const result = await files.readText(binding.folder, currentProjectionName(binding.chatId));
  if (!result.ok) throw new Error("Current saved lesson unavailable. Ask the owning teacher to export it; no action was sent.");
  const index = parseCurrentProjection(result.text, binding, minimumRevision);
  const snapshot = await files.readText(binding.folder, index.snapshot);
  if (!snapshot.ok || typeof snapshot.text !== "string" || new TextEncoder().encode(snapshot.text).length > 262144)
    throw new Error("The current redacted lesson export is unavailable.");
  await verifyBytes(index.snapshot, snapshot.text);
  const view = validateLessonView(JSON.parse(snapshot.text), { ...binding, minimumRevision: index.revision });
  if (view.revision !== index.revision) throw new Error("Current index and snapshot revisions differ.");
  return view;
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/drawing.mjs
var MAX_STROKES = 40;
var MAX_POINTS = 320;
var DRAWING_WIDTH = 1e3;
var DRAWING_HEIGHT = 600;
function validDrawing(value) {
  if (!Array.isArray(value) || value.length === 0 || value.length > MAX_STROKES) return false;
  let points = 0;
  return Array.from(value).every((stroke) => {
    if (!Array.isArray(stroke) || stroke.length === 0 || (points += stroke.length) > MAX_POINTS) return false;
    return Array.from(stroke).every((point) => Array.isArray(point) && point.length === 3 && Array.from(point).every(Number.isSafeInteger) && point[0] >= 0 && point[0] <= DRAWING_WIDTH && point[1] >= 0 && point[1] <= DRAWING_HEIGHT && point[2] >= 1 && point[2] <= 10);
  });
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/drawing-client.mjs
var SVG = "http://www.w3.org/2000/svg";
function svgElement(doc, name, attributes) {
  const element = doc.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}
function board(doc, label) {
  const svg = svgElement(doc, "svg", {
    viewBox: `0 0 ${DRAWING_WIDTH} ${DRAWING_HEIGHT}`,
    role: "img",
    "aria-label": label,
    class: "lh-drawing-board"
  });
  svg.style.width = "100%";
  svg.style.maxWidth = "540px";
  svg.style.display = "block";
  svg.style.aspectRatio = "5 / 3";
  svg.style.border = "1px solid var(--lh-border, currentColor)";
  svg.style.borderRadius = "8px";
  return svg;
}
function paint(svg, strokes) {
  const doc = svg.ownerDocument;
  const layers = strokes.flatMap((stroke) => {
    const [x, y, pressure] = stroke[0];
    return [
      svgElement(doc, "circle", { cx: x, cy: y, r: (2 + pressure) / 2, fill: "currentColor" }),
      ...stroke.slice(1).map(([x2, y2, p2], i) => svgElement(doc, "line", {
        x1: stroke[i][0],
        y1: stroke[i][1],
        x2,
        y2,
        stroke: "currentColor",
        "stroke-width": 2 + (stroke[i][2] + p2) / 2,
        "stroke-linecap": "round"
      }))
    ];
  });
  svg.replaceChildren(...layers);
}
function savedDrawing(doc, drawing) {
  if (!validDrawing(drawing)) return null;
  const details = doc.createElement("details");
  const label = doc.createElement("summary");
  label.textContent = "Your drawing";
  const svg = board(doc, "Saved learner drawing");
  paint(svg, drawing);
  details.append(label, svg);
  return details;
}
function segmentDistance([x, y], [x1, y1], [x2, y2]) {
  const dx = x2 - x1, dy = y2 - y1;
  const scale = dx || dy ? Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy))) : 0;
  return Math.hypot(x - x1 - dx * scale, y - y1 - dy * scale);
}
function drawingPad(doc, { value, onChange, disabled = false, isOpen, history = [] }) {
  let strokes = validDrawing(value) ? value : [];
  let gesture = null;
  let erasing = false;
  const details = doc.createElement("details");
  details.className = "lh-drawing";
  details.open = isOpen ?? strokes.length > 0;
  const summary = doc.createElement("summary");
  summary.textContent = "Draw";
  const tools = doc.createElement("div");
  tools.style.display = "flex";
  tools.style.flexWrap = "wrap";
  tools.style.gap = "6px";
  tools.style.marginBlock = "8px";
  const svg = board(doc, "Draw your reasoning with a pen, mouse or touch");
  svg.style.touchAction = "none";
  function button(label, action) {
    const control = doc.createElement("button");
    control.type = "button";
    control.textContent = label;
    control.style.padding = ".4rem .65rem";
    control.style.background = "var(--card, Canvas)";
    control.style.border = "1px solid var(--border, GrayText)";
    control.style.borderRadius = ".5rem";
    control.addEventListener("click", action);
    return control;
  }
  function refresh() {
    paint(svg, strokes);
    pen.setAttribute("aria-pressed", String(!erasing));
    eraser.setAttribute("aria-pressed", String(erasing));
    pen.style.background = erasing ? "var(--card, Canvas)" : "var(--accent, Canvas)";
    eraser.style.background = erasing ? "var(--accent, Canvas)" : "var(--card, Canvas)";
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
  const pen = button("Pen", () => {
    erasing = false;
    refresh();
  });
  const eraser = button("Eraser", () => {
    erasing = true;
    refresh();
  });
  const undo = button("Undo", () => {
    if (history.length) {
      strokes = history.pop();
      onChange(strokes);
      refresh();
    }
  });
  const clear = button("Clear", () => {
    const before = strokes;
    strokes = [];
    commit(before);
  });
  function point(event) {
    const bounds = svg.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return null;
    const scaled = (value2, maximum) => Math.max(0, Math.min(maximum, Math.round(value2 * maximum)));
    return [
      scaled((event.clientX - bounds.left) / bounds.width, DRAWING_WIDTH),
      scaled((event.clientY - bounds.top) / bounds.height, DRAWING_HEIGHT),
      event.pointerType === "pen" ? Math.max(1, scaled(event.pressure, 10)) : 5
    ];
  }
  function erase(at) {
    const remaining = strokes.filter((stroke) => !stroke.some((p, i) => segmentDistance(at, stroke[i - 1] ?? p, p) < 22));
    if (remaining.length !== strokes.length) strokes = remaining;
  }
  svg.addEventListener("pointerdown", (event) => {
    if (disabled || gesture || event.button !== 0 && event.button !== 5) return;
    const start = point(event);
    if (!start) return;
    const eraseMode = erasing || event.button === 5;
    const points = strokes.reduce((sum, stroke) => sum + stroke.length, 0);
    if (!eraseMode && (strokes.length >= MAX_STROKES || points >= MAX_POINTS)) return;
    gesture = { id: event.pointerId, before: strokes, erase: eraseMode, points };
    svg.setPointerCapture?.(event.pointerId);
    if (eraseMode) erase(start);
    else strokes = [...strokes, [start]];
    refresh();
  });
  svg.addEventListener("pointermove", (event) => {
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
    const { before } = gesture;
    gesture = null;
    if (accept) commit(before);
    else {
      strokes = before;
      refresh();
    }
  }
  svg.addEventListener("pointerup", (event) => finish(event, true));
  svg.addEventListener("pointercancel", (event) => finish(event, false));
  svg.addEventListener("lostpointercapture", (event) => finish(event, false));
  tools.append(pen, eraser, undo, clear);
  details.append(summary, tools, svg);
  refresh();
  return details;
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/coding-client.mjs
var LIMIT = 8192;
var encoder = new TextEncoder();
var palette = {
  comment: "color: var(--muted-foreground, #7a8494)",
  string: "color: light-dark(#075f48, #9de2bc)",
  number: "color: light-dark(#814512, #ffc684)",
  keyword: "color: light-dark(#6935a3, #d3aaff)"
};
var tokenPattern = /(\/\/[^\n]*|\/\*[\s\S]*?(?:\*\/|$))|(["'`])(?:\\[\s\S]|(?!\2)[^\\])*?(?:\2|$)|\b(\d+(?:[._]\d+)*)\b|\b(async|await|break|case|class|const|continue|default|delete|do|else|export|false|for|function|if|import|in|instanceof|let|new|null|of|return|static|super|switch|this|throw|true|try|typeof|undefined|var|void|while|yield)\b/g;
var css = `
  .lh-code-editor { display:grid; gap:8px; min-width:0; }
  .lh-code-editor label { min-width:0; }
  .lh-code-editor .lh-code-surface { position:relative; min-width:0; }
  :is(#lh-inline-lesson,.lh-code-editor) .lh-code-surface textarea[data-code-source], .lh-code-editor .lh-code-colors {
    font: 0.94rem/1.55 ui-monospace, Consolas, monospace;
    white-space: pre; tab-size: 2; box-sizing: border-box; padding: 10px 12px;
    border:1px solid var(--border,#6f7784); border-radius:8px; margin:0; width:100%;
  }
  .lh-code-editor .lh-code-colors {
    position:absolute; pointer-events:none; overflow:hidden; inset:0; height:100%;
    color:var(--foreground,CanvasText); background:var(--background,Canvas);
  }
  :is(#lh-inline-lesson,.lh-code-editor) .lh-code-surface textarea[data-code-source] {
    display:block; position:relative; color:transparent; caret-color:var(--foreground,CanvasText);
    background:transparent; resize:vertical; overflow:auto; -webkit-text-fill-color:transparent;
  }
  .lh-code-editor [data-code-source]:focus-visible { outline:2px solid var(--foreground,CanvasText); outline-offset:2px; }
  :is(#lh-inline-lesson,.lh-code-editor) .lh-code-surface textarea[data-code-source]::selection {
    background:Highlight; color:HighlightText; -webkit-text-fill-color:HighlightText;
  }
  .lh-code-editor [data-code-run] { justify-self:start; min-height:38px; padding:.45rem .7rem;
    background:var(--card,Canvas); border:1px solid var(--border,GrayText); border-radius:.5rem; }
  .lh-code-editor [data-code-status]:empty { display:none; }
  .lh-code-editor [data-code-observations] { margin:0; padding-inline-start:1.5rem; overflow-wrap:anywhere; }
  .lh-code-editor [data-code-observations]:empty { display:none; }
  @media (forced-colors: active) {
    .lh-code-editor .lh-code-colors { display:none; }
    :is(#lh-inline-lesson,.lh-code-editor) .lh-code-surface textarea[data-code-source] {
      color:CanvasText; background:Canvas; caret-color:CanvasText; -webkit-text-fill-color:CanvasText;
    }
  }
`;
function paintSource(doc, target, source) {
  const fragment = doc.createDocumentFragment();
  let position = 0;
  for (const match of source.matchAll(tokenPattern)) {
    fragment.append(source.slice(position, match.index));
    const token = doc.createElement("span");
    token.setAttribute("style", palette[match[1] ? "comment" : match[2] ? "string" : match[3] ? "number" : "keyword"]);
    token.textContent = match[0];
    fragment.append(token);
    position = match.index + match[0].length;
  }
  fragment.append(source.slice(position));
  if (source.endsWith("\n")) fragment.append(" ");
  target.replaceChildren(fragment);
}
function mountCodingEditor(root, { spec, value, onChange, onRun, onReceipt, observations, disabled = false }) {
  const doc = root.ownerDocument;
  const node = (tag, attributes = {}, text) => {
    const element = doc.createElement(tag);
    for (const [name, val] of Object.entries(attributes)) element.setAttribute(name, val);
    if (text !== void 0) element.textContent = text;
    return element;
  };
  const panel = node("div", { class: "lh-code-editor" });
  const label = node("label", { class: "lh-field" });
  const surface = node("div", { class: "lh-code-surface" });
  const colors = node("pre", { class: "lh-code-colors", "aria-hidden": "true" });
  const editor = node("textarea", {
    rows: "7",
    wrap: "off",
    maxlength: String(LIMIT),
    spellcheck: "false",
    autocapitalize: "off",
    autocomplete: "off",
    "data-code-source": ""
  });
  const run = node("button", { "data-code-run": "", type: "button" }, "Run tests");
  const output = node("ul", { "data-code-observations": "", "aria-label": "Test observations" });
  const status = node("span", { "data-code-status": "", role: "status", "aria-live": "polite" });
  const tests = Array.isArray(spec?.testNames) && spec.testNames.length > 0;
  let running = false;
  editor.value = typeof value === "string" ? value : spec?.starterCode ?? "";
  editor.disabled = disabled;
  const valid = () => editor.value.trim().length > 0 && encoder.encode(editor.value).length <= LIMIT;
  function setStatus(message, error = false) {
    status.setAttribute("role", error ? "alert" : "status");
    status.textContent = message;
  }
  function sync() {
    colors.scrollTop = editor.scrollTop;
    colors.scrollLeft = editor.scrollLeft;
  }
  function show(results) {
    const statusNames = { pass: "Passed", fail: "Failed", timeout: "Timed out", error: "Error" };
    output.replaceChildren(...(Array.isArray(results) ? results : []).map((result) => node(
      "li",
      {},
      result.name + " \u2014 " + (statusNames[result.status] ?? "Unknown") + (result.message ? ". " + result.message : result.actual !== void 0 ? ". Returned " + result.actual : "")
    )));
  }
  function updateButton() {
    run.disabled = disabled || running || !valid();
  }
  function render() {
    paintSource(doc, colors, editor.value);
    sync();
    updateButton();
  }
  editor.addEventListener("scroll", sync);
  editor.addEventListener("input", () => {
    onReceipt?.(void 0);
    show([]);
    setStatus(encoder.encode(editor.value).length > LIMIT ? "Use at most 8 KiB of code." : "");
    onChange?.(editor.value);
    render();
  });
  run.addEventListener("click", async () => {
    if (disabled || running || !valid() || typeof onRun !== "function") return;
    const source = editor.value;
    running = true;
    updateButton();
    onReceipt?.(void 0);
    show([]);
    setStatus("Running tests\u2026");
    try {
      const receipt = await onRun(source);
      if (!panel.isConnected || editor.value !== source) return;
      if (typeof receipt?.runId !== "string" || !Array.isArray(receipt.observations))
        throw new Error("No test observations returned. Run tests again.");
      show(receipt.observations);
      setStatus("Tests finished.");
      onReceipt?.(receipt);
    } catch (error) {
      if (panel.isConnected && editor.value === source) setStatus(error?.message ?? "Unable to run tests.", true);
    } finally {
      running = false;
      if (panel.isConnected && editor.value !== source) setStatus("");
      updateButton();
    }
  });
  label.append(node("span", { class: "lh-field-label" }, "JavaScript code"), surface);
  surface.append(colors, editor);
  panel.append(node("style", {}, css), label);
  if (tests && typeof onRun === "function") panel.append(run);
  if (tests && typeof onRun !== "function") panel.append(node("span", { class: "lh-secondary" }, "Open the connected lesson to run tests."));
  panel.append(status, output);
  root.append(panel);
  show(observations);
  render();
  return panel;
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/confidence-style.mjs
var CONFIDENCE_COLORS = ["#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e", "#10b981"];
function nearestConfidenceIndex(value) {
  let best = 0;
  for (let i = 1; i < CONFIDENCE_STOPS.length; i++)
    if (Math.abs(CONFIDENCE_STOPS[i] - value) < Math.abs(CONFIDENCE_STOPS[best] - value)) best = i;
  return best;
}
function confidenceRailStyle(value) {
  const color = CONFIDENCE_COLORS[CONFIDENCE_STOPS.indexOf(value)] ?? CONFIDENCE_COLORS[2];
  return {
    backgroundColor: "#141414",
    backgroundImage: [
      `linear-gradient(90deg, ${color} 0%, ${color} ${value}%, transparent ${value}%, transparent 100%)`,
      ...[30, 50, 70, 90].map(() => "linear-gradient(90deg, rgba(230,230,230,0.35), rgba(230,230,230,0.35))")
    ].join(", "),
    backgroundSize: ["100% 100%", "1px 100%", "1px 100%", "1px 100%", "1px 100%"].join(", "),
    backgroundPosition: ["0 0", ...[30, 50, 70, 90].map((p) => `${p}% 0`)].join(", "),
    backgroundRepeat: "no-repeat"
  };
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/answered-record.mjs
function answeredRecord(doc, answer, { richProse = false, externalRichExplanation = false, renderProse } = {}) {
  const node = (tag, text, attrs = {}) => {
    const e = doc.createElement(tag);
    if (text !== null) e.textContent = text;
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
    return e;
  };
  const box = node("article", null, { class: "lh-answer-record", "data-answer-record": answer.toolCallId });
  const prose = (tag, text) => {
    const element = node(tag, text);
    if (renderProse) renderProse(element, text);
    return element;
  };
  const quiz = answer.kind === "quiz", selected = new Set((answer.answers ?? []).map((a) => a.index)), correct = new Set(answer.correctIndices ?? []);
  if (!richProse) box.append(prose("div", answer.questionText));
  if (quiz) box.append(node("p", answer.dismissed ? "Skipped" : answer.dontKnow ? "Answered: I don't know" : answer.correct ? "Correct" : "Incorrect", { "data-answer-verdict": "" }));
  for (const option of answer.options ?? []) {
    const chosen = selected.has(option.index), right = quiz && correct.has(option.index);
    const row = node("div", null, { class: "lh-answer-option", "data-selected": chosen, "data-correct": right, "data-graded": quiz });
    row.append(node("span", `${chosen ? "Selected: " : ""}${right ? "Correct answer: " : ""}`), prose("span", option.label));
    box.append(row);
  }
  if (answer.coding) box.append(codingRecord(doc, answer.coding));
  else if (answer.text) box.append(node("p", answer.text));
  if (answer.other) box.append(node("p", `Other: ${answer.other}`));
  const drawing = savedDrawing(doc, answer.drawing);
  if (drawing) box.append(drawing);
  if (quiz && !answer.dontKnow && Number.isFinite(answer.confidence)) {
    const confidence = node("div", null, { class: "lh-answered-confidence", "data-answered-confidence": "" });
    const rail = node("span", null, { class: "lh-static-confidence-rail", "aria-hidden": "true" });
    Object.assign(rail.style, confidenceRailStyle(answer.confidence));
    confidence.append(rail, node("span", `Confidence: ${answer.confidence}%`));
    box.append(confidence);
  }
  for (const [label, text] of [["Your thinking", answer.thinking ?? answer.note], ["Thinking while reading", answer.readingThinking]]) if (text) {
    const details = node("details", null);
    details.append(node("summary", label), node("p", text));
    box.append(details);
  }
  if (quiz && answer.explanation && !externalRichExplanation) {
    const why = node("details", null, { "data-answer-why": "" });
    why.append(node("summary", "Why"), prose("div", answer.explanation));
    box.append(why);
  }
  if (answer.coding?.solution) {
    const solution = node("details", null);
    solution.append(node("summary", "Model solution"), node("pre", answer.coding.solution));
    box.append(solution);
  } else if (answer.kind === "explain" && answer.committed && !richProse) box.append(prose("div", `The answer: ${answer.committed}`));
  return box;
}
function codingRecord(doc, coding) {
  const box = doc.createElement("details"), label = doc.createElement("summary"), code = doc.createElement("pre");
  label.textContent = "Your code";
  code.textContent = coding.code;
  code.style.overflow = "auto";
  box.append(label, code);
  if (coding.observations?.length) {
    const tests = doc.createElement("ul");
    for (const test of coding.observations) {
      const item = doc.createElement("li");
      item.textContent = `${test.name}: ${test.status ?? (test.passed ? "passed" : "failed")}${test.detail ? " \u2014 " + test.detail : ""}`;
      tests.append(item);
    }
    box.append(tests);
  }
  return box;
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/practice-client.mjs
function mountPractice(root, initialView, options = {}) {
  const doc = root.ownerDocument, win = doc.defaultView;
  let view = initialView, text = "", open = true, pending = false, editVersion = 0, historyOpen = (initialView.feedback?.length ?? 0) > 0;
  let drawing = [], drawingHistory = [];
  const starter = (current) => current.codingAttempts?.at(-1)?.code ?? current.activeProblem?.coding?.starterCode ?? "";
  let code = starter(view), codingReceipt;
  let earlierRows = [], earlierCursor = view.earlierResponses ?? null, historyPending = false;
  const rich = createRichScope(options.renderRich);
  const key = () => lessonDraftKey(view);
  const node = (tag, value, attrs = {}) => {
    const e = doc.createElement(tag);
    if (value !== null) e.textContent = value;
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
    return e;
  };
  const button = (label, fn, attrs = {}) => {
    const e = node("button", label, { type: "button", ...attrs });
    e.addEventListener("click", fn);
    return e;
  };
  const prose = (tag, value, attrs = {}) => {
    const element = node(tag, null, attrs);
    rich.render(element, value);
    return element;
  };
  const status = (message, error = false) => {
    const e = root.querySelector("[data-status]");
    if (e) {
      e.textContent = message;
      e.setAttribute("role", error ? "alert" : "status");
    }
  };
  function save() {
    try {
      options.drafts?.write(key(), {
        key: key(),
        text,
        open,
        ...drawing.length ? { drawing } : {},
        ...view.activeProblem?.coding ? { code } : {}
      });
    } catch {
      status("The draft could not be saved. Keep this view open.", true);
    }
  }
  function restore() {
    try {
      const cached = options.drafts?.read(key());
      if (cached?.key === key() && typeof cached.text === "string" && cached.text.length <= 16e3) {
        text = cached.text;
        open = cached.open !== false;
        drawing = validDrawing(cached.drawing) ? cached.drawing : [];
        if (view.activeProblem?.coding && typeof cached.code === "string" && cached.code.length <= 8192) code = cached.code;
      }
    } catch {
    }
  }
  restore();
  async function send(type, input) {
    if (pending) return;
    pending = true;
    render();
    try {
      if (typeof options.send !== "function") throw new Error("Use the connected practice browser to save.");
      const oldKey = key(), versionAtSend = editVersion, baselineIds = (view.thinkingEntries ?? []).map((entry) => entry.id);
      const submitted = type === "practice-input" && input?.type === "thinking" && input.problemCallId === view.activeProblem?.toolCallId;
      const draftBefore = submitted ? JSON.stringify(options.drafts?.read(oldKey)) : void 0;
      const result = await options.send({ type, chatId: view.chatId, ...input ? { input } : {} });
      if (result?.requested === true) {
        status("Host action requested. Confirm delivery in chat; the saved lesson response will confirm persistence. If canceled, use Resume saved lesson.");
        return;
      }
      if (result?.delivered === true) {
        status(options.appPresentation ? "Sent. Waiting for the lesson to continue." : "Delivered to the owning agent. Waiting for the saved practice response.");
        return;
      }
      if (!result?.view || !(result.persisted || result.loaded)) throw new Error("No saved practice response received.");
      const same = result.view.activeProblem?.toolCallId === view.activeProblem?.toolCallId;
      const thinkingSaved = submitted && result.persisted === true && same && result.view.thinkingEntries?.some((entry) => !baselineIds.includes(entry.id) && practiceSubmissionIn(result.view, entry, input));
      if (thinkingSaved && editVersion === versionAtSend) try {
        if (JSON.stringify(options.drafts?.read(oldKey)) === draftBefore) options.drafts?.remove(oldKey);
      } catch {
      }
      if (result.view.feedback?.at(-1)?.id !== view.feedback?.at(-1)?.id) historyOpen = true;
      if (!same || result.view.revision !== view.revision) {
        codingReceipt = void 0;
        earlierRows = [];
        earlierCursor = result.view.earlierResponses ?? null;
      }
      view = result.view;
      pending = false;
      if (!same) {
        text = "";
        code = starter(view);
        drawing = [];
        drawingHistory = [];
        open = true;
        restore();
      } else if (thinkingSaved && editVersion === versionAtSend) {
        text = "";
        drawing = [];
        drawingHistory = [];
        open = true;
      }
      render();
      status(result.loaded ? "Saved practice reopened." : input?.type === "next" ? "Next problem requested." : thinkingSaved ? "Thinking saved." : "Saved response received; draft retained until matching thinking is confirmed.");
    } catch (error) {
      pending = false;
      render();
      status(error.message, true);
    }
  }
  function priorResponses(target) {
    for (const row of earlierRows) {
      if (row.text) target.append(node("p", `Your thinking: ${row.text}`));
      const drawing2 = savedDrawing(doc, row.drawing);
      if (drawing2) target.append(drawing2);
      if (row.coding) target.append(codingRecord(doc, row.coding));
    }
    if (earlierCursor && options.readPracticeHistory) {
      const control = button("Load earlier responses", async () => {
        if (historyPending) return;
        const cursor = earlierCursor, revision = view.revision;
        historyPending = true;
        control.disabled = true;
        try {
          const page = await options.readPracticeHistory(cursor);
          if (revision !== view.revision) return;
          if (page?.problemId !== cursor.problemId || !Array.isArray(page.rows)) throw new Error("Earlier responses could not be loaded.");
          earlierRows = [...page.rows, ...earlierRows];
          earlierCursor = page.nextBefore ? { problemId: cursor.problemId, before: page.nextBefore } : null;
          render();
          status("Earlier responses loaded.");
          root.querySelector("[data-earlier-responses]")?.focus();
        } catch (error) {
          status(error.message, true);
        } finally {
          historyPending = false;
          control.disabled = false;
        }
      }, { "data-earlier-responses": "" });
      target.append(control);
    }
  }
  function render() {
    rich.clear();
    root.replaceChildren();
    options.onPresentation?.({ open });
    const active = view.activeProblem;
    if (!active && options.exploration) {
      options.exploration.hidden = false;
      root.append(options.exploration);
    }
    if (view.conclusion && !options.richProse) {
      root.append(node("h3", "Problem review"), prose("div", view.conclusion.statement));
      for (const thought of view.conclusion.thinking ?? []) if (thought) root.append(node("p", `Your thinking: ${thought}`));
      root.append(prose("div", view.conclusion.verdict), node("h3", "Committed solution"));
      if (view.conclusion.codingLanguage) {
        const code2 = node("pre", view.conclusion.modelSolution);
        code2.style.overflow = "auto";
        root.append(code2);
      } else root.append(prose("div", view.conclusion.modelSolution));
    }
    if (view.conclusion && options.richProse) for (const thought of view.conclusion.thinking ?? []) root.append(node("p", `Your thinking: ${thought}`));
    if (!active) for (const record of view.drawings ?? []) {
      const saved = savedDrawing(doc, record.drawing);
      if (saved) root.append(saved);
    }
    if (!active) for (const attempt of view.codingAttempts ?? []) root.append(codingRecord(doc, attempt));
    if (!active) priorResponses(root);
    if (!options.richProse) for (const entry of view.discussion ?? []) root.append(entry.role === "user" ? node("p", `Your question: ${entry.text}`) : prose("div", entry.text));
    if (active) {
      const dock = node("section", null, { class: "lh-dock" });
      root.append(dock);
      if (!open) {
        dock.append(button("Practice problem \xB7 Reopen", () => {
          open = true;
          save();
          render();
        }, { class: "lh-reveal" }));
        if (options.workbench && options.exploration) root.append(options.exploration);
      } else {
        const heading = node("div", null, { class: "lh-heading" });
        heading.append(node("span", "Practice problem"), button("Close", () => {
          open = false;
          save();
          render();
        }, { class: "lh-close" }));
        dock.append(heading);
        const response = lessonResponseArea(dock, options);
        if (!options.richProse) response.append(prose("div", active.statement));
        const hasHistory = view.thinking.length > 0 || !options.richProse && (view.feedback?.length ?? 0) > 0;
        const history = options.workbench && hasHistory ? node("details", null, { class: "lh-practice-history" }) : response;
        if (history !== response) {
          history.open = historyOpen;
          history.addEventListener("toggle", () => {
            historyOpen = history.open;
          });
          history.append(node("summary", "Saved response and feedback"));
        }
        for (const thought of view.thinking) if (thought) history.append(node("p", `Your thinking: ${thought}`));
        for (const record of view.drawings ?? []) {
          const saved = savedDrawing(doc, record.drawing);
          if (saved) history.append(saved);
        }
        for (const attempt of view.codingAttempts ?? []) history.append(codingRecord(doc, attempt));
        priorResponses(history);
        if (!options.richProse) for (const entry of view.feedback ?? []) history.append(prose("div", entry.text, { "data-practice-feedback": entry.id }));
        const label = node("label", null, { class: "lh-field" });
        label.append(node("span", "Think out loud", { class: "lh-field-label" }));
        const field = node("textarea", null, { rows: options.workbench ? 3 : 4, "data-practice-thinking": "", maxlength: 16e3 });
        field.value = text;
        const canSubmit = () => !pending && (active.coding ? code.trim() && new TextEncoder().encode(code).length <= 8192 : text.trim());
        const updateSubmit = () => {
          const submit2 = root.querySelector("[data-practice-send]");
          if (submit2) submit2.disabled = !canSubmit();
        };
        field.addEventListener("input", () => {
          text = field.value;
          editVersion++;
          save();
          updateSubmit();
        });
        const submitWork = () => {
          if (canSubmit()) void send("practice-input", {
            type: "thinking",
            problemCallId: active.toolCallId,
            text,
            ...drawing.length ? { drawing } : {},
            ...active.coding ? { code, ...codingReceipt ? { codingRunId: codingReceipt.runId } : {} } : {}
          });
        };
        field.addEventListener("keydown", (event) => {
          if (!active.coding && event.key === "Enter" && (!event.shiftKey || event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            submitWork();
          }
        });
        if (active.coding) mountCodingEditor(response, {
          spec: active.coding,
          value: code,
          disabled: pending,
          observations: codingReceipt?.observations,
          onChange: (value) => {
            code = value;
            editVersion++;
            save();
            updateSubmit();
          },
          onReceipt: (receipt) => {
            codingReceipt = receipt;
          },
          onRun: options.runCoding ? (value) => options.runCoding(active.toolCallId, value) : void 0
        });
        label.append(field);
        response.append(label);
        if (!active.coding) response.append(node("span", "Enter sends \xB7 Shift+Enter newline", { class: "lh-secondary" }));
        if (options.allowDrawing !== false) response.append(drawingPad(doc, {
          value: drawing,
          disabled: pending,
          history: drawingHistory,
          onChange: (strokes) => {
            drawing = strokes;
            editVersion++;
            save();
          }
        }));
        const submit = button(active.coding ? "Submit code" : "Submit thinking", submitWork, { class: "lh-submit", "data-practice-send": "" });
        submit.disabled = !canSubmit();
        response.append(submit);
        if (history !== response) response.append(history);
      }
    } else if (view.conclusion) {
      const next = button("Next problem", () => void send("practice-input", { type: "next" }), { class: "lh-submit" });
      next.disabled = pending || view.nextAllowed;
      root.append(next);
      if (view.nextAllowed) root.append(node("p", "Next problem requested."));
    } else root.append(node("p", "No practice problem has been posed."));
    root.append(node("p", pending ? "Sending\u2026" : "", { "data-status": "", "aria-live": "polite", role: "status" }));
    if (!options.appPresentation) root.append(button("Resume saved lesson", () => options.onResume ? void options.onResume() : void send("resume"), { class: "lh-resume" }));
  }
  render();
  return { destroy() {
    rich.clear();
  }, readDraft: () => ({ text, open, pending }) };
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/lesson-prose.mjs
function richTextAllowed(text) {
  if (typeof text !== "string" || text.length > 65536) return false;
  const ordinary = /* @__PURE__ */ new Set(["", "mermaid", "text", "txt", "plaintext", "python", "py", "javascript", "js", "typescript", "ts", "json", "css", "bash", "sh", "shell", "powershell", "ps1", "sql", "java", "c", "cpp", "c++", "csharp", "c#", "go", "rust", "ruby", "rb", "r", "matlab", "latex", "tex", "smiles", "abc", "tikz"]);
  for (const match of text.matchAll(/(?:`{3,}|~{3,})[ \t]*([^\s`~]*)/g))
    if (!ordinary.has(match[1].toLowerCase())) return false;
  return !/(?:https?:|file:|data:|MEDIA:|!\s*\[|\]\s*\(|^\s{0,3}\[[^\]]+\]:|<\/?[a-z][^>]*>)/im.test(text);
}
function planDiagram(plan) {
  if (!plan || !Array.isArray(plan.nodes) || !Array.isArray(plan.edges)) return null;
  const ids = new Set(plan.nodes.map((n) => n.id));
  if (plan.nodes.some((n) => !/^[a-z0-9]+([_-][a-z0-9]+)*$/.test(n.id)) || plan.edges.some((e) => !ids.has(e.from) || !ids.has(e.to))) return null;
  const label = (s) => String(s).replace(/["\\\r\n<>&]/g, " ");
  return "```mermaid\nflowchart TD\n" + plan.nodes.map((n) => ` ${n.id}["${label(n.title)}"]`).join("\n") + "\n" + plan.edges.map((e) => ` ${e.from} --> ${e.to}`).join("\n") + "\n```";
}
function lessonProse(view, { open = true } = {}) {
  const result = [], add = (id, text) => {
    if (typeof text === "string" && text) result.push({ id, text });
  };
  if (view.kind === "practice") {
    if (view.conclusion) {
      add("review-statement", view.conclusion.statement);
      add("review-verdict", view.conclusion.verdict);
      add("review-solution", "### Committed solution\n\n" + view.conclusion.modelSolution);
    }
    for (const entry of view.discussion ?? []) add("discussion-" + entry.id, entry.role === "user" ? "Your question: " + entry.text : entry.text);
    if (view.activeProblem && open) {
      add("problem", view.activeProblem.statement);
      for (const f of view.feedback ?? []) add("feedback-" + f.id, f.text);
    }
    return result;
  }
  if (view.teachingText) add("teaching", view.teachingText);
  if (view.question && open) {
    add("question", view.question.question);
    add("context", view.question.context);
    for (const [index, option] of (view.question.options ?? []).entries()) add("option-" + index, `**Choice ${index + 1}**

${typeof option === "string" ? option : option.text ?? option.label ?? ""}`);
  }
  if (!view.question) {
    const answer = view.answers?.at(-1);
    if (answer) {
      add("answered-question", answer.questionText);
      add("revealed-answer", answer.committed);
    }
  }
  const diagram = planDiagram(view.plan);
  if (diagram) add("plan", diagram);
  const knowledge = view.knowledge?.nodes?.length ? planDiagram(view.knowledge.diagram) : null;
  if (knowledge) add("knowledge-map", "### Propositions from this lesson\n\n" + knowledge);
  return result;
}
function renderSettledExplanation(React2, MessageTextContent2, answer) {
  if (answer?.kind !== "quiz" || typeof answer.explanation !== "string" || !answer.explanation) return null;
  const text = answer.explanation;
  return React2.createElement(
    "details",
    { key: "why-" + answer.toolCallId, "data-learning-answer-why": "" },
    React2.createElement("summary", null, "Why"),
    richTextAllowed(text) && typeof MessageTextContent2 === "function" ? React2.createElement(MessageTextContent2, { text, media: false, decorateText: (children) => React2.createElement("span", null, children) }) : React2.createElement("pre", { style: { whiteSpace: "pre-wrap" } }, text)
  );
}
function renderLessonProse(React2, MessageTextContent2, view, state, choices) {
  const textContent = (text) => richTextAllowed(text) ? React2.createElement(MessageTextContent2, { text, media: false, decorateText: (children) => React2.createElement("span", null, children) }) : React2.createElement("pre", { style: { whiteSpace: "pre-wrap" } }, text);
  const q = view.question, external = typeof choices?.select === "function" && q && q.mode !== "text";
  return React2.createElement(
    "div",
    { "data-learning-prose": "", className: "lh-native-prose" },
    ...lessonProse(view, state).map((entry) => {
      if (external && /^option-\d+$/.test(entry.id)) {
        const index = Number(entry.id.slice(7)), option = q.options[index];
        const current = choices.questionId === q.toolCallId, disabled = !current || choices.pending === true;
        const select = () => {
          if (!disabled) choices.select(index, q.toolCallId);
        };
        return React2.createElement(
          "div",
          {
            key: entry.id,
            role: "button",
            className: "lh-option",
            tabIndex: disabled ? -1 : 0,
            "data-option": option.value,
            "data-learning-rich-choice": "",
            "aria-pressed": current && choices.selected?.includes(index) === true,
            "aria-disabled": disabled,
            onClick: (event) => {
              const nested = event.target?.closest?.('button,a,input,textarea,select,summary,[role="button"]');
              if (nested && nested !== event.currentTarget) return;
              select();
            },
            onKeyDown: (event) => {
              if (event.target !== event.currentTarget || event.altKey || event.ctrlKey || event.metaKey || !["Enter", " "].includes(event.key)) return;
              event.preventDefault();
              event.stopPropagation();
              select();
            }
          },
          textContent(entry.text),
          q.kind !== "quiz" && typeof option.description === "string" && option.description ? React2.createElement("span", { className: "lh-secondary" }, textContent(option.description)) : null
        );
      }
      return React2.createElement(
        "section",
        { key: entry.id, "data-learning-prose-part": entry.id },
        richTextAllowed(entry.text) ? React2.createElement(MessageTextContent2, {
          text: entry.text,
          media: false,
          // Core paragraphPlainText accepts only string children. Wrapping
          // every paragraph prevents nested transcript directives in prose.
          decorateText: (children) => React2.createElement("span", null, children)
        }) : React2.createElement("pre", { style: { whiteSpace: "pre-wrap" } }, entry.text)
      );
    }),
    view.kind === "practice" ? null : renderSettledExplanation(React2, MessageTextContent2, view.answers?.at(-1))
  );
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/inline-client.mjs
var INLINE_PREFIX = "lh.inline ";
function nativeTransport(win) {
  return async (action) => {
    const prompt = INLINE_PREFIX + JSON.stringify(action);
    if (typeof win.hermes?.send === "function") {
      if (prompt.length > 500) throw new Error("This answer is too long for Hermes\u2019s inline send. Keep the draft and use the host file/tool lane; nothing has been truncated.");
      const ack = await win.hermes.send(prompt);
      if (!ack?.ok) throw new Error(`Delivery failed: ${ack?.error ?? "undelivered"}. Your draft is retained.`);
      return { delivered: true };
    }
    if (typeof win.openai?.sendFollowUpMessage === "function") {
      await win.openai.sendFollowUpMessage({ prompt, title: action.type === "answer" ? "Submit this lesson answer" : "Resume the saved lesson" });
      return { requested: true };
    }
    throw new Error("Open this lesson in the host chat to submit. Your draft is retained.");
  };
}
function mountInline(root, initialView, options = {}) {
  if (initialView.kind === "practice") return mountPractice(root, initialView, options);
  const win = root.ownerDocument.defaultView;
  const doc = root.ownerDocument;
  const send = options.send ?? nativeTransport(win);
  const rich = createRichScope(options.renderRich);
  let destroyed = false;
  let view = initialView;
  let state = {
    selection: emptyDockSelection(),
    text: view.question?.coding?.starterCode ?? "",
    other: "",
    thinking: "",
    readingThinking: "",
    confidenceIndex: DEFAULT_CONFIDENCE_INDEX,
    open: view.question?.open ?? true,
    pending: false,
    drawing: []
  };
  let drawingHistory = [], codingReceipt;
  const draftKey = () => lessonDraftKey(view);
  function setStatus(message, error = false) {
    const status = root.querySelector("[data-status]");
    if (status) {
      status.textContent = message;
      status.setAttribute("role", error ? "alert" : "status");
    }
  }
  function save() {
    const snapshot = {
      key: draftKey(),
      selected: [...state.selection.selected],
      otherSelected: state.selection.otherSelected,
      dontKnow: state.selection.dontKnow,
      text: state.text,
      other: state.other,
      thinking: state.thinking,
      readingThinking: state.readingThinking,
      confidenceIndex: state.confidenceIndex,
      open: state.open,
      pending: state.pending,
      ...state.drawing.length ? { drawing: state.drawing } : {}
    };
    if (!options.drafts && typeof win.openai?.setWidgetState !== "function") return;
    const payload = { modelContent: null, privateContent: { lhInlineDraft: snapshot } };
    if (new TextEncoder().encode(JSON.stringify(payload)).length > 16 * 1024) {
      setStatus("This draft exceeds the host\u2019s saved-state limit. Keep this view open.", true);
      return;
    }
    try {
      Promise.resolve(options.drafts ? options.drafts.write(snapshot.key, payload) : win.openai.setWidgetState(payload)).catch(() => setStatus("The host could not save this draft. Keep this view open.", true));
    } catch {
      setStatus("The host could not save this draft. Keep this view open.", true);
    }
  }
  function restore(widgetState) {
    const s = widgetState?.privateContent?.lhInlineDraft;
    if (!s || s.key !== draftKey() || !view.question) return;
    const count = view.question.options.length;
    if (!Array.isArray(s.selected) || !s.selected.every((i) => Number.isInteger(i) && i >= 0 && i < count)) return;
    state = {
      ...state,
      selection: { selected: new Set(s.selected), otherSelected: s.otherSelected === true, dontKnow: s.dontKnow === true },
      text: typeof s.text === "string" ? s.text : "",
      other: typeof s.other === "string" ? s.other : "",
      thinking: typeof s.thinking === "string" ? s.thinking : "",
      readingThinking: typeof s.readingThinking === "string" ? s.readingThinking : "",
      confidenceIndex: Number.isInteger(s.confidenceIndex) && s.confidenceIndex >= 0 && s.confidenceIndex < CONFIDENCE_STOPS.length ? s.confidenceIndex : DEFAULT_CONFIDENCE_INDEX,
      open: typeof s.open === "boolean" ? s.open : state.open,
      pending: false,
      drawing: validDrawing(s.drawing) ? s.drawing : []
    };
  }
  let draftLoadError = false;
  try {
    restore(options.drafts ? options.drafts.read(draftKey()) : win.openai?.widgetState);
  } catch {
    draftLoadError = true;
  }
  function node(tag, text, attributes = {}) {
    const element = doc.createElement(tag);
    if (text !== null) element.textContent = text;
    for (const [key, value] of Object.entries(attributes)) if (value !== void 0) element.setAttribute(key, String(value));
    return element;
  }
  function button(text, handler, attributes = {}) {
    const b = node("button", text, { type: "button", ...attributes });
    b.addEventListener("click", handler);
    return b;
  }
  function prose(tag, text, attributes = {}) {
    const element = node(tag, null, attributes);
    rich.render(element, text);
    return element;
  }
  function field(label, name, placeholder) {
    const wrap = node("label", null, { class: "lh-field" });
    wrap.append(node("span", label, { class: "lh-field-label" }));
    const input = node("textarea", null, { rows: view.phase === "teach" ? 3 : 1, "data-field": name, placeholder });
    input.value = state[name];
    input.addEventListener("input", () => {
      state[name] = input.value;
      save();
      updateSubmit();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (!event.shiftKey || event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        if (name === "readingThinking" && !state.open) {
          state.open = true;
          save();
          render();
        } else if (name !== "readingThinking") void submit();
      }
    });
    wrap.append(input);
    return wrap;
  }
  function canSubmit() {
    const q = view.question;
    return q && !state.pending && (!q.coding || new TextEncoder().encode(state.text).length <= 8192) && (q.mode === "text" ? state.text.trim().length > 0 : state.selection.dontKnow || state.selection.selected.size > 0 || state.selection.otherSelected && state.other.trim().length > 0);
  }
  function renderLessonPanels() {
    if (view.assessment) {
      const assessment = node("details", null, { "data-assessment": "" });
      assessment.append(node("summary", "Starting assessment"));
      if (view.assessment.summary) assessment.append(node("p", view.assessment.summary));
      for (const strand of view.assessment.strands) assessment.append(node("p", `${strand.strand}: ${strand.assessment}`));
      root.append(assessment);
    }
    if (view.knowledge?.nodes?.length) {
      const knowledge = node("details", null, { "data-knowledge": "" });
      knowledge.append(node("summary", "Propositions from this lesson"));
      knowledge.append(node("p", view.knowledge.scope));
      for (const proposition of view.knowledge.nodes) {
        const detail = node("details", null, { "data-proposition": proposition.id });
        detail.append(node("summary", proposition.name), prose("div", proposition.statement));
        for (const passage of proposition.passages ?? []) detail.append(prose("blockquote", passage));
        knowledge.append(detail);
      }
      root.append(knowledge);
    }
  }
  function present() {
    const q = view.question;
    options.onPresentation?.({ open: state.open, ...options.externalChoices ? {
      questionId: q?.toolCallId ?? null,
      selected: [...state.selection.selected],
      pending: state.pending
    } : {} });
  }
  function updateSubmit() {
    const b = root.querySelector("[data-submit]");
    if (b) b.disabled = !canSubmit();
    if (options.externalChoices) present();
  }
  function selectOption(index, questionId) {
    const q = view.question;
    if (destroyed || !q || q.toolCallId !== questionId || q.mode === "text" || !state.open || state.pending || !Number.isInteger(index) || index < 0 || index >= q.options.length) return false;
    state.selection = toggleOption(q.mode, state.selection, index);
    save();
    render();
    return true;
  }
  function answerRequest() {
    const q = view.question;
    const request = {};
    if (q.mode === "text") {
      request.text = state.text;
      if (q.coding && state.thinking.trim()) request.thinking = state.thinking;
      if (q.coding && codingReceipt) request.codingRunId = codingReceipt.runId;
    } else {
      request.dontKnow = state.selection.dontKnow;
      request.values = [...state.selection.selected].map((i) => q.options[i].value);
      if (state.selection.otherSelected) request.other = state.other;
      if (state.thinking.trim()) request.thinking = state.thinking;
      if (q.kind === "quiz" && !state.selection.dontKnow) request.confidence = CONFIDENCE_STOPS[state.confidenceIndex];
    }
    if (state.readingThinking.trim()) request.readingThinking = state.readingThinking;
    if (state.drawing.length) request.drawing = state.drawing;
    return request;
  }
  async function deliver(action) {
    try {
      const ack = await send(action);
      if (ack?.view && (ack.persisted === true || ack.loaded === true)) {
        applyView(ack.view);
        setStatus(ack.loaded ? "Saved lesson reopened." : action.type === "approve" ? "Plan approval saved." : "Answer saved.");
        return;
      }
      setStatus(ack?.delivered ? options.appPresentation ? "Answer sent. Waiting for the lesson to continue." : "Delivered to the host. Waiting for the saved lesson response." : "Host action requested. Waiting for the saved lesson response.");
    } catch (error) {
      state.pending = false;
      save();
      updateSubmit();
      setStatus(error.message, true);
    }
  }
  async function submit() {
    if (!canSubmit()) return;
    const action = { type: "answer", chatId: view.chatId, toolCallId: view.question.toolCallId, request: answerRequest() };
    state.pending = true;
    save();
    updateSubmit();
    setStatus("Sending answer\u2026");
    await deliver(action);
  }
  function renderPlan() {
    if (!view.plan) return;
    const details = node("details", null, { class: "lh-plan" });
    details.append(node("summary", view.plan.approved ? "Lesson plan" : "Proposed lesson plan"));
    const list = node("ol", null);
    for (const item of view.plan.nodes) list.append(node("li", `${item.title} \xB7 ${item.status}`, { "data-node-id": item.id }));
    details.append(list);
    const diagram = planDiagram(view.plan);
    if (diagram && options.renderRich && !options.richProse) details.append(prose("div", diagram));
    if (!view.plan.approved) {
      details.open = true;
      details.append(button("Start this plan", () => {
        state.pending = true;
        save();
        void deliver({ type: "approve", chatId: view.chatId, planRevision: view.plan.planRevision, text: "Start this plan." });
      }, { class: "lh-submit", "data-approve": "" }));
    }
    root.append(details);
  }
  function render() {
    rich.clear();
    root.replaceChildren();
    if (!options.appPresentation) renderLessonPanels();
    const q = view.question;
    present();
    const previous = q && view.answers.length ? node("details", null, { "data-previous-answer": "" }) : null;
    if (previous) {
      previous.append(node("summary", "Previous answer"), answeredRecord(doc, view.answers.at(-1), { externalRichExplanation: options.richProse, renderProse: rich.render }));
      if (!options.appPresentation) root.append(previous);
    }
    if (!q) {
      if (options.exploration) {
        options.exploration.hidden = false;
        root.append(options.exploration);
      }
      const last = view.answers.at(-1);
      if (last) root.append(answeredRecord(doc, last, { richProse: options.richProse, externalRichExplanation: options.richProse, renderProse: rich.render }));
      renderPlan();
    } else {
      if (view.teachingText && !options.richProse) root.append(prose("div", view.teachingText, { class: "lh-teaching" }));
      if (q.needsReveal) root.append(field("Thinking while reading", "readingThinking", "Whatever comes to mind as you read."));
      const dock = node("section", null, { class: "lh-dock" });
      root.append(dock);
      if (!state.open) {
        dock.append(button(q.needsReveal ? "Check your understanding \xB7 Open" : `${q.questionType === "predict" ? "Prediction" : "Question"} \xB7 Reopen`, () => {
          state.open = true;
          save();
          render();
        }, { class: "lh-reveal", "data-reveal": "" }));
        if (options.workbench && options.exploration) root.append(options.exploration);
      } else {
        const heading = node("div", null, { class: "lh-heading" });
        const label = q.questionType === "predict" ? "Prediction" : q.tool === "probe" ? "Probe" : q.tool === "recall" ? "Recall" : q.kind === "ask" ? "Question" : "Check";
        if (!options.appPresentation || q.questionType === "predict") heading.append(node("span", label, { class: "lh-kind" }));
        const close = button(options.appPresentation ? "Hide question" : "Close", () => {
          state.open = false;
          save();
          render();
        }, { class: "lh-close", "data-close": "" });
        if (!options.appPresentation) heading.append(close);
        if (heading.childElementCount) dock.append(heading);
        const response = lessonResponseArea(dock, options);
        if (!options.richProse) response.append(prose("div", q.question, { class: "lh-question-text" }));
        if (q.context && !options.richProse) response.append(prose("div", q.context));
        if (q.mode !== "text") {
          const group = node("div", null, { role: "group", "aria-label": q.mode === "multi-select" ? "Choose all that apply" : "Choose an answer" });
          if (!options.externalChoices) q.options.forEach((option, index) => {
            const row = button(
              null,
              () => {
                selectOption(index, q.toolCallId);
              },
              { class: "lh-option", "aria-pressed": state.selection.selected.has(index), "data-option": option.value }
            );
            row.append(prose("span", `${index + 1}. ${option.label}`, { class: "lh-choice-text" }));
            if (q.kind !== "quiz" && option.description) row.append(prose("span", option.description, { class: "lh-secondary" }));
            group.append(row);
          });
          if (q.kind === "ask") {
            group.append(button("Other\u2026", () => {
              state.selection = toggleOther(q.mode, state.selection);
              save();
              render();
            }, { class: "lh-option", "aria-pressed": state.selection.otherSelected }));
            if (state.selection.otherSelected) group.append(field("Other", "other", "Your response."));
          }
          if (q.kind === "quiz") group.append(button(
            "I don't know",
            () => {
              state.selection = { selected: /* @__PURE__ */ new Set(), otherSelected: false, dontKnow: !state.selection.dontKnow };
              save();
              render();
            },
            { class: "lh-option", "aria-pressed": state.selection.dontKnow, "data-dont-know": "" }
          ));
          response.append(group);
          if (q.kind === "quiz") {
            const confidence = node("label", null, { class: "lh-confidence" });
            const slider = node("input", null, {
              type: "range",
              min: 0,
              max: 100,
              step: 1,
              "aria-label": "Confidence \u2014 the probability your selected answer is correct",
              "data-confidence": ""
            });
            slider.value = CONFIDENCE_STOPS[state.confidenceIndex];
            slider.disabled = state.selection.dontKnow;
            slider.setAttribute("aria-valuetext", `${CONFIDENCE_STOPS[state.confidenceIndex]} percent`);
            const track = node("span", null, { class: "lh-confidence-track" }), rail = node("span", null, { class: "lh-confidence-rail", "aria-hidden": "true" });
            const paint2 = () => {
              Object.assign(rail.style, confidenceRailStyle(CONFIDENCE_STOPS[state.confidenceIndex]));
              slider.style.setProperty("--lh-confidence-color", CONFIDENCE_COLORS[state.confidenceIndex]);
            };
            paint2();
            track.append(rail, slider);
            const value = node("output", state.selection.dontKnow ? "\u2014" : `${CONFIDENCE_STOPS[state.confidenceIndex]}%`);
            const change = (index) => {
              state.confidenceIndex = index;
              slider.value = CONFIDENCE_STOPS[index];
              value.textContent = `${CONFIDENCE_STOPS[index]}%`;
              slider.setAttribute("aria-valuetext", `${CONFIDENCE_STOPS[index]} percent`);
              paint2();
              save();
            };
            slider.addEventListener("input", () => {
              const raw = Number(slider.value);
              if (!Number.isFinite(raw) || raw < 0 || raw > 100 || slider.disabled) return;
              change(nearestConfidenceIndex(raw));
            });
            slider.addEventListener("keydown", (event) => {
              if (slider.disabled || event.altKey || event.ctrlKey || event.metaKey || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
              event.preventDefault();
              change(Math.max(0, Math.min(CONFIDENCE_STOPS.length - 1, state.confidenceIndex + (event.key === "ArrowRight" ? 1 : -1))));
            });
            confidence.append(node("span", "Confidence"), track, value);
            response.append(confidence);
          }
        }
        if (q.coding) {
          mountCodingEditor(response, {
            spec: q.coding,
            value: state.text,
            disabled: state.pending,
            observations: codingReceipt?.observations,
            onChange: (code) => {
              state.text = code;
              save();
              updateSubmit();
            },
            onReceipt: (receipt) => {
              codingReceipt = receipt;
            },
            onRun: options.runCoding ? (code) => options.runCoding(q.toolCallId, code) : void 0
          });
          response.append(field("Your thinking", "thinking", "Explain the reasoning behind your code."));
        } else response.append(q.mode === "text" ? field("Your answer", "text", "Type your answer.") : field("Your thinking", "thinking", "Why this answer? Whatever comes to mind."));
        if (options.allowDrawing !== false) response.append(drawingPad(doc, {
          value: state.drawing,
          disabled: state.pending,
          history: drawingHistory,
          onChange: (drawing) => {
            state.drawing = drawing;
            save();
          }
        }));
        const footer = node("div", null, { class: "lh-footer" });
        if (!q.coding) footer.append(node("span", "Enter submits \xB7 Shift+Enter newline", { class: "lh-secondary" }));
        footer.append(button(q.coding ? "Submit code" : "Submit answer", () => void submit(), { class: "lh-submit", "data-submit": "" }));
        response.append(footer);
        if (options.appPresentation) response.append(close);
      }
      renderPlan();
    }
    root.append(node("p", state.pending ? "Waiting for the saved lesson response." : "", { "data-status": "", "aria-live": "polite", role: "status" }));
    if (options.appPresentation) {
      if (previous) root.append(previous);
      renderLessonPanels();
    } else root.append(button("Resume saved lesson", () => {
      if (options.onResume) {
        void options.onResume();
        return;
      }
      state.pending = true;
      save();
      void deliver({ type: "resume", chatId: view.chatId });
    }, { class: "lh-resume", "data-resume": "" }));
    updateSubmit();
  }
  function applyView(next) {
    if (next.chatId !== view.chatId) throw new Error("The saved response belongs to a different lesson.");
    const same = next.question?.toolCallId === view.question?.toolCallId;
    if (!same || next.revision !== view.revision) codingReceipt = void 0;
    view = next;
    if (!same) {
      drawingHistory = [];
      state = {
        selection: emptyDockSelection(),
        text: next.question?.coding?.starterCode ?? "",
        other: "",
        thinking: "",
        readingThinking: "",
        confidenceIndex: DEFAULT_CONFIDENCE_INDEX,
        open: next.question?.open ?? true,
        pending: false,
        drawing: []
      };
    } else state.pending = false;
    if (!same && options.drafts) {
      try {
        restore(options.drafts.read(draftKey()));
      } catch {
      }
    }
    render();
  }
  const onGlobals = (event) => {
    restore(event.detail?.globals?.widgetState);
    render();
  };
  win.addEventListener("openai:set_globals", onGlobals);
  render();
  if (draftLoadError) setStatus("The saved draft could not be restored. The saved lesson is unchanged.", true);
  return {
    applyView,
    submit,
    selectOption,
    readDraft: () => ({ ...state, selection: { ...state.selection, selected: new Set(state.selection.selected) } }),
    destroy: () => {
      destroyed = true;
      rich.clear();
      win.removeEventListener("openai:set_globals", onGlobals);
    }
  };
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/hermes-native-port.mjs
var bytes = (value) => new TextEncoder().encode(JSON.stringify(value)).length;
function requirePort(ok, message) {
  if (!ok) throw new Error(message);
}
function createHermesLessonPort(ownerSessionId, view, { composer, storage }) {
  requirePort(typeof ownerSessionId === "string" && ownerSessionId.length > 0 && ownerSessionId.length <= 300 && ownerSessionId === ownerSessionId.trim() && ownerSessionId !== "new", "An exact owning Hermes session is required.");
  requirePort(typeof view.chatId === "string" && view.chatId.length > 0 && view.chatId.length <= 100 && Number.isSafeInteger(view.revision) && view.revision >= 0, "Invalid bound lesson view.");
  requirePort(typeof composer?.submit === "function" && ["get", "set", "remove"].every((k) => typeof storage?.[k] === "function"), "Supported Hermes composer/storage ports are unavailable.");
  const kind = view.kind === "practice" ? "practice" : "teach";
  const key = lessonDraftKey(view);
  const slot = "draft:v1:" + JSON.stringify([ownerSessionId, view.chatId, key]);
  function checkKey(requested) {
    requirePort(requested === key, "Draft key does not belong to this owner/question.");
  }
  const drafts = {
    read(requested) {
      checkKey(requested);
      const saved = storage.get(slot, null);
      if (!saved || saved.owner !== ownerSessionId || saved.chatId !== view.chatId || saved.key !== key || !Number.isSafeInteger(saved.baseRevision) || saved.baseRevision > view.revision || bytes(saved) > 16384) return null;
      const submitted = saved.submission;
      if (kind === "practice" && submitted && submitted.draftId === saved.draftId && samePracticeSubmission(submitted, saved.payload) && Array.isArray(submitted.baselineIds) && view.thinkingEntries?.some((entry) => !submitted.baselineIds.includes(entry.id) && practiceSubmissionIn(view, entry, submitted))) {
        storage.remove(slot);
        return null;
      }
      return saved.payload;
    },
    write(requested, payload) {
      checkKey(requested);
      const previous = storage.get(slot, null);
      requirePort(!previous || previous.baseRevision <= view.revision, "A newer card owns this draft; keep this card open.");
      const sameDraft = previous?.key === key && (kind === "practice" ? samePracticeSubmission(previous.payload, payload) : JSON.stringify(previous.payload) === JSON.stringify(payload));
      const saved = {
        owner: ownerSessionId,
        chatId: view.chatId,
        key,
        baseRevision: view.revision,
        payload,
        draftId: sameDraft && previous.draftId ? previous.draftId : globalThis.crypto.randomUUID(),
        submission: sameDraft ? previous.submission : null
      };
      requirePort(bytes(saved) <= 16384, "Native draft exceeds the 16 KiB task limit; keep the card open.");
      storage.set(slot, saved);
      requirePort(JSON.stringify(storage.get(slot, null)) === JSON.stringify(saved), "Hermes did not retain this draft; keep the card open.");
    },
    remove(requested) {
      checkKey(requested);
      storage.remove(slot);
    }
  };
  return { drafts, async send(action) {
    requirePort(action?.chatId === view.chatId && (kind === "practice" ? ["practice-input", "resume", "job-error"] : ["answer", "approve", "resume", "job-error"]).includes(action.type), "Action does not belong to this bound lesson.");
    const envelope = { v: 1, ownerSessionId, chatId: view.chatId, kind, expectedRevision: view.revision, action };
    const prompt = "lh.native " + JSON.stringify(envelope);
    requirePort(new TextEncoder().encode(prompt).length <= 65536, "Native input exceeds 64 KiB; nothing was truncated or sent.");
    let submission = null;
    if (kind === "practice" && action.type === "practice-input" && action.input?.type === "thinking") {
      const saved = storage.get(slot, null);
      requirePort(!saved || saved.baseRevision <= view.revision, "A newer card owns this draft; nothing was sent.");
      if (saved?.draftId && Number.isSafeInteger(saved.baseRevision) && samePracticeSubmission(saved.payload, action.input) && Array.isArray(view.thinkingEntries)) {
        submission = {
          before: JSON.stringify(saved),
          draftId: saved.draftId,
          text: action.input.text,
          ...action.input.code !== void 0 ? { code: action.input.code } : {},
          ...action.input.drawing ? { drawing: action.input.drawing } : {},
          baselineIds: view.thinkingEntries.map((entry) => entry.id)
        };
      }
    }
    requirePort(composer.submit(ownerSessionId, prompt) === true, "The owning Hermes composer is unavailable; draft retained.");
    if (submission) {
      try {
        const current = storage.get(slot, null);
        if (current?.baseRevision <= view.revision && JSON.stringify(current) === submission.before) {
          const { before, ...identity } = submission;
          const marked = { ...current, submission: identity };
          if (bytes(marked) <= 16384) storage.set(slot, marked);
        }
      } catch {
      }
    }
    return { delivered: true, ownerSessionId };
  } };
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/vendor/runtime/demo-pure.ts
var DEMO_BRIDGE_SCRIPT = `<script>(function(){
var send=function(m){try{parent.postMessage(m,"*")}catch(e){}};
var post=function(){
var b=document.body;
if(!b){send({type:"demo-resize",height:document.documentElement.scrollHeight});return}
var h=Math.max(b.scrollHeight,b.getBoundingClientRect().height);
var cs=getComputedStyle(b);
h+=(parseFloat(cs.marginTop)||0)+(parseFloat(cs.marginBottom)||0);
send({type:"demo-resize",height:Math.ceil(h)})
};
if(typeof ResizeObserver!=="undefined"){new ResizeObserver(post).observe(document.documentElement)}
window.addEventListener("resize",post);
window.addEventListener("load",post);
window.addEventListener("error",function(e){send({type:"demo-error",message:e.message||String(e)})});
setTimeout(post,50);
setTimeout(post,400);
})();<\/script>`;
function buildDemoSrcDoc(html) {
  if (/<\/body>/i.test(html)) return html.replace(/<\/body>/i, `${DEMO_BRIDGE_SCRIPT}</body>`);
  return `${html}${DEMO_BRIDGE_SCRIPT}`;
}
var INITIAL_DEMO_BRIDGE_STATE = { height: null, error: null };
var MIN_HEIGHT = 80;
var MAX_HEIGHT = 2400;
function reduceDemoBridgeState(state, data) {
  if (typeof data !== "object" || data === null) return state;
  const message = data;
  if (message.type === "demo-resize") {
    if (typeof message.height !== "number" || !Number.isFinite(message.height) || message.height <= 0) return state;
    const height = Math.min(Math.max(Math.round(message.height), MIN_HEIGHT), MAX_HEIGHT);
    return height === state.height ? state : { ...state, height };
  }
  if (message.type === "demo-error") {
    const text = typeof message.message === "string" && message.message.trim() ? message.message : "unknown error";
    return text === state.error ? state : { ...state, error: text };
  }
  return state;
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/visuals-view.mjs
var lessonVisualRows = (view) => (view.visuals ?? []).map((artifact) => ({ id: "visual-" + artifact.id, kind: artifact.kind, activity: artifact.title, execution: "saved", directVisual: true, artifact }));

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/artifacts.mjs
function demoDocument(html) {
  const policy = '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; script-src &#39;unsafe-inline&#39;; style-src &#39;unsafe-inline&#39;; img-src data: blob:; font-src data:; connect-src &#39;none&#39;; frame-src &#39;none&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">';
  return "<!doctype html><html><head>" + policy + "</head><body>" + buildDemoSrcDoc(html) + "</body></html>";
}
async function readArtifact(files, binding, descriptor) {
  if (!descriptor || !["demo", "visual"].includes(descriptor.kind) || !/^[a-f0-9]{64}$/.test(descriptor.sha256 ?? "") || descriptor.file !== `asset-${descriptor.kind}-${descriptor.sha256}.${descriptor.kind === "demo" ? "html" : "svg"}` || !Number.isSafeInteger(descriptor.size) || descriptor.size < 1 || descriptor.size > 1048576) throw new Error("Invalid saved artifact identity.");
  const result = await files.readText(binding.folder, descriptor.file);
  if (!result.ok || typeof result.text !== "string") throw new Error("The granted artifact is unavailable.");
  const bytes2 = new TextEncoder().encode(result.text);
  if (bytes2.length !== descriptor.size) throw new Error("Artifact size changed.");
  const sum = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes2)), (value) => value.toString(16).padStart(2, "0")).join("");
  if (sum !== descriptor.sha256) throw new Error("Artifact differs from its saved identity.");
  return result.text;
}
function createJobArtifacts(React2) {
  const h = React2.createElement;
  function Artifact({ job, ctx, binding, view, port }) {
    const [source, setSource] = React2.useState(null), [error, setError] = React2.useState(""), [bridge, setBridge] = React2.useState(INITIAL_DEMO_BRIDGE_STATE);
    const frame = React2.useRef(null), mounted = React2.useRef(false);
    React2.useEffect(() => {
      let disposed = false;
      mounted.current = true;
      setSource(null);
      setError("");
      setBridge(INITIAL_DEMO_BRIDGE_STATE);
      readArtifact(ctx.files, binding, job.artifact).then((text) => {
        if (!disposed) setSource(text);
      }).catch(() => {
        if (!disposed) setError("Saved artifact could not be verified; no alternate path was read.");
      });
      return () => {
        disposed = true;
        mounted.current = false;
      };
    }, [job.artifact.file]);
    React2.useEffect(() => {
      if (job.kind !== "demo") return;
      const receive = (event) => {
        if (event.source === frame.current?.contentWindow) {
          const data = event.data;
          const bounded = data?.type === "demo-error" ? { type: "demo-error", message: typeof data.message === "string" ? data.message.slice(0, 2e3) : "unknown error" } : data;
          setBridge((old) => reduceDemoBridgeState(old, bounded));
        }
      };
      window.addEventListener("message", receive);
      return () => window.removeEventListener("message", receive);
    }, [job.kind]);
    const report = async () => {
      if (!mounted.current || !bridge.error) return;
      try {
        await port.send({ type: "job-error", chatId: view.chatId, jobId: job.id, artifactSha256: job.artifact.sha256, error: bridge.error.slice(0, 2e3) });
        if (mounted.current) setError("Report sent to the owning teacher; this is not an automatic repair or saved-feedback claim.");
      } catch {
        if (mounted.current) setError("Owning conversation unavailable; report was not sent.");
      }
    };
    return h(
      "section",
      null,
      h("h4", null, job.artifact.title),
      error ? h("p", { role: "status" }, error) : null,
      source ? job.kind === "demo" ? h("iframe", { ref: frame, title: job.artifact.title, sandbox: "allow-scripts", referrerPolicy: "no-referrer", srcDoc: demoDocument(source), style: { width: "100%", height: bridge.height ?? 320, border: 0 } }) : h("img", { alt: job.artifact.title, src: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(source), style: { maxWidth: "100%" } }) : h("p", null, "Loading verified artifact."),
      bridge.error ? h("div", null, h("pre", null, bridge.error), !job.directVisual ? h("button", { type: "button", onClick: report }, "Send error to teacher") : null) : null
    );
  }
  return function JobArtifacts({ ctx, binding, view, port }) {
    const rows = [...view.jobs?.jobs ?? [], ...lessonVisualRows(view)];
    return h(
      "section",
      { "aria-label": "Materials and supporting work" },
      view.materials?.length ? h("section", null, h("h3", null, "Attached materials"), h("ul", null, ...view.materials.map((item) => h("li", { key: item.id }, `${item.label} (${item.kind}) \u2014 attached source; raw contents stay private.`)))) : null,
      rows.length ? h("h3", null, "Supporting work") : null,
      ...rows.map((job) => h(
        "article",
        { key: job.id },
        h("p", null, `${job.kind}: ${job.activity} (${job.execution})`),
        job.error ? h("pre", null, job.error) : null,
        job.research ? h("section", null, h("p", null, job.research.brief), h("ul", null, ...job.research.sources.map((source, index) => h("li", { key: index }, h("a", { href: source.url, target: "_blank", rel: "noopener noreferrer" }, source.title))))) : null,
        job.pdf ? h("section", null, h("p", null, job.pdf.brief), h("p", null, `Reader-reported pages read: ${job.pdf.pagesRead.join(", ")}. Consulted: ${job.pdf.pagesConsulted.join(", ")}.`)) : null,
        job.artifact ? h(Artifact, { job, ctx, binding, view, port }) : null
      )),
      view.jobs?.nextOffset !== null && view.jobs?.nextOffset !== void 0 ? h("p", null, `Showing ${rows.length} of ${view.jobs.total}; the teacher can retrieve further job pages.`) : null
    );
  };
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/hermes-contribution.mjs
async function verifyProjectionBytes(snapshot, text) {
  const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot);
  if (!match || !globalThis.crypto?.subtle) throw new Error("Snapshot content verification is unavailable.");
  const bytes2 = new TextEncoder().encode(text);
  const sum = new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", bytes2));
  const actual = Array.from(sum, (byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actual !== match[3]) throw new Error("Snapshot bytes differ from their projection identity.");
}
function registerHermesLearning(ctx, { host: host2, React: React2, MessageTextContent: MessageTextContent2, bindings, onUnbound, onReconnect }) {
  const JobArtifacts = createJobArtifacts(React2);
  const owned = bindings.map((binding) => Object.freeze({ ...binding }));
  if (owned.some((b) => typeof b.ownerSessionId !== "string" || !b.ownerSessionId || b.ownerSessionId !== b.ownerSessionId.trim() || b.ownerSessionId === "new" || !["teach", "practice"].includes(b.kind) || !b.chatId || !b.folder || b.minimumRevision !== void 0 && (!Number.isSafeInteger(b.minimumRevision) || b.minimumRevision < 0))) throw new Error("Explicit owner/lesson/export-folder bindings required.");
  function LessonLeaf({ binding, snapshot, revision, reconnect }) {
    const ref = React2.useRef(null);
    const control = React2.useRef(null);
    const highestRevision = React2.useRef(Math.max(revision, binding.minimumRevision ?? 0));
    const [view, setView] = React2.useState(null);
    const [reload, setReload] = React2.useState(0);
    const [busy, setBusy] = React2.useState(true);
    const [error, setError] = React2.useState("");
    const [presentation, setPresentation] = React2.useState({ open: true });
    const rich = typeof MessageTextContent2 === "function";
    React2.useEffect(() => {
      let disposed = false, controller;
      const root = ref.current;
      root.inert = true;
      setView(null);
      setBusy(true);
      setError("");
      root.textContent = "Loading saved lesson.";
      (async () => {
        const view2 = await loadCurrentProjection(ctx.files, binding, Math.max(revision, highestRevision.current, binding.minimumRevision ?? 0), verifyProjectionBytes);
        if (disposed) return;
        highestRevision.current = view2.revision;
        setPresentation({ open: view2.question?.open ?? true });
        setView(view2);
        const ports = createHermesLessonPort(binding.ownerSessionId, view2, { composer: host2.composer, storage: ctx.storage });
        controller = mountInline(root, view2, {
          ...ports,
          richProse: rich,
          externalChoices: rich,
          onResume: refresh,
          onPresentation: (next) => {
            if (!disposed) setPresentation((old) => old.open === next.open && old.questionId === next.questionId && old.pending === next.pending && JSON.stringify(old.selected) === JSON.stringify(next.selected) ? old : next);
          }
        });
        control.current = controller;
        root.inert = false;
        setBusy(false);
      })().catch((error2) => {
        if (!disposed) {
          root.textContent = "";
          setError(error2.message);
          setBusy(false);
        }
      });
      return () => {
        disposed = true;
        if (control.current === controller) control.current = null;
        controller?.destroy();
      };
    }, [binding, snapshot, revision, rich, reload]);
    function refresh() {
      if (ref.current) ref.current.inert = true;
      setView(null);
      setBusy(true);
      setReload((value) => value + 1);
    }
    return React2.createElement(
      "section",
      { className: "lh-native-lesson" },
      React2.createElement("button", { type: "button", disabled: busy, onClick: refresh }, "Refresh saved lesson"),
      reconnect?.(Math.max(revision, highestRevision.current)),
      error ? React2.createElement("p", { role: "alert" }, error) : null,
      rich && view ? renderLessonProse(React2, MessageTextContent2, view, presentation, {
        ...presentation,
        select: (index, questionId) => control.current?.selectOption(index, questionId)
      }) : null,
      React2.createElement("div", { ref }),
      view ? React2.createElement(JobArtifacts, { ctx, binding, view, port: createHermesLessonPort(binding.ownerSessionId, view, { composer: host2.composer, storage: ctx.storage }) }) : null
    );
  }
  return ctx.register({ id: "learning-inline", area: "transcript.directives", data: {
    name: "lh-lesson",
    render(props) {
      const binding = owned.find((b) => b.ownerSessionId === props.sessionId && b.chatId === props.attrs.lesson);
      const match = /^(teach|practice)-r([0-9]+)-[a-f0-9]{64}\.json$/.exec(props.attrs.snapshot ?? "");
      if (!match || !Number.isSafeInteger(Number(match[2])) || Object.keys(props.attrs).some((k) => !["lesson", "snapshot"].includes(k)))
        return React2.createElement("p", null, "This learning card has no approved owning-session binding.");
      if (props.streaming) return React2.createElement("p", null, "Waiting for the saved lesson export.");
      if (!binding) return onUnbound ? onUnbound(props) : React2.createElement("p", null, "Connect this lesson to its export folder first.");
      if (match[1] !== binding.kind) return React2.createElement("p", null, "Snapshot mode differs from its configured lesson.");
      return React2.createElement(LessonLeaf, {
        key: JSON.stringify([binding.ownerSessionId, binding.kind, binding.chatId]),
        binding,
        snapshot: props.attrs.snapshot,
        revision: Number(match[2]),
        reconnect: onReconnect ? (minimumRevision) => onReconnect({ ...props, minimumRevision }) : void 0
      });
    }
  } });
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/connect-export.mjs
async function connectLessonExport(ctx, { owner, chatId, snapshot, minimumRevision }, { isCurrent, verifyBytes, install }) {
  const cancelled = () => ({ connected: false, cancelled: true });
  if (!isCurrent()) return cancelled();
  const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot ?? "");
  if (typeof owner !== "string" || !owner || owner !== owner.trim() || owner === "new" || !/^[A-Za-z0-9_-]{1,80}$/.test(chatId ?? "") || !match) throw new Error("Invalid explicit lesson identity.");
  minimumRevision = minimumRevision ?? Number(match[2]);
  if (!Number.isSafeInteger(minimumRevision) || minimumRevision < Number(match[2])) throw new Error("Invalid current lesson revision floor.");
  const selected = await ctx.files.requestFolder();
  if (!isCurrent()) return cancelled();
  if (!selected.ok || !selected.folder) return { connected: false, cancelled: false };
  const files = { async readText(folder, file) {
    if (!isCurrent()) return { ok: false };
    const result = await ctx.files.readText(folder, file);
    return isCurrent() ? result : { ok: false };
  } };
  let selectedView;
  try {
    selectedView = await loadCurrentProjection(files, { chatId, kind: match[1], folder: selected.folder.id }, minimumRevision, verifyBytes);
  } catch (error) {
    if (!isCurrent()) return cancelled();
    throw error;
  }
  if (!isCurrent()) return cancelled();
  const previous = ctx.storage.get("bindings", []);
  if (!Array.isArray(previous)) throw new Error("Invalid stored folder bindings.");
  const old = previous.find((item) => item.ownerSessionId === owner && item.chatId === chatId);
  const backupKey = "binding-rollback:v1:" + JSON.stringify([owner, chatId, old?.folder]);
  if (old && ctx.storage.get(backupKey, null) === null) {
    if (!isCurrent()) return cancelled();
    ctx.storage.set(backupKey, { v: 1, binding: { ...old } });
    if (!isCurrent()) return cancelled();
    if (JSON.stringify(ctx.storage.get(backupKey, null)) !== JSON.stringify({ v: 1, binding: old })) throw new Error("Original connection backup was not retained.");
  }
  const rows = previous.filter((item) => !(item.ownerSessionId === owner && item.chatId === chatId));
  const replacement = { ownerSessionId: owner, chatId, kind: match[1], folder: selected.folder.id, minimumRevision: selectedView.revision };
  rows.push(replacement);
  if (!isCurrent()) return cancelled();
  function restoreIfOurs() {
    if (!isCurrent()) return;
    const actual = ctx.storage.get("bindings", []);
    if (!Array.isArray(actual)) return;
    const current = actual.find((item) => item.ownerSessionId === owner && item.chatId === chatId);
    if (JSON.stringify(current) !== JSON.stringify(replacement)) return;
    const restored = actual.filter((item) => !(item.ownerSessionId === owner && item.chatId === chatId));
    if (old) restored.push(old);
    if (isCurrent()) ctx.storage.set("bindings", restored);
  }
  try {
    ctx.storage.set("bindings", rows);
    if (!isCurrent()) return cancelled();
    if (JSON.stringify(ctx.storage.get("bindings", [])) !== JSON.stringify(rows)) throw new Error("Folder binding was not retained.");
    if (!isCurrent()) return cancelled();
    const connected = install(rows) === true;
    if (!connected) restoreIfOurs();
    return { connected, cancelled: false };
  } catch (error) {
    restoreIfOurs();
    throw error;
  }
}

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/inline/hermes-theme.mjs
var HERMES_LESSON_THEME = `
.lh-native-lesson {
  --background: var(--dt-background, Canvas);
  --foreground: var(--dt-card-foreground, var(--dt-foreground, CanvasText));
  --card: var(--dt-card, Canvas);
  --muted-foreground: var(--dt-secondary-foreground, var(--dt-muted-foreground, var(--foreground)));
  --border: var(--dt-border, var(--foreground));
  --accent: var(--dt-accent, var(--card));
  --ring: var(--dt-ring, var(--foreground));
  --destructive: var(--dt-destructive, var(--foreground));
}
.lh-native-lesson textarea::placeholder, .lh-native-lesson input::placeholder {
  color: var(--muted-foreground);
  opacity: 1;
}
`;

// work/learnharness-audit/learner-focus/release-source/integrations/hermes-native-learning/src/desktop-entry.mjs
var canonical = (value) => typeof value === "string" && value && value === value.trim() && value !== "new";
var desktop_entry_default = {
  id: "learnharness-native",
  name: "LearnHarness Native",
  defaultEnabled: false,
  description: "Inline learning controls over a configured local lesson store; existing Hermes agent remains the teacher.",
  register(ctx) {
    let remove = () => {
    }, active = true;
    ctx.onDispose(() => {
      active = false;
      remove();
    });
    const style = document.createElement("style");
    style.textContent = HERMES_LESSON_THEME + '\n  /* Original QuestionDock skin: 4px rhythm, 8/12/16px radii, 16px reading size.\n     Host fonts and palette remain inherited; MCP semantic aliases are in app.mjs. */\n  .lh-native-lesson { color: var(--foreground, #e6e6e6); font-family: inherit; font-size: 1rem; line-height: 1.5; max-width: 46rem; min-width: 0; overflow-wrap: anywhere; }\n  .lh-native-lesson h3 { font-size: inherit; font-weight: 500; margin: .65rem 0; }\n  .lh-native-lesson p { white-space: pre-wrap; overflow-wrap: anywhere; }\n  .lh-native-lesson button, .lh-native-lesson textarea, .lh-native-lesson input { font: inherit; color: inherit; }\n  .lh-native-lesson button { cursor: var(--cursor-interaction, pointer); }\n  .lh-native-lesson .lh-dock { border: 1px solid var(--border, #434343); border-radius: 1rem; padding: 1rem; background: var(--card, #1c1c1c); }\n  .lh-native-lesson .lh-heading, .lh-native-lesson .lh-footer, .lh-native-lesson .lh-confidence { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; }\n  .lh-native-lesson .lh-heading, .lh-native-lesson .lh-footer { justify-content: space-between; }\n  .lh-native-lesson .lh-kind, .lh-native-lesson .lh-field-label, .lh-native-lesson .lh-secondary { color: var(--muted-foreground); }\n  .lh-native-lesson .lh-secondary { display: block; }\n  .lh-native-lesson .lh-field { display: grid; gap: .4rem; margin: .85rem 0; }\n  .lh-native-lesson .lh-field-label { font-weight: 500; }\n  .lh-native-lesson .lh-kind, .lh-native-lesson .lh-field-label { font-size: .75rem; letter-spacing: .025em; text-transform: uppercase; }\n  .lh-native-lesson textarea { box-sizing: border-box; width: 100%; resize: vertical; padding: .65rem; border: 1px solid var(--border); border-radius: .5rem; background: transparent; }\n  .lh-native-lesson .lh-option { display: block; box-sizing: border-box; width: 100%; text-align: left; padding: .75rem; margin: .35rem 0; border: 1px solid var(--border); border-radius: .5rem; background: transparent; overflow-wrap: anywhere; }\n  .lh-native-lesson .lh-option[aria-pressed="true"] { background: var(--accent, #2a2a2a); border-color: var(--foreground, #e6e6e6); }\n  .lh-native-lesson .lh-option[data-dont-know] { border-style: dashed; }\n  .lh-native-lesson .lh-confidence { margin: .9rem 0; }\n  .lh-native-lesson .lh-confidence-track { position: relative; flex: 1; min-width: 6rem; height: 2.75rem; display: flex; align-items: center; }\n  .lh-native-lesson .lh-confidence-rail { position: absolute; left: 8px; right: 8px; height: 6px; border: 1px solid var(--border, #434343); border-radius: 999px; pointer-events: none; }\n  .lh-native-lesson .lh-confidence input { appearance: none; -webkit-appearance: none; background: transparent; width: 100%; min-width: 0; height: 2.75rem; margin: 0; position: relative; cursor: pointer; }\n  .lh-native-lesson .lh-confidence input::-webkit-slider-runnable-track { background: transparent; height: 6px; }\n  .lh-native-lesson .lh-confidence input::-webkit-slider-thumb { appearance: none; -webkit-appearance: none; width: 16px; height: 16px; margin-top: -5px; border-radius: 50%; background: var(--lh-confidence-color); border: 1px solid var(--border, #434343); }\n  .lh-native-lesson .lh-confidence input::-moz-range-track { background: transparent; height: 6px; }\n  .lh-native-lesson .lh-confidence input::-moz-range-thumb { width: 16px; height: 16px; border-radius: 50%; background: var(--lh-confidence-color); border: 1px solid var(--border, #434343); }\n  .lh-native-lesson .lh-confidence-track:has(input:disabled) { opacity: .4; }\n  .lh-native-lesson .lh-confidence output { min-width: 3rem; text-align: right; font-variant-numeric: tabular-nums; }\n  .lh-native-lesson .lh-submit { background: var(--foreground); color: var(--background, var(--card)); border: 1px solid var(--foreground); border-radius: .4rem; padding: .6rem .9rem; }\n  .lh-native-lesson .lh-submit:disabled { opacity: .45; cursor: default; }\n  .lh-native-lesson .lh-close, .lh-native-lesson .lh-reveal, .lh-native-lesson .lh-resume { background: transparent; border: 0; padding: .5rem 0; }\n  .lh-native-lesson .lh-reveal { width: 100%; text-align: left; font-weight: 500; }\n  .lh-native-lesson .lh-plan { margin: .9rem 0; }\n  .lh-native-lesson [data-learning-answer-why] { margin: .75rem 0; padding: .5rem .75rem; border: 1px solid var(--border, #434343); border-radius: .5rem; }\n  .lh-native-lesson .lh-answer-record { padding: 1rem; border: 1px solid var(--border, #434343); border-radius: .75rem; margin: .75rem 0; }\n  .lh-native-lesson .lh-answer-option { border: 1px solid var(--border, #434343); border-radius: .5rem; padding: .5rem .75rem; }\n  .lh-native-lesson .lh-answer-option[data-correct="true"] { border-color: #22c55e; }\n  .lh-native-lesson .lh-answer-option[data-graded="true"][data-selected="true"][data-correct="false"] { border-color: #ef4444; }\n  .lh-native-lesson .lh-answered-confidence { display: flex; align-items: center; gap: .75rem; }\n  .lh-native-lesson .lh-static-confidence-rail { display: block; height: 6px; flex: 1; border: 1px solid var(--border, #434343); border-radius: 999px; }\n  .lh-native-lesson .lh-plan summary { cursor: var(--cursor-interaction, pointer); }\n  .lh-native-lesson .lh-plan ol { padding-left: 1.4rem; }\n  .lh-native-lesson button:focus-visible, .lh-native-lesson textarea:focus-visible, .lh-native-lesson input:focus-visible { outline: 2px solid var(--ring, #8d8d8d); outline-offset: 2px; }\n  .lh-native-lesson button { min-height: 2.75rem; }\n  .lh-native-lesson [role="alert"] { color: var(--destructive, var(--foreground)); }\n  @media (max-width: 400px) { .lh-native-lesson .lh-footer { align-items: stretch; } .lh-native-lesson .lh-submit { width: 100%; } }\n';
    document.head.append(style);
    ctx.onDispose(() => style.remove());
    function install(rows) {
      if (!active) return false;
      remove();
      if (!active) return false;
      const registration = registerHermesLearning(ctx, {
        host,
        React,
        MessageTextContent,
        bindings: rows,
        onUnbound: (props) => React.createElement(Connect, { props }),
        onReconnect: (props) => React.createElement(Connect, { props, connected: true })
      });
      if (!active) {
        registration();
        return false;
      }
      remove = registration;
      return true;
    }
    function Connect({ props, connected = false }) {
      const [status, setStatus] = React.useState(connected ? "Choose this lesson's redacted exports. The existing connection is retained until the new export validates." : "This conversation has not been connected to its redacted lesson exports.");
      const [busy, setBusy] = React.useState(false);
      const lifetime = React.useRef({ mounted: false, epoch: 0, busy: false });
      const owner = props.sessionId, chatId = props.attrs.lesson, snapshot = props.attrs.snapshot;
      const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot ?? "");
      const minimumRevision = props.minimumRevision ?? Number(match?.[2]);
      React.useEffect(() => {
        const state = lifetime.current;
        state.mounted = true;
        state.epoch++;
        state.busy = false;
        setBusy(false);
        return () => {
          state.mounted = false;
          state.epoch++;
          state.busy = false;
        };
      }, [owner, chatId, snapshot, minimumRevision]);
      async function connect() {
        const state = lifetime.current;
        if (!active || !state.mounted || state.busy || !canonical(owner) || !/^[A-Za-z0-9_-]{1,80}$/.test(chatId ?? "") || !match || !Number.isSafeInteger(minimumRevision)) return;
        state.busy = true;
        const epoch = state.epoch;
        const isCurrent = () => active && state.mounted && state.epoch === epoch;
        setBusy(true);
        try {
          const result = await connectLessonExport(ctx, { owner, chatId, snapshot, minimumRevision }, { isCurrent, verifyBytes: verifyProjectionBytes, install });
          if (isCurrent() && !result.connected && !result.cancelled) setStatus("No folder connected.");
        } catch {
          if (isCurrent()) setStatus("The export could not be connected. Check its folder, lesson and revision; no answer was sent.");
        } finally {
          if (isCurrent()) {
            state.busy = false;
            setBusy(false);
          }
        }
      }
      return React.createElement(
        "section",
        { className: "lh-native-lesson" },
        React.createElement("p", null, status),
        React.createElement(
          "button",
          { type: "button", disabled: busy || !canonical(owner) || !match || !Number.isSafeInteger(minimumRevision), onClick: connect },
          connected ? "Change lesson exports" : "Connect lesson exports"
        )
      );
    }
    install(ctx.storage.get("bindings", []));
  }
};
export {
  desktop_entry_default as default
};
