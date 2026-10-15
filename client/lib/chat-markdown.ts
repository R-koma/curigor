const FENCE_OPEN = /^[ \t]*(`{3,}|~{3,})/;
const FENCE_CLOSE = /^[ \t]*(`{3,}|~{3,})[ \t]*\n?$/;
const INLINE_CODE = /`[^`\n]*`/g;
const MATH_BLOCK_LINE = /^[ \t]*\$\$[ \t]*$/gm;
const ONE_LINE_DISPLAY_MATH = /^[ \t]*\$\$(.+?)\$\$[ \t]*$/gm;

interface CloseOptions {
  streaming?: boolean;
}

export interface Segment {
  text: string;
  code: boolean;
}

export interface OpenFence {
  index: number;
  marker: string;
}

function closes(line: string, marker: string): boolean {
  const close = FENCE_CLOSE.exec(line)?.[1];
  return (
    close !== undefined &&
    close[0] === marker[0] &&
    close.length >= marker.length
  );
}

function scanFences(markdown: string): {
  segments: Segment[];
  open: OpenFence | null;
} {
  const segments: Segment[] = [];
  let buffer = "";
  let open: OpenFence | null = null;
  let offset = 0;
  for (const line of markdown.split(/(?<=\n)/)) {
    if (open) {
      buffer += line;
      if (closes(line, open.marker)) {
        segments.push({ text: buffer, code: true });
        buffer = "";
        open = null;
      }
    } else {
      const marker = FENCE_OPEN.exec(line)?.[1];
      if (marker) {
        if (buffer) segments.push({ text: buffer, code: false });
        buffer = line;
        open = { index: offset, marker };
      } else {
        buffer += line;
      }
    }
    offset += line.length;
  }
  if (buffer) segments.push({ text: buffer, code: open !== null });
  return { segments, open };
}

function splitFences(markdown: string): Segment[] {
  return scanFences(markdown).segments;
}

export function findOpenFence(markdown: string): OpenFence | null {
  return scanFences(markdown).open;
}

function splitInlineCode(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE_CODE)) {
    if (match.index > last) {
      segments.push({ text: text.slice(last, match.index), code: false });
    }
    segments.push({ text: match[0], code: true });
    last = match.index + match[0].length;
  }
  if (last < text.length)
    segments.push({ text: text.slice(last), code: false });
  return segments;
}

export function segmentsOf(markdown: string): Segment[] {
  return splitFences(markdown).flatMap((segment) =>
    segment.code ? [segment] : splitInlineCode(segment.text),
  );
}

export function mapOutsideCode(
  markdown: string,
  transform: (text: string) => string,
): string {
  return segmentsOf(markdown)
    .map((segment) => (segment.code ? segment.text : transform(segment.text)))
    .join("");
}

export function normalizeMathDelimiters(markdown: string): string {
  return mapOutsideCode(markdown, (text) =>
    text
      .replace(
        /\\\[([\s\S]+?)\\\]/g,
        (_, tex: string) => `\n$$\n${tex.trim()}\n$$\n`,
      )
      .replace(/\\\(([\s\S]+?)\\\)/g, (_, tex: string) => `$${tex.trim()}$`)
      .replace(
        ONE_LINE_DISPLAY_MATH,
        (_, tex: string) => `$$\n${tex.trim()}\n$$`,
      ),
  );
}

/**
 * ストリーミング中の未閉じコードフェンスを閉じる。
 *
 * LLM 応答は 1 文字ずつ届くため、``` 開始だけ到着して閉じ ``` が未着の状態が必ず発生する。
 * このとき Markdown はフェンス以降を生テキストとして描画してしまい表示が崩れるため、
 * 閉じていないフェンスがあれば同じ記号で一時的に閉じ、コードブロックとして描画させる。
 */
export function closeOpenCodeFence(
  content: string,
  { streaming = false }: CloseOptions = {},
): string {
  const open = findOpenFence(content);
  if (!open) return content;
  const rest = content.slice(open.index);
  const marked = streaming
    ? rest.replace(
        /^([ \t]*[`~]+)mermaid(?=[ \t]*(?:\n|$))/,
        "$1mermaid-pending",
      )
    : rest;
  return `${content.slice(0, open.index)}${marked}\n${open.marker}`;
}

export function closeOpenMathBlock(content: string): string {
  const count = segmentsOf(content)
    .filter((segment) => !segment.code)
    .reduce(
      (total, segment) =>
        total + (segment.text.match(MATH_BLOCK_LINE)?.length ?? 0),
      0,
    );
  return count % 2 === 1 ? `${content}\n$$` : content;
}

export function closeOpenBlocks(
  content: string,
  options: CloseOptions = {},
): string {
  return closeOpenMathBlock(
    closeOpenCodeFence(normalizeMathDelimiters(content), options),
  );
}
