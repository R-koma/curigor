const FENCE_LINE = /^```/gm;
const OPEN_MERMAID = /^```mermaid(?=[ \t]*(?:\n|$))/;
const INLINE_CODE = /`[^`\n]*`/g;
const MATH_BLOCK_LINE = /^[ \t]*\$\$[ \t]*$/gm;
const ONE_LINE_DISPLAY_MATH = /^[ \t]*\$\$(.+?)\$\$[ \t]*$/gm;

interface CloseOptions {
  streaming?: boolean;
}

interface Segment {
  text: string;
  code: boolean;
}

function splitFences(markdown: string): Segment[] {
  const segments: Segment[] = [];
  let buffer = "";
  let inFence = false;
  for (const line of markdown.split(/(?<=\n)/)) {
    const isFence = line.startsWith("```");
    if (isFence && !inFence) {
      if (buffer) segments.push({ text: buffer, code: false });
      buffer = line;
      inFence = true;
    } else if (isFence) {
      segments.push({ text: buffer + line, code: true });
      buffer = "";
      inFence = false;
    } else {
      buffer += line;
    }
  }
  if (buffer) segments.push({ text: buffer, code: inFence });
  return segments;
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

function segmentsOf(markdown: string): Segment[] {
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
 * フェンス数が奇数なら一時的に閉じフェンスを補い、コードブロックとして描画させる。
 */
export function closeOpenCodeFence(
  content: string,
  { streaming = false }: CloseOptions = {},
): string {
  const fences = [...content.matchAll(FENCE_LINE)];
  if (fences.length % 2 === 0) return content;
  const open = fences[fences.length - 1].index;
  const rest = streaming
    ? content.slice(open).replace(OPEN_MERMAID, "```mermaid-pending")
    : content.slice(open);
  return `${content.slice(0, open)}${rest}\n\`\`\``;
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
