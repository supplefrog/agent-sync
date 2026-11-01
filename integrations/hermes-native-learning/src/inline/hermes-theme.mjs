// SPDX-License-Identifier: AGPL-3.0-only
// Adapter-local aliases: Hermes defines dt-* tokens, not the dock's card/ring aliases.
// Keep the color pairs in one host theme; never fall back to a dark card in light mode.
export const HERMES_LESSON_THEME = `
.lh-native-lesson {
  --background: var(--dt-background, Canvas);
  --foreground: var(--dt-card-foreground, var(--dt-foreground, CanvasText));
  --card: var(--dt-card, Canvas);
  --muted-foreground: var(--dt-secondary-foreground, var(--dt-muted-foreground, var(--foreground)));
  --border: var(--dt-border, var(--foreground));
  --accent: var(--dt-accent, var(--card));
  --ring: var(--dt-ring, var(--foreground));
  --destructive: var(--dt-destructive, var(--foreground));
}
.lh-native-lesson textarea::placeholder, .lh-native-lesson input::placeholder {
  color: var(--muted-foreground);
  opacity: 1;
}
`;
