import { describe, expect, it } from "vitest";
import { anchorFromRange, rangeFromAnchor } from "@/lib/text-anchor";

function mount(html: string): HTMLElement {
  const root = document.createElement("div");
  root.innerHTML = html;
  document.body.replaceChildren(root);
  return root;
}

function textNodes(root: Node): Text[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  return nodes;
}

function rangeOver(
  start: Text,
  startOffset: number,
  end: Text,
  endOffset: number,
): Range {
  const range = document.createRange();
  range.setStart(start, startOffset);
  range.setEnd(end, endOffset);
  return range;
}

function rangeOfText(node: Text, text: string, from = 0): Range {
  const at = node.data.indexOf(text, from);
  return rangeOver(node, at, node, at + text.length);
}

describe("anchorFromRange", () => {
  it("returns quote and occurrence 0 for the first match", () => {
    const root = mount("<p>索引を使うと速く探せる</p>");
    const [text] = textNodes(root);

    expect(anchorFromRange(root, rangeOfText(text, "索引"))).toEqual({
      quote: "索引",
      occurrence: 0,
    });
  });

  it('counts earlier matches: second "索引" has occurrence 1', () => {
    const root = mount(
      "<p>索引はデータの位置を指す。</p><p>本の索引と同じで、索引を引けば速い。</p>",
    );
    const [, second] = textNodes(root);
    const range = rangeOfText(second, "索引", second.data.indexOf("索引") + 1);

    const anchor = anchorFromRange(root, range);

    expect(anchor).toEqual({ quote: "索引", occurrence: 2 });
    const restored = rangeFromAnchor(root, anchor!.quote, anchor!.occurrence);
    expect(restored?.startContainer).toBe(range.startContainer);
    expect(restored?.startOffset).toBe(range.startOffset);
    expect(restored?.toString()).toBe("索引");
  });

  it("selection across <strong> and <code> inside one paragraph round-trips", () => {
    const root = mount(
      "<p>まず <strong>B木</strong> を作り、<code>CREATE INDEX</code> で登録する</p><p>B木 を作り</p>",
    );
    const nodes = textNodes(root);
    const first = nodes[0];
    const codeText = nodes[3];
    const range = rangeOver(first, 3, codeText, 6);

    const anchor = anchorFromRange(root, range);

    expect(anchor).toEqual({ quote: "B木 を作り、CREATE", occurrence: 0 });
    const restored = rangeFromAnchor(root, anchor!.quote, anchor!.occurrence);
    expect(restored?.toString()).toBe("B木 を作り、CREATE");
    expect(restored?.startContainer).toBe(nodes[1]);
    expect(restored?.endContainer).toBe(codeText);
  });

  it("trims surrounding whitespace", () => {
    const root = mount("<p>索引 と 表</p>");
    const [text] = textNodes(root);

    expect(anchorFromRange(root, rangeOver(text, 2, text, 5))).toEqual({
      quote: "と",
      occurrence: 0,
    });
  });

  it("returns null across two paragraphs", () => {
    const root = mount("<p>索引</p><p>表</p>");
    const [a, b] = textNodes(root);

    expect(anchorFromRange(root, rangeOver(a, 0, b, 1))).toBeNull();
  });

  it("returns null inside <pre>", () => {
    const root = mount("<p>前</p><pre><code>SELECT 1</code></pre>");
    const [, code] = textNodes(root);

    expect(anchorFromRange(root, rangeOfText(code, "SELECT"))).toBeNull();
  });

  it("returns null inside .katex", () => {
    const root = mount('<p>式 <span class="katex">x+1</span> を見る</p>');
    const [, math] = textNodes(root);

    expect(anchorFromRange(root, rangeOfText(math, "x+1"))).toBeNull();
  });

  it("returns null inside a diagram", () => {
    const root = mount(
      '<div data-diagram=""><p>図を表示できませんでした</p></div>',
    );
    const [text] = textNodes(root);

    expect(anchorFromRange(root, rangeOfText(text, "図"))).toBeNull();
  });

  it("returns null over 300 chars", () => {
    const root = mount(`<p>${"あ".repeat(301)}</p>`);
    const [text] = textNodes(root);

    expect(anchorFromRange(root, rangeOver(text, 0, text, 301))).toBeNull();
    expect(anchorFromRange(root, rangeOver(text, 0, text, 300))).not.toBeNull();
  });

  it("returns null for whitespace only", () => {
    const root = mount("<p>索引   表</p>");
    const [text] = textNodes(root);

    expect(anchorFromRange(root, rangeOver(text, 2, text, 5))).toBeNull();
  });

  it("returns null outside the root", () => {
    const root = mount("<p>索引</p>");
    const outside = document.createElement("p");
    outside.textContent = "索引";
    document.body.append(outside);

    expect(
      anchorFromRange(root, rangeOfText(outside.firstChild as Text, "索引")),
    ).toBeNull();
  });

  it("does not count text inside code blocks", () => {
    const root = mount("<pre>索引</pre><p>索引です</p>");
    const [, text] = textNodes(root);

    expect(anchorFromRange(root, rangeOfText(text, "索引"))).toEqual({
      quote: "索引",
      occurrence: 0,
    });
  });
});

describe("rangeFromAnchor", () => {
  it("rangeFromAnchor returns null when the text is gone", () => {
    const root = mount("<p>索引</p>");

    expect(rangeFromAnchor(root, "B木", 0)).toBeNull();
    expect(rangeFromAnchor(root, "索引", 1)).toBeNull();
  });
});
