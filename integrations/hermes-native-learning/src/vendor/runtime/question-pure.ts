// SPDX-License-Identifier: AGPL-3.0-only
// LearnHarness v0.3.4, Amos Blomqvist. See NOTICE.md and provenance.json.
import { stripModelValueDebris } from "./value-debris.ts";
export interface QuizOption {
	label: string;
	value: string;
	description?: string;
}

export function parseOptionsIfString<T>(options: string | T[] | undefined): unknown {
	if (typeof options !== "string") return options;
	try {
		const parsed: unknown = JSON.parse(options);
		if (Array.isArray(parsed)) return parsed;
	} catch {
		/* not JSON — fall through untouched */
	}
	return options;
}

// ─── cross-field authoring validation (tool-schema refinements) ──────────
// Enforced at the tool-call boundary (see the superRefines below): an invalid
// question NEVER reaches the learner — the SDK returns the validation error
// to the teacher as a tool result and the teacher retries. The rules mirror
// the grading path exactly (normalizeOptions / coerceCorrectAnswer /
// resolveCorrect), so schema-valid ⇔ gradeable.

/** Option sanity shared by quiz + ask: labels non-empty, resolved values
 *  (trimmed `value`, falling back to the trimmed label — exactly how
 *  normalizeOptions keys them) distinct. Returns the problems plus the
 *  resolved keys for the correctAnswer check. */
function optionProblems(
	options: Array<{ label: string; value?: string }>,
): { problems: string[]; keys: string[] } {
	const problems: string[] = [];
	const keys: string[] = [];
	options.forEach((option, i) => {
		const label = option.label.trim();
		if (label.length === 0) {
			problems.push(`options[${i}].label is empty — every option needs a label.`);
			return;
		}
		const key = option.value?.trim() || label;
		if (keys.includes(key)) {
			problems.push(`Two options resolve to the same value "${key}" — options must be distinct.`);
		}
		keys.push(key);
	});
	return { problems, keys };
}

/** ask options: the shared sanity, nothing more (ask is not graded). */
export function askOptionProblems(options: Array<{ label: string; value?: string }>): string[] {
	return optionProblems(options).problems;
}

/** The full quiz authoring contract: option sanity + correctAnswer must be
 *  gradeable. Empty result = a quiz the dock can arm and grade faithfully. */
export function quizInputProblems(input: {
	options: Array<{ label: string; value?: string }>;
	correctAnswer: string | string[];
	multiSelect?: boolean;
}): string[] {
	const { problems, keys } = optionProblems(input.options);

	// Preserve exact option keys before trying copy-syntax cleanup — the
	// same option-aware coercion runs at the display and grading seams.
	const entries = coerceCorrectAnswer(input.correctAnswer, keys);
	const unique = [...new Set(entries)];
	if (unique.length === 0 || unique.some((v) => v.length === 0)) {
		problems.push("correctAnswer is required — provide the value (or label) of the correct option(s).");
		return problems;
	}
	for (const v of unique) {
		if (!keys.includes(v)) {
			problems.push(
				`correctAnswer "${v}" does not match any option value. Valid values: ${keys.map((k) => `"${k}"`).join(", ")}. ` +
					"Copy the exact value (or label) of the intended option — never a paraphrase or slug.",
			);
		}
	}
	if (unique.length > 1 && input.multiSelect !== true) {
		problems.push(
				`correctAnswer lists ${unique.length} values but multiSelect is not true — a single-select question with several ` +
					"correct answers can never be answered correctly. Set multiSelect: true, or make exactly one option correct.",
		);
	}
	return problems;
}

export const QUIZ_QUESTION_TYPES = ["predict", "check"] as const;
export type QuizQuestionType = (typeof QUIZ_QUESTION_TYPES)[number];

/** Normalize a persisted quiz `type` (display seam): old records carry
 *  none, and unhealable wobble degrades to undefined — callers render
 *  "Quiz" and the check-style card. The debris strip (whitehead,
 *  2026-10-09) heals the recorded `"\"predict\""` wobble — a raw
 *  persisted record displays its intended role. */
export function normalizeQuizType(raw: unknown): QuizQuestionType | undefined {
	if (typeof raw !== "string") return undefined;
	const v = stripModelValueDebris(raw);
	return v === "predict" ? "predict" : v === "check" ? "check" : undefined;
}

