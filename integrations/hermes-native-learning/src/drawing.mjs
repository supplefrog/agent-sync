// SPDX-License-Identifier: AGPL-3.0-only
// Shared learner drawing contract, expressed as bounded, data-only strokes.
export const MAX_STROKES = 40;
export const MAX_POINTS = 320;
export const DRAWING_WIDTH = 1000;
export const DRAWING_HEIGHT = 600;

export function validDrawing(value) {
  if (!Array.isArray(value) || value.length === 0 || value.length > MAX_STROKES) return false;
  let points = 0;
  return Array.from(value).every(stroke => {
    if (!Array.isArray(stroke) || stroke.length === 0 || (points += stroke.length) > MAX_POINTS) return false;
    return Array.from(stroke).every(point => Array.isArray(point) && point.length === 3 &&
      Array.from(point).every(Number.isSafeInteger) && point[0] >= 0 && point[0] <= DRAWING_WIDTH &&
      point[1] >= 0 && point[1] <= DRAWING_HEIGHT && point[2] >= 1 && point[2] <= 10);
  });
}

export function drawingText(drawing, messageId) {
  return `Learner drawing attached to message ${messageId}. Use the bound drawing reader to inspect it. Stroke data (x, y, pressure in a 1000 by 600 canvas): ${JSON.stringify(drawing)}`;
}
