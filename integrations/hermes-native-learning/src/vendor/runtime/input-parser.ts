// SPDX-License-Identifier: AGPL-3.0-only
// LearnHarness v0.3.4, Amos Blomqvist. See NOTICE.md and provenance.json.
import type { QuestionAnswerData } from "./question-pure.ts";
export type ChatInput =
	| { type: "text"; text: string }
	| { type: "answer"; toolCallId: string; answer: QuestionAnswerData }
	| { type: "continue" }
	/** The practice dock's two buttons (owner, 2026-10-04): the learner's
	 *  thinking on the ACTIVE problem — one lane (owner 2026-10-05):
	 *  whether it claims an answer is read from the text. One
	 *  problem may carry many submissions; each is its own turn. */
	| { type: "thinking"; problemCallId: string; text: string }
	/** The practice move-on signal (owner round 16): the learner's
	 *  explicit go-ahead during the between-problems pause — the Next
	 *  chip or Enter on an empty composer. Practice sessions only, and
	 *  only with nothing active (mid-problem input rides the dock). */
	| { type: "next" };

export class ChatInputError extends Error {}

/** Parse and validate an input event off a request body. */
export function parseChatInput(input: unknown): ChatInput {
	if (typeof input !== "object" || input === null) throw new ChatInputError("input must be an object");
	const i = input as Record<string, unknown>;
	switch (i.type) {
		case "text":
			if (typeof i.text !== "string" || (i.text as string).trim().length === 0) {
				throw new ChatInputError("text input requires non-empty text");
			}
			return { type: "text", text: i.text };
		case "answer":
			if (typeof i.toolCallId !== "string" || i.toolCallId.length === 0) {
				throw new ChatInputError("answer input requires toolCallId");
			}
			if (typeof i.answer !== "object" || i.answer === null) {
				throw new ChatInputError("answer input requires the graded answer object");
			}
			return { type: "answer", toolCallId: i.toolCallId, answer: i.answer as QuestionAnswerData };
		case "continue":
			return { type: "continue" };
		case "thinking":
			if (typeof i.problemCallId !== "string" || i.problemCallId.length === 0) {
				throw new ChatInputError("thinking input requires problemCallId");
			}
			if (typeof i.text !== "string" || i.text.trim().length === 0) {
				throw new ChatInputError("thinking input requires non-empty text");
			}
			return { type: "thinking", problemCallId: i.problemCallId, text: i.text };
		case "next":
			return { type: "next" };
		default:
			throw new ChatInputError(`unknown input type: ${String(i.type)}`);
	}
}

