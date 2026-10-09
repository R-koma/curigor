import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

function source(file: string): string {
  return readFileSync(path.resolve(__dirname, "../..", file), "utf8");
}

describe("mobile layout", () => {
  it("declares a viewport that reaches under the notch and home bar", () => {
    const code = source("app/layout.tsx");
    expect(code).toContain("export const viewport");
    expect(code).toContain('viewportFit: "cover"');
  });

  it("sizes the shell with dvh, not vh, so the mobile address bar does not hide the input", () => {
    const code = source("components/layout/main-layout-client.tsx");
    expect(code).toContain("h-dvh");
    expect(code).not.toMatch(/\bh-screen\b/);
  });
});
