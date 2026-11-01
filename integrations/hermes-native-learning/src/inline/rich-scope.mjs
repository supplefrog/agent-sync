// SPDX-License-Identifier: AGPL-3.0-only
// Presentation roots are owned by the imperative card that replaces their DOM.
export function createRichScope(renderRich) {
  let cleanups=[];
  return {
    render(element,text) {
      element.textContent=typeof text==='string'?text:'';
      if(typeof renderRich!=='function'||typeof text!=='string')return;
      try {const dispose=renderRich(element,text);if(typeof dispose==='function')cleanups.push(dispose);}
      catch {element.textContent=text;}
    },
    clear() {const previous=cleanups;cleanups=[];for(const dispose of previous){try{dispose();}catch{/* Retired presentation cannot block the next card. */}}}
  };
}
