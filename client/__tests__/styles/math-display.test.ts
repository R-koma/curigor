import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  path.resolve(__dirname, "../../app/globals.css"),
  "utf8",
);

describe("display math", () => {
  it("scrolls inside the formula instead of widening the page", () => {
    const rule = /\.katex-display\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
    expect(rule).toContain("overflow-x: auto");
  });
});
