import { segmentsOf } from "@/lib/chat-markdown";

export interface TextSelection {
  start: number;
  end: number;
}

export interface TextEdit {
  start: number;
  end: number;
  text: string;
}

export interface MathSpan {
  start: number;
  end: number;
  latex: string;
}

const INLINE_MATH = /(?<![\\$])\$([^$\n]+?)(?<!\\)\$(?!\$)/g;
const RICH_MATH = /\$\$|\\\(|\\\[|(?<!\\)\$[^$\n]+?(?<!\\)\$/;
const FENCE_LINE = /^```/gm;

const isBoundary = (char: string | undefined) =>
  char === undefined || /\s/.test(char);

export function applyEdit(value: string, edit: TextEdit): string {
  return value.slice(0, edit.start) + edit.text + value.slice(edit.end);
}

export function insertMath(
  value: string,
  selection: TextSelection,
  latex: string,
): TextEdit {
  const before = isBoundary(value[selection.start - 1]) ? "" : " ";
  const after = isBoundary(value[selection.end]) ? "" : " ";
  return { ...selection, text: `${before}$${latex}$${after}` };
}

export function replaceMath(span: MathSpan, latex: string): TextEdit {
  return { start: span.start, end: span.end, text: `$${latex}$` };
}

export function insertCodeBlock(
  value: string,
  selection: TextSelection,
  code: string,
  fence: string,
): TextEdit {
  const before =
    selection.start === 0 || value[selection.start - 1] === "\n" ? "" : "\n";
  const after = value[selection.end] === "\n" ? "" : "\n";
  const body = code.replace(/\n+$/, "");
  return {
    ...selection,
    text: `${before}\`\`\`${fence}\n${body}\n\`\`\`${after}`,
  };
}

export function findMathAt(value: string, cursor: number): MathSpan | null {
  let offset = 0;
  for (const segment of segmentsOf(value)) {
    if (!segment.code) {
      for (const match of segment.text.matchAll(INLINE_MATH)) {
        const start = offset + match.index;
        const end = start + match[0].length;
        if (start < cursor && cursor < end) {
          return { start, end, latex: match[1] };
        }
      }
    }
    offset += segment.text.length;
  }
  return null;
}

export function hasRichContent(value: string): boolean {
  if (/^```/m.test(value)) return true;
  return segmentsOf(value).some(
    (segment) => !segment.code && RICH_MATH.test(segment.text),
  );
}

export function isInsideFence(value: string, cursor: number): boolean {
  return (value.slice(0, cursor).match(FENCE_LINE)?.length ?? 0) % 2 === 1;
}
