import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  path.resolve(__dirname, "../../app/globals.css"),
  "utf8",
);

function selectorsWith(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`([^{}]*${escaped}[^{}]*)\\{`).exec(css)?.[1] ?? "";
}

describe("code editor highlighting", () => {
  it.each([
    [".hljs-comment", ".tok-comment"],
    [".hljs-keyword", ".tok-keyword"],
    [".hljs-string", ".tok-string"],
    [".hljs-number", ".tok-number"],
    [".hljs-title", ".tok-className"],
  ])("colors %s and %s the same", (hljs, tok) => {
    expect(selectorsWith(hljs)).toContain(tok);
  });
});
