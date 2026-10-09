import { describe, expect, it } from "vitest";
import { PAGE_TITLES } from "@/lib/nav-links";

describe("PAGE_TITLES", () => {
  it("names the three top-level pages for their h1", () => {
    expect(PAGE_TITLES["/dashboard"]).toBe("今日の復習");
    expect(PAGE_TITLES["/notes"]).toBe("学習履歴");
    expect(PAGE_TITLES["/collections"]).toBe("まとめ");
  });
});
