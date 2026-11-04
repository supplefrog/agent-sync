// SPDX-License-Identifier: AGPL-3.0-only
// Browser-safe adapter for the existing artifact components.
export const lessonVisualRows=view=>(view.visuals??[]).map(artifact=>({id:'visual-'+artifact.id,kind:artifact.kind,activity:artifact.title,execution:'saved',directVisual:true,artifact}));
