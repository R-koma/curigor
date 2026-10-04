import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../..");
const UI_DIR = path.join("components", "ui");

function sourceFiles(dir: string): string[] {
  return readdirSync(path.join(ROOT, dir)).flatMap((name) => {
    const relative = path.join(dir, name);
    if (statSync(path.join(ROOT, relative)).isDirectory()) {
      return sourceFiles(relative);
    }
    return relative.endsWith(".tsx") ? [relative] : [];
  });
}

const FILES = [...sourceFiles("app"), ...sourceFiles("components")].filter(
  (file) => !file.startsWith(UI_DIR),
);

const PAIR = /(?<![:\w[-])(?:h-([0-9.]+) w-\1|w-([0-9.]+) h-\2)(?![\w-])/;
const NUMERIC_Z = /(?<![:\w-])z-\d+(?![\w-])/;
const ARBITRARY_TEXT = /text-\[[0-9.]+(?:rem|px)\]/;

function offenders(pattern: RegExp): string[] {
  return FILES.filter((file) =>
    pattern.test(readFileSync(path.join(ROOT, file), "utf8")),
  );
}

describe("size and layer tokens", () => {
  it("leaves no h-N w-N pair outside components/ui", () => {
    expect(offenders(PAIR)).toEqual([]);
  });

  it("leaves no numeric z-index outside components/ui", () => {
    expect(offenders(NUMERIC_Z)).toEqual([]);
  });

  it("leaves no arbitrary text size outside components/ui", () => {
    expect(offenders(ARBITRARY_TEXT)).toEqual([]);
  });

  it("uses text-prose for markdown", () => {
    const markdown = readFileSync(
      path.join(ROOT, "components/ui/markdown.tsx"),
      "utf8",
    );
    expect(markdown).toContain("text-prose");
    expect(markdown).not.toContain("text-[17px]");
  });

  it("does not flag pairs with different values", () => {
    expect(PAIR.test("h-1.5 w-4")).toBe(false);
    expect(PAIR.test("sm:h-4 sm:w-4")).toBe(false);
    expect(PAIR.test("h-4 w-4")).toBe(true);
    expect(PAIR.test("w-3.5 h-3.5")).toBe(true);
  });
});
