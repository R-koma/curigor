import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  path.resolve(__dirname, "../../app/globals.css"),
  "utf8",
);

function block(opener: string): string {
  const start = css.indexOf(`${opener} {`);
  if (start === -1) throw new Error(`${opener} not found`);
  const end = css.indexOf("\n}", start);
  return css.slice(start, end);
}

const COLOR_TOKENS = [
  "brand",
  "brand-foreground",
  "brand-soft",
  "brand-text",
  "brand-deep",
  "brand-strong",
  "success",
  "success-soft",
  "success-text",
  "warning",
  "warning-soft",
  "warning-text",
  "caution",
  "caution-soft",
  "caution-text",
  "destructive-foreground",
];

describe("color tokens in globals.css", () => {
  const root = block(":root");
  const dark = block(".dark");
  const theme = block("@theme inline");

  it.each(COLOR_TOKENS)("%s is defined for light and dark", (name) => {
    expect(root).toContain(`--${name}:`);
    expect(dark).toContain(`--${name}:`);
  });

  it.each(COLOR_TOKENS)("%s is registered as a Tailwind color", (name) => {
    expect(theme).toContain(`--color-${name}: var(--${name});`);
  });

  it.each([1, 2, 3, 4, 5])("chart-%i is a distinct hue per slot", (n) => {
    expect(root).toContain(`--chart-${n}:`);
    expect(dark).toContain(`--chart-${n}:`);
  });

  it("keeps --primary unchanged", () => {
    expect(root).toContain("--primary: oklch(0.205 0 0);");
    expect(dark).toContain("--primary: oklch(0.87 0 0);");
  });
});

describe("utilities in globals.css", () => {
  it.each([
    ["z-raised", "10"],
    ["z-menu", "20"],
    ["z-drawer", "40"],
    ["z-overlay", "50"],
  ])("%s sets z-index %s", (name, value) => {
    expect(css).toMatch(
      new RegExp(`@utility ${name} \\{\\s*z-index: ${value};\\s*\\}`),
    );
  });

  it.each(["bg-brand-wash", "bg-brand-bold"])("defines %s", (name) => {
    expect(css).toContain(`@utility ${name} {`);
  });

  it("defines the gradient stops for light and dark", () => {
    const root = block(":root");
    const dark = block(".dark");
    for (const stop of [
      "brand-wash-from",
      "brand-wash-via",
      "brand-wash-to",
      "brand-bold-from",
      "brand-bold-to",
    ]) {
      expect(root).toContain(`--${stop}:`);
      expect(dark).toContain(`--${stop}:`);
    }
  });

  it("defines the text sizes", () => {
    const theme = block("@theme inline");
    expect(theme).toContain("--text-3xs: 0.625rem;");
    expect(theme).toContain("--text-2xs: 0.6875rem;");
    expect(theme).toContain("--text-prose: 1.0625rem;");
  });
});
