const IGNORED = /[\s、,|]/;

export interface FoundSentence {
  range: Range;
  end: number;
}

export function findSentenceRange(
  root: Node,
  sentence: string,
  from = 0,
): FoundSentence | null {
  const target = sentence
    .split("")
    .filter((ch) => !IGNORED.test(ch))
    .join("");
  if (!target) return null;

  const doc = root.ownerDocument ?? document;
  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const positions: { node: Text; offset: number }[] = [];
  let normalized = "";
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node as Text;
    for (let offset = 0; offset < text.data.length; offset++) {
      const ch = text.data[offset];
      if (IGNORED.test(ch)) continue;
      positions.push({ node: text, offset });
      normalized += ch;
    }
  }

  const at = normalized.indexOf(target, from);
  if (at === -1) return null;
  const start = positions[at];
  const last = positions[at + target.length - 1];
  const range = doc.createRange();
  range.setStart(start.node, start.offset);
  range.setEnd(last.node, last.offset + 1);
  return { range, end: at + target.length };
}
