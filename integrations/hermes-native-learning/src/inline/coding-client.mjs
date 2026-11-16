// SPDX-License-Identifier: AGPL-3.0-only
// Native editor projection. Source and observations are always inert DOM text.
const LIMIT = 8192;
const encoder = new TextEncoder();
const palette = {
  comment: 'color: var(--muted-foreground, #7a8494)',
  string: 'color: light-dark(#075f48, #9de2bc)',
  number: 'color: light-dark(#814512, #ffc684)',
  keyword: 'color: light-dark(#6935a3, #d3aaff)',
};
const tokenPattern = /(\/\/[^\n]*|\/\*[\s\S]*?(?:\*\/|$))|(["'`])(?:\\[\s\S]|(?!\2)[^\\])*?(?:\2|$)|\b(\d+(?:[._]\d+)*)\b|\b(async|await|break|case|class|const|continue|default|delete|do|else|export|false|for|function|if|import|in|instanceof|let|new|null|of|return|static|super|switch|this|throw|true|try|typeof|undefined|var|void|while|yield)\b/g;
const css = `
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
    const token = doc.createElement('span');
    token.setAttribute('style', palette[match[1] ? 'comment' : match[2] ? 'string' : match[3] ? 'number' : 'keyword']);
    token.textContent = match[0];
    fragment.append(token);
    position = match.index + match[0].length;
  }
  fragment.append(source.slice(position));
  if (source.endsWith('\n')) fragment.append(' ');
  target.replaceChildren(fragment);
}

/** Pass the server-bound current prompt callback as onRun(code). */
export function mountCodingEditor(root, {spec, value, onChange, onRun, onReceipt, observations, disabled = false}) {
  const doc = root.ownerDocument;
  const node = (tag, attributes = {}, text) => {
    const element = doc.createElement(tag);
    for (const [name, val] of Object.entries(attributes)) element.setAttribute(name, val);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const panel = node('div', {class: 'lh-code-editor'});
  const label = node('label', {class: 'lh-field'});
  const surface = node('div', {class: 'lh-code-surface'});
  const colors = node('pre', {class: 'lh-code-colors', 'aria-hidden': 'true'});
  const editor = node('textarea', {rows: '7', wrap: 'off', maxlength: String(LIMIT), spellcheck: 'false',
    autocapitalize: 'off', autocomplete: 'off', 'data-code-source': ''});
  const run = node('button', {'data-code-run': '', type: 'button'}, 'Run tests');
  const output = node('ul', {'data-code-observations': '', 'aria-label': 'Test observations'});
  const status = node('span', {'data-code-status': '', role: 'status', 'aria-live': 'polite'});
  const tests = Array.isArray(spec?.testNames) && spec.testNames.length > 0;
  let running = false;
  editor.value = typeof value === 'string' ? value : spec?.starterCode ?? '';
  editor.disabled = disabled;
  const valid = () => editor.value.trim().length > 0 && encoder.encode(editor.value).length <= LIMIT;

  function setStatus(message, error = false) {
    status.setAttribute('role', error ? 'alert' : 'status');
    status.textContent = message;
  }
  function sync() {
    colors.scrollTop = editor.scrollTop;
    colors.scrollLeft = editor.scrollLeft;
  }
  function show(results) {
    const statusNames = {pass: 'Passed', fail: 'Failed', timeout: 'Timed out', error: 'Error'};
    output.replaceChildren(...(Array.isArray(results) ? results : []).map(result => node('li', {},
      result.name + ' — ' + (statusNames[result.status] ?? 'Unknown') +
      (result.message ? '. ' + result.message : result.actual !== undefined ? '. Returned ' + result.actual : ''))));
  }
  function updateButton() {
    run.disabled = disabled || running || !valid();
  }
  function render() {
    paintSource(doc, colors, editor.value);
    sync();
    updateButton();
  }
  editor.addEventListener('scroll', sync);
  editor.addEventListener('input', () => {
    onReceipt?.(undefined);
    show([]);
    setStatus(encoder.encode(editor.value).length > LIMIT ? 'Use at most 8 KiB of code.' : '');
    onChange?.(editor.value);
    render();
  });
  run.addEventListener('click', async () => {
    if (disabled || running || !valid() || typeof onRun !== 'function') return;
    const source = editor.value;
    running = true;
    updateButton();
    onReceipt?.(undefined);
    show([]);
    setStatus('Running tests…');
    try {
      const receipt = await onRun(source);
      if (!panel.isConnected || editor.value !== source) return;
      if (typeof receipt?.runId !== 'string' || !Array.isArray(receipt.observations))
        throw new Error('No test observations returned. Run tests again.');
      show(receipt.observations);
      setStatus('Tests finished.');
      onReceipt?.(receipt);
    } catch (error) {
      if (panel.isConnected && editor.value === source) setStatus(error?.message ?? 'Unable to run tests.', true);
    } finally {
      running = false;
      if (panel.isConnected && editor.value !== source) setStatus('');
      updateButton();
    }
  });
  label.append(node('span', {class: 'lh-field-label'}, 'JavaScript code'), surface);
  surface.append(colors, editor);
  panel.append(node('style', {}, css), label);
  if (tests && typeof onRun === 'function') panel.append(run);
  if (tests && typeof onRun !== 'function') panel.append(node('span', {class: 'lh-secondary'}, 'Open the connected lesson to run tests.'));
  panel.append(status, output);
  root.append(panel);
  show(observations);
  render();
  return panel;
}
