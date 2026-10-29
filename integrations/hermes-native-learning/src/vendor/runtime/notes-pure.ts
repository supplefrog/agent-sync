// SPDX-License-Identifier: AGPL-3.0-only
// Exact chunkNotes body from pinned LearnHarness6cba9c8 src/agent/subagents/extraction.ts; export only.
export function chunkNotes(text: string, budget: number): string[] {
		if (text.trim().length === 0) return [];
		const out: string[] = [];
		let current = "";
		for (const line of text.split("\n")) {
			const candidate = current.length === 0 ? line : current + "\n" + line;
			if (current.length > 0 && Math.ceil(candidate.length / 4) > budget) {
				out.push(current);
				current = line;
			} else {
				current = candidate;
			}
		}
		if (current.trim().length > 0) out.push(current);
		return out;
	}

