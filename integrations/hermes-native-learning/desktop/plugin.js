// SPDX-License-Identifier: AGPL-3.0-only; LearnHarness native integration. See NOTICE.md.

// src/desktop-entry.mjs
import { host, MessageTextContent } from "@hermes/plugin-sdk";
import * as React from "react";

// src/vendor/runtime/question-pure.ts
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

// src/inline/practice-client.mjs
function mountPractice(root, initialView, options = {}) {
  const doc = root.ownerDocument, win = doc.defaultView;
  let view = initialView, text = "", open = true, pending = false;
  const key = () => `${view.chatId}:practice:${view.activeProblem?.toolCallId ?? "between"}`;
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
  const status = (message, error = false) => {
    const e = root.querySelector("[data-status]");
    if (e) {
      e.textContent = message;
      e.setAttribute("role", error ? "alert" : "status");
    }
  };
  function save() {
    try {
      options.drafts?.write(key(), { key: key(), text, open });
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
      const result = await options.send({ type, chatId: view.chatId, ...input ? { input } : {} });
      if (result?.delivered === true) {
        status("Delivered to the owning agent. Waiting for the saved practice response.");
        return;
      }
      if (!result?.view || !(result.persisted || result.loaded)) throw new Error("No saved practice response received.");
      const oldKey = key(), same = result.view.activeProblem?.toolCallId === view.activeProblem?.toolCallId;
      view = result.view;
      pending = false;
      if (input?.type === "thinking" || !same) {
        try {
          options.drafts?.remove(oldKey);
        } catch {
        }
        text = "";
        open = true;
      }
      if (!same) restore();
      render();
      status(result.loaded ? "Saved practice reopened." : input?.type === "next" ? "Next problem requested." : "Thinking saved.");
    } catch (error) {
      pending = false;
      render();
      status(error.message, true);
    }
  }
  function render() {
    root.replaceChildren();
    options.onPresentation?.({ open });
    const active = view.activeProblem;
    if (view.conclusion && !options.richProse) {
      root.append(node("h3", "Problem review"), node("p", view.conclusion.statement));
      for (const thought of view.conclusion.thinking ?? []) root.append(node("p", `Your thinking: ${thought}`));
      root.append(node("p", view.conclusion.verdict), node("h3", "Committed solution"), node("p", view.conclusion.modelSolution));
    }
    if (view.conclusion && options.richProse) for (const thought of view.conclusion.thinking ?? []) root.append(node("p", `Your thinking: ${thought}`));
    if (!options.richProse) for (const entry of view.discussion ?? []) root.append(node("p", entry.role === "user" ? `Your question: ${entry.text}` : entry.text));
    if (active) {
      const dock = node("section", null, { class: "lh-dock" });
      root.append(dock);
      if (!open) dock.append(button("Practice problem \xB7 Reopen", () => {
        open = true;
        save();
        render();
      }, { class: "lh-reveal" }));
      else {
        const heading = node("div", null, { class: "lh-heading" });
        heading.append(node("span", "Practice problem"), button("Close", () => {
          open = false;
          save();
          render();
        }, { class: "lh-close" }));
        dock.append(heading);
        if (!options.richProse) dock.append(node("h3", active.statement));
        for (const thought of view.thinking) dock.append(node("p", `Your thinking: ${thought}`));
        if (!options.richProse) for (const entry of view.feedback ?? []) dock.append(node("p", entry.text, { "data-practice-feedback": entry.id }));
        const label = node("label", null, { class: "lh-field" });
        label.append(node("span", "Your thinking", { class: "lh-field-label" }));
        const field = node("textarea", null, { rows: 4, "data-practice-thinking": "", maxlength: 16e3, placeholder: "Work here, think out loud." });
        field.value = text;
        field.addEventListener("input", () => {
          text = field.value;
          save();
          const submit2 = root.querySelector("[data-practice-send]");
          if (submit2) submit2.disabled = pending || !text.trim();
        });
        field.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && (!event.shiftKey || event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            if (text.trim()) void send("practice-input", { type: "thinking", problemCallId: active.toolCallId, text });
          }
        });
        label.append(field);
        dock.append(label, node("span", "Enter sends \xB7 Shift+Enter newline", { class: "lh-secondary" }));
        const submit = button("Submit thinking", () => void send("practice-input", { type: "thinking", problemCallId: active.toolCallId, text }), { class: "lh-submit", "data-practice-send": "" });
        submit.disabled = pending || !text.trim();
        dock.append(submit);
      }
    } else if (view.conclusion) {
      const next = button("Next problem", () => void send("practice-input", { type: "next" }), { class: "lh-submit" });
      next.disabled = pending || view.nextAllowed;
      root.append(next);
      if (view.nextAllowed) root.append(node("p", "Next problem requested."));
    } else root.append(node("p", "No practice problem has been posed."));
    root.append(node("p", pending ? "Saving\u2026" : "", { "data-status": "", "aria-live": "polite", role: "status" }), button("Resume saved lesson", () => void send("resume"), { class: "lh-resume" }));
  }
  render();
  return { destroy() {
  }, readDraft: () => ({ text, open, pending }) };
}