/** The reveal law as a pure predicate (owner 2026-10-03; explain joined
 *  2026-10-09): a teach-phase CHECK collapses behind the "Check your
 *  understanding" reveal — a prediction NEVER does (it precedes the
 *  teaching and gates it; collapsing it would invert the cycle), and
 *  neither do probe/plan questions or ask. Both teach quizzing tools
 *  (quiz and explain) obey the same law. chat.tsx calls this for its
 *  pending question; the reading-thinking field mounts on the same
 *  truth. Records that predate the `type` field carry none — they render
 *  as checks, the standing default. */
export function questionNeedsReveal(tool: string, rawInput: unknown, phase: string): boolean {
	if ((tool !== "quiz" && tool !== "explain") || phase !== "teach") return false;
	return normalizeQuizType((rawInput as { type?: unknown } | null)?.type) !== "predict";
}

export function explainInputProblems(input: { correctAnswer: string }): string[] {
	if (input.correctAnswer.trim().length === 0) {
		return ["correctAnswer is required — commit to the full correct answer BEFORE posing the question."];
	}
	return [];
}

/** A real selected answer, in the order the options were displayed. */
export interface OptionAnswer {
	label: string;
	value: string;
	index: number; // 1-based display index
}

export type QuestionKind = "quiz" | "ask" | "explain";
export type SelectMode = "single-select" | "multi-select";
export type QuestionMode = SelectMode | "text";

/** Full question data — stored in the `lh_question` custom entry. */
export interface QuestionData {
	id: string;
	kind: QuestionKind;
	/** quiz only (teach phase, owner 2026-10-03): the question's role in
	 *  the cycle — predict (before the teaching, never collapsed) or check
	 *  (after it, behind the reveal). Absent on probe quizzes and old
	 *  records — everything check-shaped. */
	questionType?: QuizQuestionType;
	question: string;
	context?: string;
	mode: QuestionMode;
	options: QuizOption[]; // display order (post-shuffle)
	// quiz only. NEVER send to the client before answering:
	correctIndices?: number[];
	// explain only. NEVER send to the client before answering:
	committedAnswer?: string;
	// quiz only (the MC "why"). NEVER send to the client before answering:
	explanation?: string;
	createdAt: string;
}

/** The learner's answer — full structured record, stored in `lh_question_answered`.
 *  NO questionId (owner, tool-result diet 2026-10-02): it was the
 *  toolCallId restated — the toolResult message already carries it. */
export interface QuestionAnswerData {
	kind: QuestionKind;
	/** The persisted call's tool NAME (owner, 2026-10-09): probe-phase
	 *  calls are `probe`/`recall`, teach calls `quiz`/`explain` — the
	 *  cards label by it ("Probe"/"Recall"), so the phase boundary is
	 *  visible in the transcript. Absent on pre-rename records: they
	 *  keep the kind-based labels. */
	tool?: string;
	/** quiz only (teach phase): the role snapshot for rendering (a
	 *  prediction tucks its explanation) and later calibration splits.
	 *  Absent on old records and probe answers. */
	questionType?: QuizQuestionType;
	questionText: string;
	options?: { index: number; label: string }[]; // snapshot for rendering
	dontKnow: boolean;
	answers: OptionAnswer[];
	other?: string; // ask: "Other" free text
	text?: string; // ask/explain: text-mode answer
	/** The learner's reasoning on the QUESTION (renamed from `note`, owner
	 *  2026-10-03 — "that's what it is"). */
	thinking?: string;
	/** @deprecated the pre-rename key — never written again; old records
	 *  replay through the same types, so it stays declared. Read via
	 *  `thinking ?? note`. */
	note?: string;
	/** The learner's thinking WHILE READING the teaching prose (owner
	 *  2026-10-03) — a separate channel from `thinking`, captured by the
	 *  reading field and riding the check answer. Absent when empty. */
	readingThinking?: string;
	confidence?: number; // quiz only: the learner's stated probability (0-100, raw) that his selected answer is correct — never sent on "I don't know" (owner, 2026-10-01)
	correct?: boolean; // quiz only
	correctIndices?: number[]; // quiz only (rendering)
	committed?: string; // explain only (rendering): the model's committed answer
	explanation?: string; // quiz only (rendering)
	dismissed?: boolean;
	answeredAt: string;
}

