import { describe, expect, it } from "vitest";
import {
  childrenOf,
  closeWithDescendants,
  mergeLoaded,
  openOnly,
  pathTo,
  topLevelInOrder,
} from "@/lib/side-question-tree";
import type { SideQuestion } from "@/lib/side-questions";

function thread(
  id: string,
  overrides: Partial<SideQuestion> = {},
): SideQuestion {
  return {
    id,
    parentId: null,
    anchorMessageId: "m1",
    anchorSideMessageId: null,
    quote: id,
    occurrence: 0,
    depth: 0,
    messages: [],
    ...overrides,
  };
}

const parent = thread("p");
const child = thread("c", {
  parentId: "p",
  anchorMessageId: null,
  anchorSideMessageId: "pa1",
  depth: 1,
});
const grandchild = thread("g", {
  parentId: "c",
  anchorMessageId: null,
  anchorSideMessageId: "ca1",
  depth: 2,
});
const sibling = thread("s", {
  parentId: "p",
  anchorMessageId: null,
  anchorSideMessageId: "pa2",
  depth: 1,
});
const all = [parent, child, grandchild, sibling];

describe("side question tree", () => {
  it("pathTo lists the thread and its ancestors", () => {
    expect(pathTo(all, "g")).toEqual(["g", "c", "p"]);
  });

  it("openOnly keeps ancestors open", () => {
    expect(openOnly(all, "g")).toEqual(new Set(["g", "c", "p"]));
  });

  it("closeWithDescendants closes children too", () => {
    const open = new Set(["p", "c", "g"]);
    expect(closeWithDescendants(all, open, "c")).toEqual(new Set(["p"]));
    expect(closeWithDescendants(all, open, "p")).toEqual(new Set());
  });

  it("topLevelInOrder sorts by message then occurrence", () => {
    const later = thread("later", { anchorMessageId: "m2" });
    const second = thread("second", { occurrence: 1 });
    const first = thread("first", { occurrence: 0 });
    const gone = thread("gone", { anchorMessageId: "missing" });

    expect(
      topLevelInOrder([gone, later, second, child, first], ["m1", "m2"]).map(
        (t) => t.id,
      ),
    ).toEqual(["first", "second", "later", "gone"]);
  });

  it("topLevelInOrder prefers the position in the text when known", () => {
    const a = thread("a", { quote: "後ろ" });
    const b = thread("b", { quote: "前" });
    const positions: Record<string, number> = { a: 40, b: 3 };

    expect(
      topLevelInOrder([a, b], ["m1"], (t) => positions[t.id]).map((t) => t.id),
    ).toEqual(["b", "a"]);
  });

  it("childrenOf filters by answer message", () => {
    expect(childrenOf(all, "p").map((t) => t.id)).toEqual(["c", "s"]);
    expect(childrenOf(all, "p", "pa2").map((t) => t.id)).toEqual(["s"]);
  });
});

describe("mergeLoaded", () => {
  const message = (id: string) => ({
    id,
    role: "user" as const,
    content: id,
  });

  it("keeps a thread created while the list was loading", () => {
    const merged = mergeLoaded([thread("new")], [thread("old")]);

    expect(merged.map((t) => t.id)).toEqual(["old", "new"]);
  });

  it("prefers the copy with more messages", () => {
    const local = thread("a", { messages: [message("u1"), message("a1")] });
    const stale = thread("a", { messages: [message("u1")] });

    expect(mergeLoaded([local], [stale])[0].messages).toHaveLength(2);
    expect(mergeLoaded([stale], [local])[0].messages).toHaveLength(2);
  });
});
