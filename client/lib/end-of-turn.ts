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
  /(や|とか|を|に|へ|が|て|で|(?<![こっ])と|は|から|けど|けれど|ので|のに|し|ば|たり|えー+|えっと|あの[ー〜]*|その[ー〜]*|まあ|うーん|まず|つまり|要するに|ただ|あと|それで|そして|それから|特に)。$/;

const CONTINUATION_HEAD =
  /^(?:を|の(?!ち)|が(?![、，])|に|へ|より|まで|など|なんか|って|とか|とい[うっ]|と(?:呼|言|思|考|して|した))/;

function closeSegment(text: string, next: string): string {
  if (CONTINUATION_HEAD.test(next)) return text.replace(/。$/, "");
  return text.replace(MID_SENTENCE_PERIOD, "$1、");
}

const FILLER =
  /(?<=^|[、。，．\s])(?:(?:えーと|えーっと|えっと|えと|えー+|うーん+|うー+ん+|んー+|あー+|(?:あの|その|まあ|なんか)ー+|(?:あの|その|まあ|なんか)(?=[、，]))[、，\s]*)/g;

export function removeFillers(text: string): string {
  return text
    .replace(FILLER, "")
    .replace(/、{2,}/g, "、")
    .replace(/、。/g, "。")
    .replace(/^[、。\s]+/, "")
    .trim();
}

export function closeSegments(
  segments: TranscriptSegment[],
): TranscriptSegment[] {
  let next: string | null = null;
  return segments
    .toReversed()
    .map((segment) => {
      if (segment.status !== "done") return segment;
      const text = segment.text.trim();
      const closed = next === null ? text : closeSegment(text, next);
      next = text;
      return { ...segment, text: removeFillers(closed) };
    })
    .toReversed()
    .filter((segment) => segment.status !== "done" || segment.text !== "");
}

export function joinSegments(segments: TranscriptSegment[]): string {
  return closeSegments(segments)
    .filter((segment) => segment.status === "done")
    .map((segment) => segment.text)
    .join("");
}

export function rawTranscriptOf(segments: TranscriptSegment[]): string {
  return stripEndWord(
    segments
      .filter((segment) => segment.status === "done")
      .map((segment) => segment.text.trim())
      .join(""),
  );
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
