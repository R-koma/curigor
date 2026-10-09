import { describe, expect, it } from "vitest";
import { PAGE_TITLES, pageTitleFor } from "@/lib/nav-links";

describe("pageTitleFor", () => {
  it("names the three top-level pages", () => {
    expect(pageTitleFor("/dashboard")).toBe("今日の復習");
    expect(pageTitleFor("/notes")).toBe("学習履歴");
    expect(pageTitleFor("/collections")).toBe("まとめ");
  });

  it("returns null for nested and other pages", () => {
    expect(pageTitleFor("/notes/abc")).toBeNull();
    expect(pageTitleFor("/learn")).toBeNull();
  });

  it("exposes the same strings the pages use for their h1", () => {
    expect(PAGE_TITLES["/dashboard"]).toBe("今日の復習");
  });
});