/** Client-facing question payload — deliberately omits the answer. */
export interface ClientQuestion {
	id: string;
	kind: QuestionKind;
	question: string;
	context?: string;
	mode: QuestionMode;
	options: QuizOption[];
}

/** What the server passes to the bridge when the learner answers. */
export interface AnswerRequest {
	dontKnow?: boolean;
	values?: string[]; // option values
	other?: string; // ask "Other"
	text?: string; // ask text-mode
	thinking?: string; // the reasoning-on-the-question channel (was `note`)
	readingThinking?: string; // the thinking-while-reading channel (check answers)
	confidence?: number; // quiz only: 0-100 raw probability — 50 is a real coin flip, always sent (owner, 2026-10-01)
}

/** The confidence slider's snap stops (owner, 2026-10-01): raw probability
 *  that the selected answer is correct, uneven on purpose — resolution
 *  concentrates at the top where the calibration signal lives (90 vs 100
 *  separates knows from mastered). 50 is a genuine coin flip and the
 *  resting default — untouched and deliberate 50 are the same number. */
export const CONFIDENCE_STOPS: readonly number[] = [0, 30, 50, 70, 90, 100];
export const DEFAULT_CONFIDENCE_INDEX = 2;

// ─── dock selection (the client state machine, pure for tests) ─────────────

/** The question dock's selection state (0-based indices in display order). */
export interface DockSelection {
	selected: Set<number>;
	otherSelected: boolean;
	dontKnow: boolean;
}

export const emptyDockSelection = (): DockSelection => ({ selected: new Set(), otherSelected: false, dontKnow: false });

/**
 * Toggling a listed option. Single-select: the option becomes THE answer and
 * displaces "Other". Multi-select: the option toggles alongside its siblings
 * AND "Other" — selections are independent (picking options must never clear
 * a custom answer, and picking the custom row must never clear them).
 */
export function toggleOption(mode: SelectMode, sel: DockSelection, idx: number): DockSelection {
	if (mode === "multi-select") {
		const selected = new Set(sel.selected);
		if (selected.has(idx)) selected.delete(idx);
		else selected.add(idx);
		return { selected, otherSelected: sel.otherSelected, dontKnow: false };
	}
	return { selected: new Set([idx]), otherSelected: false, dontKnow: false };
}

/**
 * Toggling the ask "Other…" row. Single-select: picking it makes it THE
 * answer, displacing the listed options (the typed text always survives).
 * Multi-select: it toggles alongside the listed selections and clears
 * nothing.
 */
export function toggleOther(mode: SelectMode, sel: DockSelection): DockSelection {
	if (mode === "multi-select") return { ...sel, otherSelected: !sel.otherSelected, dontKnow: false };
	return { selected: new Set(), otherSelected: true, dontKnow: false };
}

// ─── options ────────────────────────────────────────────────────────────────

export function normalizeOptions(
	options: string | Array<{ label: string; value?: string; description?: string }> | undefined,
): QuizOption[] {
	const seen = new Set<string>();
	// The persisted tool call can carry GLM's string-encoded options —
	// parseOptionsIfString is the same coercion the server's
	// prepareArguments runs pre-validation (see parseOptionsIfString).
	const coerced = parseOptionsIfString(options);
	const list = Array.isArray(coerced)
		? (coerced as Array<{ label: string; value?: string; description?: string }>)
		: [];
	return list
		.map((option) => ({
			label: option.label.trim(),
			value: option.value?.trim() || option.label.trim(),
			description: option.description?.trim() || undefined,
		}))
		.filter((option) => {
			if (option.label.length === 0) return false;
			if (seen.has(option.value)) throw new Error(`duplicate option value "${option.value}"`);
			seen.add(option.value);
			return true;
		});
}

/** Fisher-Yates over a copy. correctAnswer is keyed by value, so display
 *  order can be shuffled safely before resolving indices. */
// ─── options ────────────────────────────────────────────────────────────────

