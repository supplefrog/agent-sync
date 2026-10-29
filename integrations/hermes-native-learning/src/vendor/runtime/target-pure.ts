// SPDX-License-Identifier: AGPL-3.0-only
// Exact resolveTargetId body, upstream core/chains.ts at6cba9c8c.
// Type-only alias avoids importing the standalone graph/runtime.
import { stripModelValueDebris } from './value-debris.ts';
type GraphNode = {id:string;name:string};
export function resolveTargetId(
	target: string,
	nodes: ReadonlyArray<Pick<GraphNode, "id" | "name">>,
): string | null {
	const t = stripModelValueDebris(target);
	if (t.length === 0) return null;
	if (nodes.some((n) => n.id === t)) return t;
	const lower = t.toLowerCase();
	for (const n of nodes) {
		if (stripModelValueDebris(n.name).toLowerCase() === lower) return n.id;
	}
	return null;
}

