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
  "components/notes/note-list.tsx",
  "components/notes/note-feedback-card.tsx",
  "components/notes/note-aspect-map.tsx",
  "components/collections/collection-synthesis.tsx",
  "components/landing/landing-auth-cta.tsx",
  "components/landing/landing-cta.tsx",
  "components/landing/landing-features.tsx",
  "components/landing/landing-footer.tsx",
  "components/landing/landing-header.tsx",
  "components/landing/landing-hero.tsx",
  "components/landing/landing-how-it-works.tsx",
  "app/(auth)/layout.tsx",
  "app/(auth)/sign-in/page.tsx",
  "app/(auth)/sign-up/page.tsx",
  "components/auth/google-login-button.tsx",
];

describe("migrated files use tokens instead of raw palette colors", () => {
  it.each(MIGRATED)("%s", (file) => {
    const source = readFileSync(path.resolve(__dirname, "../..", file), "utf8");
    expect(source.match(RAW_PALETTE)).toBeNull();
  });
});

describe("opengraph-image", () => {
  const source = readFileSync(
    path.resolve(__dirname, "../..", "app/opengraph-image.tsx"),
    "utf8",
  );

  it.each(["#1e1b4b", "#312e81", "#4338ca", "#c7d2fe"])(
    "no longer uses the indigo %s",
    (hex) => {
      expect(source.toLowerCase()).not.toContain(hex);
    },
  );

  it.each(["#172554", "#1e3a8a", "#1d4ed8", "#bfdbfe"])(
    "uses the blue %s",
    (hex) => {
      expect(source.toLowerCase()).toContain(hex);
    },
  );
});