/** mulberry32 seeded by a string — deterministic shuffle for hydration-safe rendering. */
export function seededRandom(seed: string): () => number {
	let h = 2166136261;
	for (let i = 0; i < seed.length; i++) {
		h ^= seed.charCodeAt(i);
		h = Math.imul(h, 16777619);
	}
	let a = h >>> 0;
	return () => {
		a |= 0;
		a = (a + 0x6d2b79f5) | 0;
		let t = Math.imul(a ^ (a >>> 15), 1 | a);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/**
 * Fisher–Yates with an injectable RNG. Pass `seededRandom(toolCallId)` in
 * rendered components: Math.random() shuffles differently on server vs client
 * and breaks hydration (React #418). A per-toolCallId seed keeps the order
 * stable across reloads while still varying it per question.
 */
export function shuffleOptions(options: QuizOption[], rand: () => number = Math.random): QuizOption[] {
	const out = [...options];
	for (let i = out.length - 1; i > 0; i--) {
		const j = Math.floor(rand() * (i + 1));
		const a = out[i]!;
		const b = out[j]!;
		out[i] = b;
		out[j] = a;
	}
	return out;
}

// ─── quiz grading ───────────────────────────────────────────────────────────

/** Preserve an exact option key before trying copy-syntax cleanup: a
 *  label's final period, quotes, or backticks can be CONTENT (calculus
 *  incident, 2026-10-12), not model debris. The actual option values are
 *  required so no caller can strip a valid answer before membership.
 *  Non-matches keep the existing whitehead heal (`[":parmenides"]`) and
 *  JSON-stringified multi-select coercion. Shared by boundary, display,
 *  and grading; canonical option keys are never rewritten. */
export function coerceCorrectAnswer(
	correctAnswer: string | string[],
	optionValues: readonly string[],
): string[] {
	const clean = (value: string): string => {
		const trimmed = value.trim();
		return optionValues.includes(trimmed) ? trimmed : stripModelValueDebris(value);
	};
	if (Array.isArray(correctAnswer)) return correctAnswer.map(clean);
	const trimmed = correctAnswer.trim();
	// An exact string key can itself look like a JSON array.
	if (optionValues.includes(trimmed)) return [trimmed];
	if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
		try {
			const parsed = JSON.parse(trimmed);
			if (Array.isArray(parsed)) return parsed.map((v) => clean(String(v)));
		} catch {
			// not valid JSON — treat as a single literal value
		}
	}
	return [clean(correctAnswer)];
}

/** Resolve author-supplied value(s) to 1-based display indices. Keying by
 *  value (not position) makes a typo a hard error instead of a silent wrong
 *  grade. Must run AFTER shuffling. */
export function resolveCorrect(
	correctAnswer: string | string[] | undefined,
	options: QuizOption[],
): { indices: number[]; error?: string } {
	if (correctAnswer === undefined) return { indices: [], error: "correctAnswer is required" };
	const arr = coerceCorrectAnswer(correctAnswer, options.map((o) => o.value));
	if (arr.length === 0) return { indices: [], error: "correctAnswer is required" };
	const byValue = new Map(options.map((o, i) => [o.value, i + 1]));
	const indices: number[] = [];
	for (const raw of arr) {
		const v = typeof raw === "string" ? raw.trim() : raw;
		const idx = byValue.get(v);
		if (idx === undefined) {
			const known = options.map((o) => `"${o.value}"`).join(", ");
			return { indices: [], error: `correctAnswer "${v}" does not match any option value (${known})` };
		}
		indices.push(idx);
	}
	return { indices: Array.from(new Set(indices)).sort((a, b) => a - b) };
}

/** Exact-set match: same number of selections, same indices. */
export function isCorrect(selectedIndices: number[], correctIndices: number[]): boolean {
	if (selectedIndices.length !== correctIndices.length) return false;
	const a = [...selectedIndices].sort((x, y) => x - y);
	const b = [...correctIndices].sort((x, y) => x - y);
	return a.every((v, i) => v === b[i]);
}

// ─── arming + answering ─────────────────────────────────────────────────────

export function toClientQuestion(qd: QuestionData): ClientQuestion {
	return {
		id: qd.id,
		kind: qd.kind,
		question: qd.question,
		context: qd.context,
		mode: qd.mode,
		options: qd.options,
	};
}

function formatOptionRef(options: QuizOption[], index: number): string {
	const opt = options.find((o, i) => i + 1 === index);
	return `${index}. ${opt ? opt.label : "(unknown)"}`;
}

/**
 * Turn an AnswerRequest into the full answer record + the user message the
 * agent will see. Quiz answers are graded here; ask answers are not.
 */
export function buildAnswer(qd: QuestionData, req: AnswerRequest, tool?: string): QuestionAnswerData {
	const base: QuestionAnswerData = {
		kind: qd.kind,
		...(tool ? { tool } : {}),
		questionType: qd.questionType,
		questionText: qd.question,
		options: qd.options.map((o, i) => ({ index: i + 1, label: o.label })),
		dontKnow: req.dontKnow === true,
		answers: [],
		thinking: req.thinking?.trim() || undefined,
		readingThinking: req.readingThinking?.trim() || undefined,
		answeredAt: new Date().toISOString(),
	};
	// resolve selected option values → OptionAnswer (in display order)
	if (req.values && req.values.length > 0) {
		const byValue = new Map(qd.options.map((o, i) => [o.value, { ...o, index: i + 1 }]));
		for (const v of req.values) {
			const opt = byValue.get(v);
			if (!opt) continue; // unknown value — ignore
			base.answers.push({ label: opt.label, value: opt.value, index: opt.index });
		}
		base.answers.sort((a, b) => a.index - b.index);
	}
	if (req.other?.trim()) base.other = req.other.trim();
	if (req.text?.trim()) base.text = req.text.trim();

	if (qd.kind === "quiz") {
		base.correctIndices = qd.correctIndices ?? [];
		base.explanation = qd.explanation;
		base.correct = base.dontKnow ? false : isCorrect(base.answers.map((a) => a.index), qd.correctIndices ?? []);
		// The confidence slider rides on real quiz answers only — never on
		// "I don't know" (no answer, no probability). Clamped defensively;
		// the dock snaps to the grid, the record accepts any integer.
		if (!base.dontKnow && req.confidence !== undefined) {
			base.confidence = Math.max(0, Math.min(100, Math.round(req.confidence)));
		}
	}
	if (qd.kind === "explain") {
		// No client grading — the model grades in its reply, against the
		// commitment. The commitment snapshots for the reveal + rendering.
		base.committed = qd.committedAnswer;
	}
	return base;
}

/**
 * The MODEL-VISIBLE answer record (owner, tool-result diet 2026-10-02):
 * the tool call already carries everything the model itself authored —
 * the question, every option, the correct answer, the explanation, the
 * explain commitment — so the result returns ONLY what the learner added:
 * his selection or words, the graded verdict, his stated confidence, his
 * note. The full graded QuestionAnswerData rides `details` for the record
 * and the UI; this is the JSON the agent actually reads.
 */
/** The dismissal record (ESC-abort from a pending question, owner
 *  2026-10-02): the minimum honest answer. The model sees
 *  {kind, dismissed:true} via compactAnswerForModel; the answered card
 *  renders the question text + "skipped". Rides the same answer path —
 *  the teacher acknowledges the skip in its next turn, exactly like any
 *  answer. */
export function dismissedAnswer(kind: QuestionKind, questionText: string): QuestionAnswerData {
	return {
		kind,
		questionText,
		dontKnow: false,
		answers: [],
		dismissed: true,
		answeredAt: new Date().toISOString(),
	};
}

export function compactAnswerForModel(ad: QuestionAnswerData): Record<string, unknown> {
	if (ad.dismissed) return { kind: ad.kind, dismissed: true };
	const out: Record<string, unknown> = { kind: ad.kind };
	if (ad.dontKnow) out.dontKnow = true;
	// Array.isArray: the seam is called with `unknown` answers (test
	// fixtures, foreign records) — degrade to omission, never crash.
	if (Array.isArray(ad.answers) && ad.answers.length > 0)
		out.answers = ad.answers.map((a) => ({ index: a.index, label: a.label }));
	if (ad.text) out.text = ad.text;
	if (ad.other) out.other = ad.other;
	// The verdict + stated confidence are the learner's PERFORMANCE — new
	// information the model needs for its next move. (dontKnow implies
	// incorrect and carries no confidence: both stay implicit.)
	if (ad.correct !== undefined && !ad.dontKnow) out.correct = ad.correct;
	if (ad.confidence !== undefined) out.confidence = ad.confidence;
	// Two DISTINCT thinking channels, clearly keyed so the model never
	// conflates them (owner 2026-10-03): reasoning on the question vs
	// thinking while reading the teaching. `note` is the pre-rename key —
	// old records replay through here too, so both feed `thinking`.
	const thinking = ad.thinking ?? ad.note;
	if (thinking) out.thinking = thinking;
	if (ad.readingThinking) out.thinkingWhileReading = ad.readingThinking;
	return out;
}
