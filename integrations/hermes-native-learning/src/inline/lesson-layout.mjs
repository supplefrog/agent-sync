// SPDX-License-Identifier: AGPL-3.0-only
// Keep the same explorer node across rendering and width changes.
export function lessonResponseArea(dock, {exploration,workbench}) {
  if (!exploration) return dock;
  exploration.hidden = false;
  if (!workbench) {
    dock.append(exploration);
    return dock;
  }
  const grid = dock.ownerDocument.createElement('div');
  grid.className = 'lh-workbench';
  const response = dock.ownerDocument.createElement('div');
  response.className = 'lh-workbench-response';
  grid.append(exploration, response);
  dock.append(grid);
  return response;
}