// src/inline/inline-client.mjs
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
  let view = initialView;
  let state = {
    selection: emptyDockSelection(),
    text: "",
    other: "",
    thinking: "",
    readingThinking: "",
    confidenceIndex: DEFAULT_CONFIDENCE_INDEX,
    open: view.question?.open ?? true,
    pending: false
  };
  const draftKey = () => `${view.chatId}:${view.question?.toolCallId ?? "idle"}`;
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
      pending: state.pending
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
      pending: false
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
    return q && !state.pending && (q.mode === "text" ? state.text.trim().length > 0 : state.selection.dontKnow || state.selection.selected.size > 0 || state.selection.otherSelected && state.other.trim().length > 0);
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
        detail.append(node("summary", proposition.name), node("p", proposition.statement));
        for (const passage of proposition.passages ?? []) detail.append(node("blockquote", passage));
        knowledge.append(detail);
      }
      root.append(knowledge);
    }
  }
  function updateSubmit() {
    const b = root.querySelector("[data-submit]");
    if (b) b.disabled = !canSubmit();
  }
  function answerRequest() {
    const q = view.question;
    const request = {};
    if (q.mode === "text") request.text = state.text;
    else {
      request.dontKnow = state.selection.dontKnow;
      request.values = [...state.selection.selected].map((i) => q.options[i].value);
      if (state.selection.otherSelected) request.other = state.other;
      if (state.thinking.trim()) request.thinking = state.thinking;
      if (q.kind === "quiz" && !state.selection.dontKnow) request.confidence = CONFIDENCE_STOPS[state.confidenceIndex];
    }
    if (state.readingThinking.trim()) request.readingThinking = state.readingThinking;
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
      setStatus(ack?.delivered ? "Delivered to the host. Waiting for the saved lesson response." : "Host action requested. Waiting for the saved lesson response.");
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
    root.replaceChildren();
    renderLessonPanels();
    options.onPresentation?.({ open: state.open });
    const q = view.question;
    if (!q) {
      const last = view.answers.at(-1);
      if (last) {
        if (!options.richProse) root.append(node("h3", last.questionText));
        root.append(node("p", last.text ?? (last.dontKnow ? "I don\u2019t know" : last.answers.map((a) => a.label).join(", "))));
        if (last.thinking) root.append(node("p", `Your thinking: ${last.thinking}`));
        if (last.readingThinking) root.append(node("p", `Thinking while reading: ${last.readingThinking}`));
        if (last.correct !== void 0) root.append(node("p", last.correct ? "Correct" : "Review this step"));
        if (last.committed && !options.richProse) root.append(node("p", last.committed));
        if (last.explanation && !options.richProse) root.append(node("p", last.explanation));
      }
      renderPlan();
    } else {
      if (view.teachingText && !options.richProse) root.append(node("p", view.teachingText, { class: "lh-teaching" }));
      if (q.needsReveal) root.append(field("Thinking while reading", "readingThinking", "Whatever comes to mind as you read."));
      const dock = node("section", null, { class: "lh-dock" });
      root.append(dock);
      if (!state.open) {
        dock.append(button(q.needsReveal ? "Check your understanding \xB7 Open" : `${q.questionType === "predict" ? "Prediction" : "Question"} \xB7 Reopen`, () => {
          state.open = true;
          save();
          render();
        }, { class: "lh-reveal", "data-reveal": "" }));
      } else {
        const heading = node("div", null, { class: "lh-heading" });
        const label = q.questionType === "predict" ? "Prediction" : q.tool === "probe" ? "Probe" : q.tool === "recall" ? "Recall" : q.kind === "ask" ? "Question" : "Check";
        heading.append(node("span", label, { class: "lh-kind" }), button("Close", () => {
          state.open = false;
          save();
          render();
        }, { class: "lh-close", "data-close": "" }));
        dock.append(heading);
        if (!options.richProse) dock.append(node("h3", q.question));
        if (q.context && !options.richProse) dock.append(node("p", q.context));
        if (q.mode !== "text") {
          const group = node("div", null, { role: "group", "aria-label": q.mode === "multi-select" ? "Choose all that apply" : "Choose an answer" });
          q.options.forEach((option, index) => {
            const row = button(
              `${index + 1}. ${option.label}`,
              () => {
                state.selection = toggleOption(q.mode, state.selection, index);
                save();
                render();
              },
              { class: "lh-option", "aria-pressed": state.selection.selected.has(index), "data-option": option.value }
            );
            if (option.description) row.append(node("span", option.description, { class: "lh-secondary" }));
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
          group.append(button(
            "I don\u2019t know",
            () => {
              state.selection = { selected: /* @__PURE__ */ new Set(), otherSelected: false, dontKnow: !state.selection.dontKnow };
              save();
              render();
            },
            { class: "lh-option", "aria-pressed": state.selection.dontKnow, "data-dont-know": "" }
          ));
          dock.append(group);
          if (q.kind === "quiz") {
            const confidence = node("label", null, { class: "lh-confidence" });
            const slider = node("input", null, {
              type: "range",
              min: 0,
              max: CONFIDENCE_STOPS.length - 1,
              step: 1,
              "aria-label": "Confidence \u2014 the probability your selected answer is correct",
              "data-confidence": ""
            });
            slider.value = state.confidenceIndex;
            slider.disabled = state.selection.dontKnow;
            const value = node("output", state.selection.dontKnow ? "\u2014" : `${CONFIDENCE_STOPS[state.confidenceIndex]}%`);
            slider.addEventListener("input", () => {
              state.confidenceIndex = Number(slider.value);
              value.textContent = `${CONFIDENCE_STOPS[state.confidenceIndex]}%`;
              save();
            });
            confidence.append(node("span", "Confidence"), slider, value);
            dock.append(confidence);
          }
        }
        dock.append(q.mode === "text" ? field("Your answer", "text", "Type your answer.") : field("Your thinking", "thinking", "Why this answer? Whatever comes to mind."));
        const footer = node("div", null, { class: "lh-footer" });
        footer.append(node("span", "Enter submits \xB7 Shift+Enter newline", { class: "lh-secondary" }), button("Submit answer", () => void submit(), { class: "lh-submit", "data-submit": "" }));
        dock.append(footer);
      }
      renderPlan();
    }
    root.append(node("p", state.pending ? "Waiting for the saved lesson response." : "", { "data-status": "", "aria-live": "polite", role: "status" }));
    root.append(button("Resume saved lesson", () => {
      state.pending = true;
      save();
      void deliver({ type: "resume", chatId: view.chatId });
    }, { class: "lh-resume", "data-resume": "" }));
    updateSubmit();
  }
  function applyView(next) {
    if (next.chatId !== view.chatId) throw new Error("The saved response belongs to a different lesson.");
    const same = next.question?.toolCallId === view.question?.toolCallId;
    const previousKey = draftKey();
    view = next;
    if (!same) state = { selection: emptyDockSelection(), text: "", other: "", thinking: "", readingThinking: "", confidenceIndex: DEFAULT_CONFIDENCE_INDEX, open: next.question?.open ?? true, pending: false };
    else state.pending = false;
    if (!same && options.drafts) {
      try {
        options.drafts.remove(previousKey);
      } catch {
      }
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
    readDraft: () => ({ ...state, selection: { ...state.selection, selected: new Set(state.selection.selected) } }),
    destroy: () => win.removeEventListener("openai:set_globals", onGlobals)
  };
}

// src/inline/hermes-native-port.mjs
var bytes = (value) => new TextEncoder().encode(JSON.stringify(value)).length;
function requirePort(ok, message) {
  if (!ok) throw new Error(message);
}
function createHermesLessonPort(ownerSessionId, view, { composer, storage }) {
  requirePort(typeof ownerSessionId === "string" && ownerSessionId.length > 0 && ownerSessionId.length <= 300 && ownerSessionId === ownerSessionId.trim() && ownerSessionId !== "new", "An exact owning Hermes session is required.");
  requirePort(typeof view.chatId === "string" && view.chatId.length > 0 && view.chatId.length <= 100 && Number.isSafeInteger(view.revision) && view.revision >= 0, "Invalid bound lesson view.");
  requirePort(typeof composer?.submit === "function" && ["get", "set", "remove"].every((k) => typeof storage?.[k] === "function"), "Supported Hermes composer/storage ports are unavailable.");
  const kind = view.kind === "practice" ? "practice" : "teach";
  const key = kind === "practice" ? `${view.chatId}:practice:${view.activeProblem?.toolCallId ?? "between"}` : `${view.chatId}:${view.question?.toolCallId ?? "idle"}`;
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
      if (kind === "practice" && submitted && submitted.draftId === saved.draftId && submitted.text === saved.payload?.text && Array.isArray(submitted.baselineIds) && view.thinkingEntries?.some((entry) => !submitted.baselineIds.includes(entry.id) && entry.text === submitted.text)) {
        storage.remove(slot);
        return null;
      }
      return saved.payload;
    },
    write(requested, payload) {
      checkKey(requested);
      const previous = storage.get(slot, null);
      requirePort(!previous || previous.baseRevision <= view.revision, "A newer card owns this draft; keep this card open.");
      const sameDraft = previous?.key === key && (kind === "practice" ? previous.payload?.text === payload?.text : JSON.stringify(previous.payload) === JSON.stringify(payload));
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
      if (saved?.draftId && Number.isSafeInteger(saved.baseRevision) && saved.payload?.text === action.input.text && Array.isArray(view.thinkingEntries)) {
        submission = {
          before: JSON.stringify(saved),
          draftId: saved.draftId,
          text: action.input.text,
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

// src/inline/lesson-prose.mjs
function richTextAllowed(text) {
  if (typeof text !== "string" || text.length > 65536) return false;
  const ordinary = /* @__PURE__ */ new Set(["", "mermaid", "text", "txt", "plaintext", "python", "py", "javascript", "js", "typescript", "ts", "json", "css", "bash", "sh", "shell", "powershell", "ps1", "sql", "java", "c", "cpp", "c++", "csharp", "c#", "go", "rust", "ruby", "rb", "r", "matlab", "latex", "tex"]);
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
      add("revealed-explanation", answer.explanation);
    }
  }
  const diagram = planDiagram(view.plan);
  if (diagram) add("plan", diagram);
  const knowledge = view.knowledge?.nodes?.length ? planDiagram(view.knowledge.diagram) : null;
  if (knowledge) add("knowledge-map", "### Propositions from this lesson\n\n" + knowledge);
  return result;
}
function renderLessonProse(React2, MessageTextContent2, view, state) {
  return React2.createElement(
    "div",
    { "data-learning-prose": "", className: "lh-native-prose" },
    ...lessonProse(view, state).map((entry) => React2.createElement(
      "section",
      { key: entry.id, "data-learning-prose-part": entry.id },
      richTextAllowed(entry.text) ? React2.createElement(MessageTextContent2, {
        text: entry.text,
        media: false,
        // Core paragraphPlainText accepts only string children. Wrapping
        // every paragraph prevents nested transcript directives in prose.
        decorateText: (children) => React2.createElement("span", null, children)
      }) : React2.createElement("pre", { style: { whiteSpace: "pre-wrap" } }, entry.text)
    ))
  );
}

// src/vendor/runtime/demo-pure.ts
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

// src/inline/artifacts.mjs
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
      bridge.error ? h("div", null, h("pre", null, bridge.error), h("button", { type: "button", onClick: report }, "Send error to teacher")) : null
    );
  }
  return function JobArtifacts({ ctx, binding, view, port }) {
    const rows = view.jobs?.jobs ?? [];
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

// src/inline/hermes-contribution.mjs
async function verifyProjectionBytes(snapshot, text) {
  const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot);
  if (!match || !globalThis.crypto?.subtle) throw new Error("Snapshot content verification is unavailable.");
  const bytes2 = new TextEncoder().encode(text);
  const sum = new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", bytes2));
  const actual = Array.from(sum, (byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actual !== match[3]) throw new Error("Snapshot bytes differ from their projection identity.");
}
function registerHermesLearning(ctx, { host: host2, React: React2, MessageTextContent: MessageTextContent2, bindings, onUnbound }) {
  const JobArtifacts = createJobArtifacts(React2);
  const owned = bindings.map((binding) => Object.freeze({ ...binding }));
  if (owned.some((b) => typeof b.ownerSessionId !== "string" || !b.ownerSessionId || b.ownerSessionId !== b.ownerSessionId.trim() || b.ownerSessionId === "new" || !["teach", "practice"].includes(b.kind) || !b.chatId || !b.folder)) throw new Error("Explicit owner/lesson/export-folder bindings required.");
  function LessonLeaf({ binding, snapshot, revision }) {
    const ref = React2.useRef(null);
    const [view, setView] = React2.useState(null);
    const [presentation, setPresentation] = React2.useState({ open: true });
    const rich = typeof MessageTextContent2 === "function";
    React2.useEffect(() => {
      let disposed = false, controller;
      const root = ref.current;
      setView(null);
      root.textContent = "Loading saved lesson.";
      (async () => {
        const result = await ctx.files.readText(binding.folder, snapshot);
        if (disposed) return;
        if (!result.ok || typeof result.text !== "string" || result.size > 262144 || new TextEncoder().encode(result.text).length > 262144)
          throw new Error("The approved redacted lesson export is unavailable.");
        await verifyProjectionBytes(snapshot, result.text);
        if (disposed) return;
        const view2 = JSON.parse(result.text);
        if (view2.chatId !== binding.chatId || (view2.kind === "practice" ? "practice" : "teach") !== binding.kind || view2.revision !== revision)
          throw new Error("Snapshot owner/lesson/revision differs; ask the owner to return a fresh card.");
        if (view2.question && ["committedAnswer", "correctIndices", "explanation"].some((k) => k in view2.question))
          throw new Error("An active question export exposed its commitment.");
        if (view2.activeProblem && Object.keys(view2.activeProblem).some((k) => !["toolCallId", "statement"].includes(k)))
          throw new Error("An active problem export contains teacher-only fields.");
        setPresentation({ open: view2.question?.open ?? true });
        setView(view2);
        const ports = createHermesLessonPort(binding.ownerSessionId, view2, { composer: host2.composer, storage: ctx.storage });
        controller = mountInline(root, view2, {
          ...ports,
          richProse: rich,
          onPresentation: (next) => {
            if (!disposed) setPresentation((old) => old.open === next.open ? old : next);
          }
        });
      })().catch((error) => {
        if (!disposed) root.textContent = error.message;
      });
      return () => {
        disposed = true;
        controller?.destroy();
      };
    }, [binding, snapshot, revision, rich]);
    return React2.createElement(
      "section",
      { className: "lh-native-lesson" },
      rich && view ? renderLessonProse(React2, MessageTextContent2, view, presentation) : null,
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
      return React2.createElement(LessonLeaf, { binding, snapshot: props.attrs.snapshot, revision: Number(match[2]) });
    }
  } });
}

