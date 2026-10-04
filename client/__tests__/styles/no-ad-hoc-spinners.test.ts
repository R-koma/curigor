import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../..");
const ALLOWED = new Set([path.join("components", "ui", "spinner.tsx")]);

function sourceFiles(dir: string): string[] {
  return readdirSync(path.join(ROOT, dir)).flatMap((name) => {
    const relative = path.join(dir, name);
    if (statSync(path.join(ROOT, relative)).isDirectory()) {
      return sourceFiles(relative);
    }
    return relative.endsWith(".tsx") ? [relative] : [];
  });
}

describe("spinners", () => {
  it("are rendered through the Spinner component only", () => {
    const offenders = [...sourceFiles("app"), ...sourceFiles("components")]
      .filter((file) => !ALLOWED.has(file))
      .filter((file) =>
        readFileSync(path.join(ROOT, file), "utf8").includes("animate-spin"),
      );
    expect(offenders).toEqual([]);
  });
});
