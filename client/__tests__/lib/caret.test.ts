import { afterEach, describe, expect, it } from "vitest";
import { CARET_SKIP_ATTR, caretPointAt, textOffsetWithin } from "@/lib/caret";

function build(html: string): HTMLElement {
  const root = document.createElement("div");
  root.innerHTML = html;
  document.body.append(root);
  return root;
}

describe("textOffsetWithin", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("counts the characters before the point across spans", () => {
    const root = build("<span>二分探索は</span><span>半分に</span>");
    const second = root.children[1].firstChild!;
    expect(textOffsetWithin(root, second, 2)).toBe(7);
  });

  it("skips the placeholder text", () => {
    const root = build(
      `<span>二分探索は</span><span ${CARET_SKIP_ATTR}>（聞き取れませんでした）</span><span>半分に</span>`,
    );
    expect(textOffsetWithin(root, root.children[2].firstChild!, 1)).toBe(6);
    expect(textOffsetWithin(root, root.children[1].firstChild!, 3)).toBe(5);
  });

  it("accepts an element node with a child index", () => {
    const root = build("<span>二分探索は</span><span>半分に</span>");
    expect(textOffsetWithin(root, root, 1)).toBe(5);
  });

  it("returns null outside the root", () => {
    const root = build("<span>二分探索は</span>");
    expect(textOffsetWithin(root, document.body, 0)).toBeNull();
  });
});

describe("caretPointAt", () => {
  afterEach(() => {
    Reflect.deleteProperty(document, "caretPositionFromPoint");
    Reflect.deleteProperty(document, "caretRangeFromPoint");
  });

  function stub(name: string, value: unknown) {
    Object.defineProperty(document, name, { configurable: true, value });
  }

  it("prefers caretPositionFromPoint", () => {
    const node = document.createTextNode("二分");
    stub("caretPositionFromPoint", () => ({ offsetNode: node, offset: 1 }));
    stub("caretRangeFromPoint", () => {
      throw new Error("not used");
    });
    expect(caretPointAt(1, 2)).toEqual({ node, offset: 1 });
  });

  it("falls back to caretRangeFromPoint", () => {
    const node = document.createTextNode("二分");
    stub("caretRangeFromPoint", () => ({
      startContainer: node,
      startOffset: 2,
    }));
    expect(caretPointAt(1, 2)).toEqual({ node, offset: 2 });
  });

  it("returns null when neither exists", () => {
    expect(caretPointAt(1, 2)).toBeNull();
  });
});