// src/connect-export.mjs
async function connectLessonExport(ctx, { owner, chatId, snapshot }, { isCurrent, verifyBytes, install }) {
  const cancelled = () => ({ connected: false, cancelled: true });
  if (!isCurrent()) return cancelled();
  const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot ?? "");
  if (typeof owner !== "string" || !owner || owner !== owner.trim() || owner === "new" || !/^[A-Za-z0-9_-]{1,80}$/.test(chatId ?? "") || !match) throw new Error("Invalid explicit lesson identity.");
  const selected = await ctx.files.requestFolder();
  if (!isCurrent()) return cancelled();
  if (!selected.ok || !selected.folder) return { connected: false, cancelled: false };
  const file = await ctx.files.readText(selected.folder.id, snapshot);
  if (!isCurrent()) return cancelled();
  if (!file.ok || typeof file.text !== "string" || new TextEncoder().encode(file.text).length > 262144)
    throw new Error("Select this lesson's redacted exports.");
  await verifyBytes(snapshot, file.text);
  if (!isCurrent()) return cancelled();
  const view = JSON.parse(file.text);
  if (view.chatId !== chatId || (view.kind === "practice" ? "practice" : "teach") !== match[1] || view.revision !== Number(match[2]))
    throw new Error("Snapshot lesson or revision differs.");
  if (!isCurrent()) return cancelled();
  const previous = ctx.storage.get("bindings", []);
  if (!Array.isArray(previous)) throw new Error("Invalid stored folder bindings.");
  const rows = previous.filter((item) => !(item.ownerSessionId === owner && item.chatId === chatId));
  rows.push({ ownerSessionId: owner, chatId, kind: match[1], folder: selected.folder.id });
  if (!isCurrent()) return cancelled();
  ctx.storage.set("bindings", rows);
  if (!isCurrent()) return cancelled();
  if (JSON.stringify(ctx.storage.get("bindings", [])) !== JSON.stringify(rows)) throw new Error("Folder binding was not retained.");
  if (!isCurrent()) return cancelled();
  return { connected: install(rows) === true, cancelled: false };
}

