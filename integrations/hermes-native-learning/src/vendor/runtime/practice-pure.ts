// SPDX-License-Identifier: AGPL-3.0-only
// LearnHarness v0.3.4, Amos Blomqvist. See practice-provenance.json.
import * as crypto from "node:crypto";
type LhMessage = any; type LhMarkerMessage = any; type AssistantMessage = any; type ToolResultMessage = any;
const PRACTICE_PROBLEM_TOOL = "problem"; const PRACTICE_CONCLUDE_TOOL = "conclude";
export const THINKING_LABEL = "Your thinking";
export const CONCLUDE_ACK_TEXT =
	"Problem concluded. Say your closing words about the learner's work if useful, then END YOUR TURN — no further tool calls. The next problem is NEVER posed here: it waits for the learner's explicit go-ahead (a *Next problem* message, or their own words asking for the next one). Between problems, answer their questions about the concluded one.";
export const NEXT_PROBLEM_TEXT =
	"[NEXT PROBLEM] — the learner's explicit go-ahead: pose the next problem now per the selection rules, or wrap the session in text if the arc is complete.";
export function newMessageId(): string {
	return `msg_${Date.now().toString(36)}_${crypto.randomUUID().slice(0, 8)}`;
}

function cleanToolCallIds(messages: readonly LhMessage[]): Set<string> {
	const ids = new Set<string>();
	for (const m of messages) {
		if ((m as { role?: string }).role !== "toolResult") continue;
		const result = m as ToolResultMessage;
		if (!result.isError) ids.add(result.toolCallId);
	}
	return ids;
}

export function problemInputForConclude(
	messages: readonly LhMessage[],
	concludeCallId: string,
): { statement?: unknown; mode?: unknown; target?: unknown; modelSolution?: unknown } | undefined {
	let mi = messages.findIndex(
		(m) =>
			(m as { role?: string }).role === "assistant" &&
			(m as AssistantMessage).content.some(
				(b) => b.type === "toolCall" && b.id === concludeCallId,
			),
	);
	if (mi < 0) return undefined;
	const clean = cleanToolCallIds(messages);
	for (; mi >= 0; mi--) {
		const m = messages[mi]!;
		if ((m as { role?: string }).role !== "assistant") continue;
		const assistant = m as AssistantMessage;
		for (let bi = assistant.content.length - 1; bi >= 0; bi--) {
			const block = assistant.content[bi]!;
			if (block.type !== "toolCall" || block.name !== PRACTICE_PROBLEM_TOOL) continue;
			if (!clean.has(block.id)) continue; // a refused pose revealed nothing
			return (block.arguments ?? undefined) as
				| { statement?: unknown; mode?: unknown; target?: unknown; modelSolution?: unknown }
				| undefined;
		}
	}
	return undefined;
}

export function modelSolutionForConclude(
	messages: readonly LhMessage[],
	concludeCallId: string,
): string | undefined {
	const input = problemInputForConclude(messages, concludeCallId);
	return typeof input?.modelSolution === "string" ? input.modelSolution : undefined;
}

export function activeProblemOf(
	messages: readonly LhMessage[],
): { toolCallId: string; input: unknown } | null {
	// HONEST ACTIVATION (owner ruling, 2026-10-05 — the BKT incident):
	// calls count only through their RESULTS — a problem activates on its
	// clean ack, a conclude frees on its clean ack; errored and dangling
	// calls are skipped ("either it goes through or it doesn't").
	const cleanCallIds = cleanToolCallIds(messages);
	for (let mi = messages.length - 1; mi >= 0; mi--) {
		const m = messages[mi]!;
		const role = (m as { role?: string }).role;
		if (role === "custom") {
			const marker = m as LhMarkerMessage;
			if (marker.customType === "problem-dismissed") return null;
			continue;
		}
		if (role === "assistant") {
			const assistant = m as AssistantMessage & { id: string };
			for (let bi = assistant.content.length - 1; bi >= 0; bi--) {
				const block = assistant.content[bi]!;
				if (block.type !== "toolCall") continue;
				if (block.name === PRACTICE_CONCLUDE_TOOL) {
					if (cleanCallIds.has(block.id)) return null; // a CLEAN conclude frees
					continue; // errored/dangling conclude: the free never happened
				}
				if (block.name !== PRACTICE_PROBLEM_TOOL) continue;
				if (cleanCallIds.has(block.id)) return { toolCallId: block.id, input: block.arguments };
				// errored/dangling pose — it did not go through; keep scanning
			}
			continue;
		}
	}
	return null;
}

export function newThinkingMessage(problemCallId: string, text: string): LhMarkerMessage {
	return {
		id: newMessageId(),
		role: "custom",
		customType: "practice-thinking",
		content: `${THINKING_LABEL}:\n${text}`,
		display: true,
		details: { problemCallId, text },
		timestamp: Date.now(),
	};
}

export function newNextMessage(): LhMarkerMessage {
	return {
		id: newMessageId(),
		role: "custom",
		customType: "practice-next",
		content: NEXT_PROBLEM_TEXT,
		display: true,
		details: {},
		timestamp: Date.now(),
	};
}
