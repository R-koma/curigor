import { readFileSync } from "node:fs";
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
