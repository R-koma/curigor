import { describe, expect, it } from "vitest";
import { findSentenceRange } from "@/lib/speech-highlight";

function container(html: string): HTMLElement {
  const root = document.createElement("div");
  root.innerHTML = html;
  return root;
}

describe("findSentenceRange", () => {
  it("finds a sentence across Markdown elements", () => {
    const root = container(
      "<p>二分探索は<strong>半分</strong>に絞ります。</p><p>次です。</p>",
    );

    const found = findSentenceRange(root, "二分探索は半分に絞ります。");

    expect(found?.range.toString()).toBe("二分探索は半分に絞ります。");
  });

  it("ignores whitespace, commas and table pipes", () => {
    const root = container(
      "<table><tr><td>用語</td><td>意味</td></tr></table><p>a  b</p>",
    );

    expect(findSentenceRange(root, "用語、意味")?.range.toString()).toBe(
      "用語意味",
    );
    expect(findSentenceRange(root, "a b")).not.toBeNull();
  });

  it("finds the next occurrence after the given position", () => {
    const root = container("<p>はい。</p><p>次へ。</p><p>はい。</p>");
    const first = findSentenceRange(root, "はい。");

    const second = findSentenceRange(root, "はい。", first?.end);

    expect(second).not.toBeNull();
    expect(second?.range.startContainer).not.toBe(first?.range.startContainer);
  });

  it("returns null when the sentence is not there", () => {
    expect(
      findSentenceRange(container("<p>別の文。</p>"), "無い文。"),
    ).toBeNull();
    expect(findSentenceRange(container("<p>文。</p>"), "  、 ")).toBeNull();
  });
});
