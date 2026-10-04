import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const RAW_PALETTE =
  /\b(?:bg|text|border|ring|fill|stroke|from|to|via|shadow|outline|decoration)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d{2,3}/;

const MIGRATED = [
  "app/(main)/dashboard/page.tsx",
  "app/(main)/learn/page.tsx",
  "components/chat/intake-card.tsx",
  "components/chat/depth-map-panel.tsx",
  "components/chat/learning-progress.tsx",
  "components/chat/voice-mode-toggle.tsx",
  "components/chat/topic-suggestions.tsx",
  "components/chat/message-speech-button.tsx",
  "components/chat/end-session-button.tsx",
  "components/layout/sidebar-calendar.tsx",
];

describe("migrated files use tokens instead of raw palette colors", () => {
  it.each(MIGRATED)("%s", (file) => {
    const source = readFileSync(path.resolve(__dirname, "../..", file), "utf8");
    expect(source.match(RAW_PALETTE)).toBeNull();
  });
});
