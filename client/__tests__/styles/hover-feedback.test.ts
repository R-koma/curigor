import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

function source(file: string): string {
  return readFileSync(path.resolve(__dirname, "../..", file), "utf8");
}

describe("note cards", () => {
  it.each([
    ["the note list", "components/notes/note-list.tsx"],
    ["the dashboard review list", "app/(main)/dashboard/page.tsx"],
  ])("%s do not move on hover and tint their background instead", (_, file) => {
    const code = source(file);
    expect(code).not.toMatch(/hover:-?translate-y/);
    expect(code).toContain("hover:bg-muted/60");
  });
});

function sourceFiles(dir: string): string[] {
  const root = path.resolve(__dirname, "..", "..");
  return readdirSync(path.join(root, dir)).flatMap((name) => {
    const relative = path.join(dir, name);
    if (statSync(path.join(root, relative)).isDirectory()) {
      return sourceFiles(relative);
    }
    return relative.endsWith(".tsx") ? [relative] : [];
  });
}

describe("interaction feedback", () => {
  it("never moves, grows, shrinks or rotates an element on hover, press or state change", () => {
    const motion =
      /(?:^|[\s"'`])(?:group-hover[\w/-]*|hover|active|group-data-\[[^\]]+\]):-?(?:translate|scale|rotate)/;
    const offenders = [...sourceFiles("app"), ...sourceFiles("components")]
      .filter((file) => !file.startsWith(path.join("components", "ui")))
      .filter((file) => motion.test(source(file)));
    expect(offenders).toEqual([]);
  });
});