// src/desktop-entry.mjs
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
    style.textContent = '\n  .lh-native-lesson { color: var(--foreground); font-family: inherit; max-width: 46rem; }\n  .lh-native-lesson h3 { font-size: inherit; font-weight: 500; margin: .65rem 0; }\n  .lh-native-lesson p { white-space: pre-wrap; overflow-wrap: anywhere; }\n  .lh-native-lesson button, .lh-native-lesson textarea, .lh-native-lesson input { font: inherit; color: inherit; }\n  .lh-native-lesson button { cursor: var(--cursor-interaction, pointer); }\n  .lh-native-lesson .lh-dock { border: 1px solid var(--border); border-radius: .8rem; padding: .85rem; background: var(--card); }\n  .lh-native-lesson .lh-heading, .lh-native-lesson .lh-footer, .lh-native-lesson .lh-confidence { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; }\n  .lh-native-lesson .lh-heading, .lh-native-lesson .lh-footer { justify-content: space-between; }\n  .lh-native-lesson .lh-kind, .lh-native-lesson .lh-field-label, .lh-native-lesson .lh-secondary { color: var(--muted-foreground); }\n  .lh-native-lesson .lh-secondary { display: block; }\n  .lh-native-lesson .lh-field { display: grid; gap: .4rem; margin: .85rem 0; }\n  .lh-native-lesson .lh-field-label { font-weight: 500; }\n  .lh-native-lesson textarea { box-sizing: border-box; width: 100%; resize: vertical; padding: .65rem; border: 1px solid var(--border); border-radius: .5rem; background: transparent; }\n  .lh-native-lesson .lh-option { display: block; box-sizing: border-box; width: 100%; text-align: left; padding: .75rem; margin: .35rem 0; border: 1px solid var(--border); border-radius: .5rem; background: transparent; overflow-wrap: anywhere; }\n  .lh-native-lesson .lh-option[aria-pressed="true"] { background: color-mix(in srgb, var(--accent) 14%, transparent); border-color: var(--accent); }\n  .lh-native-lesson .lh-confidence { margin: .9rem 0; }\n  .lh-native-lesson .lh-confidence input { flex: 1; min-width: 8rem; accent-color: var(--accent); }\n  .lh-native-lesson .lh-submit { background: var(--foreground); color: var(--background, var(--card)); border: 1px solid var(--foreground); border-radius: .4rem; padding: .6rem .9rem; }\n  .lh-native-lesson .lh-submit:disabled { opacity: .45; cursor: default; }\n  .lh-native-lesson .lh-close, .lh-native-lesson .lh-reveal, .lh-native-lesson .lh-resume { background: transparent; border: 0; padding: .5rem 0; }\n  .lh-native-lesson .lh-reveal { width: 100%; text-align: left; font-weight: 500; }\n  .lh-native-lesson .lh-plan { margin: .9rem 0; }\n  .lh-native-lesson .lh-plan summary { cursor: var(--cursor-interaction, pointer); }\n  .lh-native-lesson .lh-plan ol { padding-left: 1.4rem; }\n  .lh-native-lesson [role="alert"] { color: var(--destructive, var(--foreground)); }\n  @media (max-width: 400px) { .lh-native-lesson .lh-footer { align-items: stretch; } .lh-native-lesson .lh-submit { width: 100%; } }\n';
    document.head.append(style);
    ctx.onDispose(() => style.remove());
    function install(rows) {
      if (!active) return false;
      remove();
      if (!active) return false;
      const registration = registerHermesLearning(ctx, { host, React, MessageTextContent, bindings: rows, onUnbound: (props) => React.createElement(Connect, { props }) });
      if (!active) {
        registration();
        return false;
      }
      remove = registration;
      return true;
    }
    function Connect({ props }) {
      const [status, setStatus] = React.useState("This conversation has not been connected to its redacted lesson exports.");
      const [busy, setBusy] = React.useState(false);
      const lifetime = React.useRef({ mounted: false, epoch: 0, busy: false });
      const owner = props.sessionId, chatId = props.attrs.lesson, snapshot = props.attrs.snapshot;
      const match = /^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot ?? "");
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
      }, [owner, chatId, snapshot]);
      async function connect() {
        const state = lifetime.current;
        if (!active || !state.mounted || state.busy || !canonical(owner) || !/^[A-Za-z0-9_-]{1,80}$/.test(chatId ?? "") || !match) return;
        state.busy = true;
        const epoch = state.epoch;
        const isCurrent = () => active && state.mounted && state.epoch === epoch;
        setBusy(true);
        try {
          const result = await connectLessonExport(ctx, { owner, chatId, snapshot }, { isCurrent, verifyBytes: verifyProjectionBytes, install });
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
        React.createElement("button", { type: "button", disabled: busy || !canonical(owner) || !match, onClick: connect }, "Connect lesson exports")
      );
    }
    install(ctx.storage.get("bindings", []));
  }
};
export {
  desktop_entry_default as default
};
