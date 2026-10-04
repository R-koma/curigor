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
