// SPDX-License-Identifier: AGPL-3.0-only
// Exact pure bridge/state portions of pinned LearnHarness6cba9c8 demo-card.tsx.
export const DEMO_BRIDGE_SCRIPT = `<script>(function(){
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
})();</script>`;

/** Inject the bridge before </body> (or at the end of a body-less document). */
export function buildDemoSrcDoc(html: string): string {
	if (/<\/body>/i.test(html)) return html.replace(/<\/body>/i, `${DEMO_BRIDGE_SCRIPT}</body>`);
	return `${html}${DEMO_BRIDGE_SCRIPT}`;
}

export interface DemoBridgeState {
	height: number | null;
	error: string | null;
}

export const INITIAL_DEMO_BRIDGE_STATE: DemoBridgeState = { height: null, error: null };

const MIN_HEIGHT = 80;
const MAX_HEIGHT = 2400;

/** Pure reducer over incoming postMessage data (contracts.ts DemoBridgeMessage). */
export function reduceDemoBridgeState(state: DemoBridgeState, data: unknown): DemoBridgeState {
	if (typeof data !== "object" || data === null) return state;
	const message = data as { type?: unknown; height?: unknown; message?: unknown };
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


