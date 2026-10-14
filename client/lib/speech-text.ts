import { mapOutsideCode, normalizeMathDelimiters } from "@/lib/chat-markdown";
import { latexToSpeech, SPOKEN_FORMULA } from "@/lib/latex-speech";

export const MAX_SPEECH_CHARS = 500;
export const FIRST_SENTENCE_MAX_CHARS = 25;
export const FIRST_SENTENCE_MIN_CHARS = 10;

const FENCE = "```";
const SENTENCE_END = /[。！？!?\n]/;
const HAS_WORD = /[\p{L}\p{N}]/u;
const TABLE_SEPARATOR_ROW = /^[ \t|:-]*\|[ \t|:-]*-[ \t|:-]*$/gm;
const TABLE_ROW = /^[ \t]*\|(.*)\|[ \t]*$/gm;
const DISPLAY_MATH = /(?<!\\)\$\$([\s\S]+?)(?<!\\)\$\$/g;
const INLINE_MATH = /(?<!\\)\$((?:\\\$|[^$\n])+?)(?<!\\)\$/g;
const ESCAPED_DOLLAR = /\\\$/g;
const PROSE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}、。]/u;
const UNSPLITTABLE_SPANS = [
  { open: "$$", close: "$$", inline: false },
  { open: "\\[", close: "\\]", inline: false },
  { open: "\\(", close: "\\)", inline: true },
  { open: "$", close: "$", inline: true },
  { open: "`", close: "`", inline: true },
] as const;

function readInlineFormula(source: string, tex: string): string {
  const reading = latexToSpeech(tex);
  return reading === SPOKEN_FORMULA && PROSE.test(tex) ? source : reading;
}

function readFormulas(markdown: string): string {
  return mapOutsideCode(markdown, (text) =>
    text
      .replace(DISPLAY_MATH, (_, tex: string) => ` ${latexToSpeech(tex)} `)
      .replace(INLINE_MATH, readInlineFormula)
      .replace(ESCAPED_DOLLAR, "$"),
  );
}

function findSentenceEnd(text: string): number {
  let span: (typeof UNSPLITTABLE_SPANS)[number] | null = null;
  for (let i = 0; i < text.length; i++) {
    if (text[i] === "\\" && text[i + 1] === "$") {
      i++;
      continue;
    }
    if (span) {
      if (text.startsWith(span.close, i)) {
        i += span.close.length - 1;
        span = null;
      } else if (span.inline && text[i] === "\n") {
        return i;
      }
      continue;
    }
    const opened = UNSPLITTABLE_SPANS.find((s) => text.startsWith(s.open, i));
    if (opened) {
      span = opened;
      i += opened.open.length - 1;
      continue;
    }
    if (SENTENCE_END.test(text[i])) return i;
  }
  return -1;
}

export function toSpeakableText(markdown: string): string {
  return readFormulas(
    normalizeMathDelimiters(markdown).replace(/```[\s\S]*?```/g, " "),
  )
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

function splitFirst(piece: string): string[] {
  if (piece.length <= FIRST_SENTENCE_MAX_CHARS) return [piece];
  const commas = [
    piece.indexOf("、", FIRST_SENTENCE_MIN_CHARS - 1),
    piece.indexOf(",", FIRST_SENTENCE_MIN_CHARS - 1),
  ].filter((i) => i !== -1);
  if (commas.length === 0) return [piece];
  const at = Math.min(...commas) + 1;
  return [piece.slice(0, at), piece.slice(at).trim()].filter(Boolean);
}

export class SentenceSplitter {
  private buffer = "";
  private inFence = false;
  private emitted = false;

  private emit(out: string[], pieces: string[]): void {
    for (const piece of pieces) {
      if (this.emitted) {
        out.push(piece);
        continue;
      }
      this.emitted = true;
      out.push(...splitFirst(piece));
    }
  }

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
      const end = findSentenceEnd(this.buffer);
      if (fence !== -1 && (end === -1 || fence < end)) {
        this.emit(out, speakable(this.buffer.slice(0, fence)));
        this.buffer = this.buffer.slice(fence + FENCE.length);
        this.inFence = true;
        continue;
      }
      if (end === -1) break;
      this.emit(out, speakable(this.buffer.slice(0, end + 1)));
      this.buffer = this.buffer.slice(end + 1);
    }
    return out;
  }

  flush(): string[] {
    const rest = this.inFence ? "" : this.buffer;
    this.buffer = "";
    this.inFence = false;
    const out: string[] = [];
    this.emit(out, speakable(rest));
    return out;
  }
}

export function splitIntoSentences(markdown: string): string[] {
  const splitter = new SentenceSplitter();
  return [...splitter.push(markdown), ...splitter.flush()];
}
