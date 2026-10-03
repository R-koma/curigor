export const MAX_SPEECH_CHARS = 500;

const FENCE = "```";
const SENTENCE_END = /[。！？!?\n]/;
const HAS_WORD = /[\p{L}\p{N}]/u;
const TABLE_SEPARATOR_ROW = /^[ \t|:-]*\|[ \t|:-]*-[ \t|:-]*$/gm;
const TABLE_ROW = /^[ \t]*\|(.*)\|[ \t]*$/gm;

export function toSpeakableText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " ")
    .replace(TABLE_SEPARATOR_ROW, "")
    .replace(TABLE_ROW, (_, cells: string) =>
      cells
        .split("|")
        .map((cell) => cell.trim())
        .filter(Boolean)
        .join("、"),
    )
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/`/g, "")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/^\s*([-*+]|\d+\.)\s+/gm, "")
    .replace(/^\s*([-*_]\s*){3,}$/gm, "")
    .replace(/\*\*|~~|\*/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function splitLong(text: string): string[] {
  const pieces: string[] = [];
  let rest = text;
  while (rest.length > MAX_SPEECH_CHARS) {
    const window = rest.slice(0, MAX_SPEECH_CHARS);
    const cut = Math.max(
      window.lastIndexOf("、"),
      window.lastIndexOf(","),
      window.lastIndexOf(" "),
    );
    const at = cut > 0 ? cut + 1 : MAX_SPEECH_CHARS;
    const piece = rest.slice(0, at).trim();
    if (piece) pieces.push(piece);
    rest = rest.slice(at);
  }
  if (rest.trim()) pieces.push(rest.trim());
  return pieces;
}

function speakable(text: string): string[] {
  const spoken = toSpeakableText(text);
  if (!HAS_WORD.test(spoken)) return [];
  return splitLong(spoken).filter((piece) => HAS_WORD.test(piece));
}

export class SentenceSplitter {
  private buffer = "";
  private inFence = false;

  push(chunk: string): string[] {
    this.buffer += chunk;
    const out: string[] = [];
    for (;;) {
      if (this.inFence) {
        const close = this.buffer.indexOf(FENCE);
        if (close === -1) {
          this.buffer = this.buffer.slice(-(FENCE.length - 1));
          break;
        }
        this.buffer = this.buffer.slice(close + FENCE.length);
        this.inFence = false;
        continue;
      }
      const fence = this.buffer.indexOf(FENCE);
      const end = this.buffer.search(SENTENCE_END);
      if (fence !== -1 && (end === -1 || fence < end)) {
        out.push(...speakable(this.buffer.slice(0, fence)));
        this.buffer = this.buffer.slice(fence + FENCE.length);
        this.inFence = true;
        continue;
      }
      if (end === -1) break;
      out.push(...speakable(this.buffer.slice(0, end + 1)));
      this.buffer = this.buffer.slice(end + 1);
    }
    return out;
  }

  flush(): string[] {
    const rest = this.inFence ? "" : this.buffer;
    this.buffer = "";
    this.inFence = false;
    return speakable(rest);
  }
}

export function splitIntoSentences(markdown: string): string[] {
  const splitter = new SentenceSplitter();
  return [...splitter.push(markdown), ...splitter.flush()];
}
