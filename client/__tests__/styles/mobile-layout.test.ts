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
      'navbarCenter !== null ? "flex border-b md:border-b-0" : "hidden"',
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

  it.each([
    ["the dashboard review list", "app/(main)/dashboard/page.tsx"],
    ["the note list", "components/notes/note-list.tsx"],
  ])("%s keeps the card menu out of the meta row", (_, file) => {
    const code = source(file);
    expect(code).not.toContain("absolute right-3 bottom-3");
    expect(code).toContain("absolute right-3 top-3");
    expect(code).toContain(
      '"flex items-start justify-between gap-4 pr-9 pointer-coarse:pr-0"',
    );
  });

  it.each([
    "app/(main)/dashboard/page.tsx",
    "app/(main)/notes/page.tsx",
    "app/(main)/notes/loading.tsx",
    "app/(main)/collections/page.tsx",
    "app/(main)/collections/[id]/page.tsx",
    "app/(main)/collections/loading.tsx",
  ])("%s uses the narrow page gutter below md", (file) => {
    const code = source(file);
    expect(code).not.toContain('"mx-auto max-w-4xl px-6 py-8"');
    expect(code).toContain('"mx-auto max-w-4xl px-4 py-6 md:px-6 md:py-8"');
  });

  it("scales the note detail for narrow screens", () => {
    const page = source("app/(main)/notes/[id]/page.tsx");
    expect(page).toContain('"mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-12"');
    expect(page).toContain(
      '"text-base text-foreground/80 md:text-lg [&_p]:my-3 [&_p]:leading-8"',
    );
    const header = source("components/notes/note-header.tsx");
    expect(header).toContain('"mb-6 md:mb-12"');
    expect(header).toContain(
      '"text-xl font-bold tracking-tight md:text-3xl lg:text-4xl"',
    );
    expect(source("components/review/review-start-screen.tsx")).toContain(
      '"mx-auto max-w-3xl px-4 py-6 md:px-6 md:py-8"',
    );
  });

  it("keeps each top page's h1 for screen readers but shows the title in the mobile header row", () => {
    for (const file of [
      "app/(main)/dashboard/page.tsx",
      "app/(main)/notes/page.tsx",
      "app/(main)/collections/page.tsx",
    ]) {
      const code = source(file);
      expect(code, file).toContain("<PageHeading");
      expect(code, file).toContain("PAGE_TITLES[");
      expect(code, file).not.toContain("border-l-4 border-muted-foreground/40");
    }
  });

  it.each([
    "app/(main)/dashboard/page.tsx",
    "app/(main)/notes/loading.tsx",
    "app/(main)/collections/loading.tsx",
  ])(
    "%s hides the heading placeholder on mobile like the loaded page",
    (file) => {
      expect(source(file)).toMatch(/max-md:hidden/);
    },
  );

  it("deletes a review card by swiping on touch and hides its more-actions menu there", () => {
    const code = source("app/(main)/dashboard/page.tsx");
    expect(code).toContain("<SwipeToDelete");
    expect(code).toContain("pointer-coarse:hidden");
  });

  it("drops the dashboard's new-learning button on mobile, where the tab bar already starts one", () => {
    const code = source("app/(main)/dashboard/page.tsx");
    expect(code).toContain(
      '<div className="flex shrink-0 flex-col items-end gap-3 max-md:hidden">',
    );
    expect(code).toContain(
      '<div className="mb-6 flex items-start justify-between max-md:hidden">',
    );
  });

  it("offers a way to start learning from the empty review list", () => {
    const code = source("app/(main)/dashboard/page.tsx");
    const empty = code.slice(code.indexOf("<EmptyState"));
    expect(empty.slice(0, empty.indexOf("/>") + 400)).toContain("新しく学ぶ");
  });

  it("pins the previous conversation to the top of the learn start screen on every width", () => {
    const code = source("app/(main)/learn/page.tsx");
    expect(code).not.toContain(
      "items-start justify-center overflow-y-auto p-4 md:items-center",
    );
    expect(code).toContain(
      '"flex h-full flex-col items-center overflow-y-auto p-4"',
    );
    expect(code).toContain('"space-y-8 pt-4 md:my-auto"');
  });

  it.each([
    ["app/(main)/dashboard/page.tsx", "件 · "],
    ["app/(main)/notes/page.tsx", "ノート ${"],
    ["app/(main)/collections/page.tsx", "まとめノート ${"],
  ])("%s says where things stand under its heading", (file, phrase) => {
    expect(source(file)).toContain(phrase);
  });
});
