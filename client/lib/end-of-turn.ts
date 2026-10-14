import type { TranscriptSegment } from "@/lib/stt/types";

export const END_WORD = "以上";
const END_WORD_VARIANTS = [END_WORD];
const RESUME_WORDS = ["続けて", "続けてください", "続けて下さい"];
const PUNCTUATION = "\\s。、．，.,!！?？「」『』";
const IGNORED = new RegExp(`[${PUNCTUATION}]`, "g");
const TRAILING = new RegExp(
  `[${PUNCTUATION}]*(?:${END_WORD_VARIANTS.join("|")})[${PUNCTUATION}]*$`,
);

function endsWithAny(text: string, words: string[]): boolean {
  const normalized = text.replace(IGNORED, "");
  return words.some((word) => normalized.endsWith(word));
}

export function endsTurn(text: string): boolean {
  return endsWithAny(text, END_WORD_VARIANTS);
}

export function stripEndWord(text: string): string {
  return text.replace(TRAILING, "").trim();
}

const MID_SENTENCE_PERIOD =
  /(や|とか|を|に|へ|が|(?<![んい])で|(?<![こっ])と|は|から|けど|けれど|ので|のに|し|ば|たり)。$/;

export function joinSegments(segments: TranscriptSegment[]): string {
  const texts = segments
    .filter((segment) => segment.status === "done")
    .map((segment) => segment.text.trimEnd());
  return texts
    .map((text, index) =>
      index < texts.length - 1
        ? text.replace(MID_SENTENCE_PERIOD, "$1、")
        : text,
    )
    .join("");
}

function lastSettledText(segments: TranscriptSegment[]): string | null {
  const last = segments.at(-1);
  if (!last || last.status !== "done") return null;
  if (segments.some((segment) => segment.status === "pending")) return null;
  return last.text;
}

export function turnIsComplete(segments: TranscriptSegment[]): boolean {
  const text = lastSettledText(segments);
  return text !== null && endsTurn(text);
}

export function asksToResume(segments: TranscriptSegment[]): boolean {
  const text = lastSettledText(segments);
  return text !== null && endsWithAny(text, RESUME_WORDS);
}

export function contentLength(segments: TranscriptSegment[]): number {
  return joinSegments(segments).replace(IGNORED, "").length;
}
