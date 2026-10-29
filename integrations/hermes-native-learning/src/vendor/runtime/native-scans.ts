// SPDX-License-Identifier: AGPL-3.0-only
// LearnHarness v0.3.4, Amos Blomqvist. See NOTICE.md and provenance.json.
import { QUESTION_TOOLS } from "./pending.ts";
import type { LhMessage } from "../upstream/src/core/native-messages.ts";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { AssistantMessage, ToolResultMessage } from "@earendil-works/pi-ai";
const PRACTICE_PROBLEM_TOOL = "problem";
function resultIdsFrom(messages: readonly AgentMessage[]): Set<string> {
	const ids = new Set<string>();
	for (const m of messages) {
		if ((m as { role?: string }).role === "toolResult") {
			ids.add((m as ToolResultMessage).toolCallId);
		}
	}
	return ids;
}

export function danglingQuestionOf(
	messages: readonly LhMessage[],
): { toolCallId: string; tool: string; input: unknown } | null {
	for (let mi = messages.length - 1; mi >= 0; mi--) {
		const m = messages[mi]!;
		if ((m as { role?: string }).role !== "assistant") continue;
		const assistant = m as AssistantMessage & { id: string };
		const answered = resultIdsFrom(messages.slice(mi + 1));
		for (const block of assistant.content) {
			if (block.type !== "toolCall") continue;
			if (!(QUESTION_TOOLS as readonly string[]).includes(block.name)) continue;
			if (answered.has(block.id)) continue;
			return { toolCallId: block.id, tool: block.name, input: block.arguments };
		}
		return null; // the newest assistant message's questions are all answered
	}
	return null;
}

/** The probe→teach construction seam (chat-handler): a probe_done call in
 *  the transcript — any state — means the probe is concluded: teach. */
export function hasProbeDone(messages: readonly LhMessage[]): boolean {
	for (const m of messages) {
		if ((m as { role?: string }).role !== "assistant") continue;
		const assistant = m as AssistantMessage;
		if (assistant.content.some((b) => b.type === "toolCall" && b.name === "probe_done")) return true;
	}
	return false;
}

/** Every toolResult id in the record — answer-event validation (the call
 *  must be a DANGLING question call, not an already-answered one). */
export function answeredCallIds(messages: readonly LhMessage[]): Set<string> {
	return resultIdsFrom(messages);
}

// ─── the continuation fold (Wave D: the SDK's
//     lastAssistantMessageIsCompleteWithToolCalls, natively) ──────────────────

/**
 * Does the record END on un-consumed tool results — a turn that stopped
 * after its tools ran (a job dispatch's ack, an aborted answer turn),
 * leaving the agent owing a continuation? This is the mount/sync
 * continuation seam's gate (chat.tsx): when true and nothing runs, the
 * client sends {type:"continue"} and the teacher picks up from the record.
 *
 * The pre-Wave-D client asked the SDK's
 * lastAssistantMessageIsCompleteWithToolCalls (last view message is
 * assistant; its last step's tool calls all output-available or
 * output-error; at least one). The native fold over the record: the last
 * message is a toolResult, and the results' OWNING assistant message has
 * at least one call, ALL of them answered (a dangling question — the
 * dock's domain — fails the all-answered rule and never fires a turn,
 * exactly as the SDK's every(output-available) did).
 */
/** Is this record message a user-dismissed question result? The full
 *  answer rides the toolResult's `details` (newAnswerResult) — the
 *  dismissal pause and the continuation fold both read it. */
function isDismissedResult(m: LhMessage): boolean {
	if ((m as { role?: string }).role !== "toolResult") return false;
	const details = (m as { details?: unknown }).details as { dismissed?: unknown } | undefined;
	return details?.dismissed === true;
}

/** The dismissal pause (owner design 2026-10-03, "A2"): the record ends
 *  in user dismissal — the session waits for the USER. While paused,
 *  nothing auto-wakes: the continuation fold demands nothing (below) and
 *  the wake pipeline holds job deliveries in the steer queue until the
 *  next send. Derived from the tail — no latch to persist or clear; any
 *  user message flips it off by changing the record. */
export function endsInDismissal(messages: readonly LhMessage[]): boolean {
	const last = messages[messages.length - 1];
	return last !== undefined && isDismissedResult(last);
}

export function needsContinuation(messages: readonly LhMessage[]): boolean {
	const last = messages[messages.length - 1];
	if (!last || (last as { role?: string }).role !== "toolResult") return false;
	// The trailing results batch (contiguous by construction — the agent
	// appends its batch; the question gate keeps a quiz call and its
	// learner answer adjacent).
	let start = messages.length - 1;
	while (
		start > 0 &&
		(messages[start - 1] as { role?: string } | undefined)?.role === "toolResult"
	) {
		start--;
	}
	// The dismissal rule (A2 + owner ruling 2026-10-03, round-1 incident):
	// the batch's LAST resolution decides. Ending on a dismissal = the
	// user signaled STOP — no wake, no reaction owed now; the answers'
	// reactions ride the user's next plain message. Ending on a real
	// answer = the reaction is owed. One law with the pump's pause
	// (endsInDismissal reads the same last result), so continuation,
	// delivery-holding, and the pause can never disagree.
	if (isDismissedResult(messages[messages.length - 1]!)) {
		return false;
	}
	const owner = messages[start - 1];
	if (!owner || (owner as { role?: string }).role !== "assistant") return false;
	const content = (owner as { content?: unknown }).content;
	if (!Array.isArray(content)) return false;
	const results = messages.slice(start) as ToolResultMessage[];
	// PRACTICE (owner design, 2026-10-04): a batch acking a problem POSE
	// owes nothing — terminate:true ended that turn DELIBERATELY (the
	// learner's next thinking submission is the next turn), and unlike a
	// question's placeholder this ack PERSISTS (the model reads its own
	// "Problem posed" result later). Without this fold a reload after a
	// pose would wake a phantom continuation turn.
	const posedProblem = results.some(
		(m) => m.toolName === PRACTICE_PROBLEM_TOOL && !m.isError && m.details == null,
	);
	if (posedProblem) return false;
	const answered = new Set(results.map((m) => m.toolCallId));
	const calls = (content as Array<{ type?: string; id?: string }>).filter(
		(b) => b.type === "toolCall" && typeof b.id === "string",
	);
	return calls.length > 0 && calls.every((b) => answered.has(b.id!));
}
