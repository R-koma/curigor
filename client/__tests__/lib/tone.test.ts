import { describe, expect, it } from "vitest";
import { TONE_CLASSES, TONES } from "@/lib/tone";

const RAW_PALETTE =
  /\b(?:bg|text|border|ring|fill|stroke|from|to|via|shadow|outline|decoration)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d{2,3}/;

describe("TONE_CLASSES", () => {
  it("covers every tone", () => {
    expect(Object.keys(TONE_CLASSES).sort()).toEqual([...TONES].sort());
  });

  it.each(TONES)("%s defines text, soft, border and marker", (tone) => {
    const classes = TONE_CLASSES[tone];
    for (const key of ["text", "soft", "border", "marker"] as const) {
      expect(classes[key].trim()).not.toBe("");
    }
  });

  it("uses tokens instead of raw palette colors", () => {
    for (const tone of TONES) {
      for (const value of Object.values(TONE_CLASSES[tone])) {
        expect(value).not.toMatch(RAW_PALETTE);
      }
    }
  });

  it("maps the status tones to their tokens", () => {
    expect(TONE_CLASSES.success.text).toBe("text-success-text");
    expect(TONE_CLASSES.warning.soft).toBe("bg-warning-soft");
    expect(TONE_CLASSES.caution.border).toBe("border-caution");
    expect(TONE_CLASSES.brand.marker).toBe("bg-brand");
    expect(TONE_CLASSES.danger.text).toBe("text-destructive");
  });
});
