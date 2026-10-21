export const CARET_SKIP_ATTR = "data-caret-skip";

export interface CaretPoint {
  node: Node;
  offset: number;
}

type CaretDocument = Document & {
  caretPositionFromPoint?: (
    x: number,
    y: number,
  ) => { offsetNode: Node; offset: number } | null;
  caretRangeFromPoint?: (x: number, y: number) => Range | null;
};

export function caretPointAt(x: number, y: number): CaretPoint | null {
  const doc = document as CaretDocument;
  if (typeof doc.caretPositionFromPoint === "function") {
    const position = doc.caretPositionFromPoint(x, y);
    return position
      ? { node: position.offsetNode, offset: position.offset }
      : null;
  }
  if (typeof doc.caretRangeFromPoint === "function") {
    const range = doc.caretRangeFromPoint(x, y);
    return range
      ? { node: range.startContainer, offset: range.startOffset }
      : null;
  }
  return null;
}

export function textOffsetWithin(
  root: Node,
  node: Node,
  offset: number,
): number | null {
  if (!root.contains(node)) return null;
  const range = document.createRange();
  range.setStart(root, 0);
  range.setEnd(node, offset);
  const fragment = range.cloneContents();
  for (const skipped of fragment.querySelectorAll(`[${CARET_SKIP_ATTR}]`)) {
    skipped.remove();
  }
  return fragment.textContent?.length ?? 0;
}
