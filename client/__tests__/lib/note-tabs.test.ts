import { describe, it, expect } from "vitest";
import { initialNoteTab, tabForHash } from "@/lib/note-tabs";

describe("initialNoteTab", () => {
  it("opens the understanding tab right after a review", () => {
    expect(initialNoteTab("updated")).toBe("understanding");
  });

  it("opens the note tab otherwise", () => {
    expect(initialNoteTab(undefined)).toBe("note");
    expect(initialNoteTab("other")).toBe("note");
  });
});

describe("tabForHash", () => {
  it.each([
    ["#summary", "note"],
    ["#content", "note"],
    ["#revisions", "note"],
    ["#feedback", "understanding"],
    ["#aspect-map", "understanding"],
    ["#aspect-a1-2", "understanding"],
    ["#collection", "connections"],
    ["#links", "connections"],
  ])("maps %s to %s", (hash, tab) => {
    expect(tabForHash(hash)).toBe(tab);
  });

  it("decodes percent-encoded ids", () => {
    expect(tabForHash("#aspect-%E8%A6%B3%E7%82%B9")).toBe("understanding");
  });

  it.each(["", "#", "#unknown", "#%E0%A4%A", "#constructor", "#toString"])(
    "returns null for %j",
    (hash) => {
      expect(tabForHash(hash)).toBeNull();
    },
  );
});
