import type { TranscriptSegment } from "@/lib/stt/types";

export const END_WORD = "以上";
const END_WORD_VARIANTS = [END_WORD];
const PUNCTUATION = "\\s。、．，.,!！?？「」『』";
const IGNORED = new RegExp(`[${PUNCTUATION}]`, "g");
const TRAILING = new RegExp(
  `[${PUNCTUATION}]*(?:${END_WORD_VARIANTS.join("|")})[${PUNCTUATION}]*$`,
);

export function endsTurn(text: string): boolean {
  const normalized = text.replace(IGNORED, "");
  return END_WORD_VARIANTS.some((word) => normalized.endsWith(word));
}

export function stripEndWord(text: string): string {
  return text.replace(TRAILING, "").trim();
}

export function joinSegments(segments: TranscriptSegment[]): string {
  return segments
    .filter((segment) => segment.status === "done")
    .map((segment) => segment.text)
    .join("");
}

export function turnIsComplete(segments: TranscriptSegment[]): boolean {
  const last = segments.at(-1);
  if (!last || last.status !== "done") return false;
  if (segments.some((segment) => segment.status === "pending")) return false;
  return endsTurn(last.text);
}
