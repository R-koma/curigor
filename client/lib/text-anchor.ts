import { MAX_SIDE_QUOTE_LENGTH } from "@/lib/side-questions";

const EXCLUDED = "pre, .katex, svg, [data-diagram]";
const BLOCKS = "p, li, h1, h2, h3, h4, h5, h6, td, th, blockquote";

interface Segment {
  node: Text;
  start: number;
}

interface Flattened {
  text: string;
  segments: Segment[];
}

function elementOf(node: Node): Element | null {
  return node.nodeType === Node.ELEMENT_NODE
    ? (node as Element)
    : node.parentElement;
}

function isExcluded(node: Node, root: HTMLElement): boolean {
  const excluded = elementOf(node)?.closest(EXCLUDED);
  return !!excluded && root.contains(excluded);
}

function flatten(root: HTMLElement): Flattened {
  const walker = root.ownerDocument.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
  );
  const segments: Segment[] = [];
  let text = "";
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    if (isExcluded(node, root)) continue;
    segments.push({ node, start: text.length });
    text += node.data;
  }
  return { text, segments };
}

function countBefore(text: string, quote: string, before: number): number {
  let count = 0;
  let at = text.indexOf(quote);
  while (at !== -1 && at < before) {
    count += 1;
    at = text.indexOf(quote, at + 1);
  }
  return count;
}

function blockOf(node: Node, root: HTMLElement): Element | null {
  const block = elementOf(node)?.closest(BLOCKS);
  return block && root.contains(block) ? block : null;
}

export function anchorFromRange(
  root: HTMLElement,
  range: Range,
): { quote: string; occurrence: number } | null {
  if (
    !root.contains(range.startContainer) ||
    !root.contains(range.endContainer)
  ) {
    return null;
  }
  if (
    isExcluded(range.startContainer, root) ||
    isExcluded(range.endContainer, root)
  ) {
    return null;
  }
  const block = blockOf(range.startContainer, root);
  if (!block || block !== blockOf(range.endContainer, root)) return null;

  const { text, segments } = flatten(root);
  let start: number | null = null;
  let end: number | null = null;
  for (const { node, start: offset } of segments) {
    if (!range.intersectsNode(node)) continue;
    const from =
      node === range.startContainer ? offset + range.startOffset : offset;
    const to =
      node === range.endContainer
        ? offset + range.endOffset
        : offset + node.length;
    start ??= from;
    end = to;
  }
  if (start === null || end === null || end <= start) return null;

  const raw = text.slice(start, end);
  const leading = raw.length - raw.trimStart().length;
  const quote = raw.trim();
  if (!quote || quote.length > MAX_SIDE_QUOTE_LENGTH) return null;
  return { quote, occurrence: countBefore(text, quote, start + leading) };
}

function pointAt(
  segments: Segment[],
  index: number,
  atEnd: boolean,
): { node: Text; offset: number } | null {
  for (const { node, start } of segments) {
    const end = start + node.length;
    if (atEnd ? index > start && index <= end : index >= start && index < end) {
      return { node, offset: index - start };
    }
  }
  return null;
}

export function rangeFromAnchor(
  root: HTMLElement,
  quote: string,
  occurrence: number,
): Range | null {
  if (!quote) return null;
  const { text, segments } = flatten(root);
  let at = text.indexOf(quote);
  for (let i = 0; i < occurrence && at !== -1; i += 1) {
    at = text.indexOf(quote, at + 1);
  }
  if (at === -1) return null;
  const start = pointAt(segments, at, false);
  const end = pointAt(segments, at + quote.length, true);
  if (!start || !end) return null;
  const range = root.ownerDocument.createRange();
  range.setStart(start.node, start.offset);
  range.setEnd(end.node, end.offset);
  return range;
}
