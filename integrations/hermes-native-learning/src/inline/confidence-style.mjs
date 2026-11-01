// SPDX-License-Identifier: AGPL-3.0-only
// Paint port of LearnHarness v0.3.4 components/confidence-rail.tsx.
// Same six-stop ramp, center-inset geometry and ticks; no grading or submission.
import { CONFIDENCE_STOPS } from '../vendor/runtime/question-pure.ts';
export const CONFIDENCE_COLORS = ['#ef4444','#f97316','#eab308','#84cc16','#22c55e','#10b981'];
export function nearestConfidenceIndex(value) {
  let best=0;
  for(let i=1;i<CONFIDENCE_STOPS.length;i++)
    if(Math.abs(CONFIDENCE_STOPS[i]-value)<Math.abs(CONFIDENCE_STOPS[best]-value))best=i;
  return best;
}
export function confidenceRailStyle(value) {
  const color=CONFIDENCE_COLORS[CONFIDENCE_STOPS.indexOf(value)]??CONFIDENCE_COLORS[2];
  return {backgroundColor:'#141414',backgroundImage:[
    `linear-gradient(90deg, ${color} 0%, ${color} ${value}%, transparent ${value}%, transparent 100%)`,
    ...[30,50,70,90].map(()=> 'linear-gradient(90deg, rgba(230,230,230,0.35), rgba(230,230,230,0.35))')
  ].join(', '),backgroundSize:['100% 100%','1px 100%','1px 100%','1px 100%','1px 100%'].join(', '),
  backgroundPosition:['0 0',...[30,50,70,90].map(p=>`${p}% 0`)].join(', '),backgroundRepeat:'no-repeat'};
}
