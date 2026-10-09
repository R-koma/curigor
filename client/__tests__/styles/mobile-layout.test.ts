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

  it("shows the sidebar and the navbar only from md, and the mobile header and tab bar below it", () => {
    const shell = source("components/layout/main-layout-client.tsx");
    expect(shell).toContain("<MobileHeader");
    expect(shell).toContain("<MobileTabBar");
    expect(source("components/layout/sidebar.tsx")).toContain(
      '"relative hidden shrink-0 md:flex"',
    );
    expect(source("components/layout/navbar.tsx")).toContain(
      '"relative hidden min-h-15 shrink-0 items-center bg-background/80 px-6 py-3 backdrop-blur-lg md:flex"',
    );
  });

  it.each(["app/(main)/learn/page.tsx", "app/(main)/review/[noteId]/page.tsx"])(
    "%s builds its header slot from SessionHeader",
    (file) => {
      const code = source(file);
      expect(code).toContain("<SessionHeader");
      expect(code).not.toContain("<EndSessionButton");
      expect(code).not.toContain("<ReconnectingIndicator");
    },
  );

  it.each([
    "app/(main)/learn/page.tsx",
    "app/(main)/review/[noteId]/page.tsx",
    "components/collections/synthesis-chat.tsx",
  ])("%s uses the narrow gutter below md in the chat column", (file) => {
    const code = source(file);
    expect(code).not.toContain('"flex-1 overflow-y-auto px-6"');
    expect(code).toContain('"flex-1 overflow-y-auto px-4 md:px-6"');
  });

  it.each(["app/(main)/learn/page.tsx", "app/(main)/review/[noteId]/page.tsx"])(
    "%s keeps the input above the home bar",
    (file) => {
      expect(source(file)).toContain(
        '"shrink-0 bg-background/95 px-4 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] backdrop-blur-sm md:px-6 md:pb-4"',
      );
    },
  );
});
