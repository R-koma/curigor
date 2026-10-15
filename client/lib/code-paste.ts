import { common, createLowlight } from "lowlight";
import { CODE_LANGUAGES, fenceForVscodeMode } from "@/lib/code-languages";
import {
  insertCodeBlock,
  isInsideFence,
  type TextEdit,
  type TextSelection,
} from "@/lib/compose-insert";

type LineKind = "code" | "prose" | "plain" | "neutral";

const lowlight = createLowlight(common);
const SUBSET = CODE_LANGUAGES.map((language) => language.highlight);
const MIN_RELEVANCE = 3;
const MIN_CODE_RATIO = 0.6;
const MAX_PROSE_RATIO = 0.3;
const MIN_JAPANESE_RATIO = 0.5;

const LATEX = /^\s*\\[a-zA-Z]|\\\\\s*$/;
const MARKDOWN = /^\s*([-*+]\s|\d+\.\s|>\s?|\|.*\|\s*$)/;
const COMMENT = /^\s*(#(?!include|define)|\/\/|--|\/\*|\*)/;
const INDENTED = /^(\t| {2,})\S/;
const KEYWORD =
  /^\s*(def|class|import|from|function|const|let|var|return|if|elif|else|for|while|public|private|protected|static|void|int|fn|func|package|#include|#define|SELECT|FROM|WHERE|JOIN|ORDER BY|GROUP BY|INSERT|UPDATE|DELETE|CREATE|npm|npx|pip|git|cd|ls|echo|sudo)(?=[\s(:]|$)/;
const SHELL_PROMPT = /^\s*\$ \S/;
const ASSIGNMENT = /[\w\])]\s*(=|\+=|-=|==|=>|:=)\s*\S/;
const CODE_ENDING = /[;{}:)]\s*$/;
const JAPANESE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/gu;

function japaneseRatio(line: string): number {
  const chars = line.replace(/\s/g, "");
  return (chars.match(JAPANESE)?.length ?? 0) / chars.length;
}

function classify(line: string): LineKind {
  if (LATEX.test(line) || MARKDOWN.test(line)) return "prose";
  if (COMMENT.test(line)) return "neutral";
  if (
    INDENTED.test(line) ||
    KEYWORD.test(line) ||
    SHELL_PROMPT.test(line) ||
    ASSIGNMENT.test(line)
  ) {
    return "code";
  }
  if (japaneseRatio(line) > MIN_JAPANESE_RATIO) return "prose";
  return CODE_ENDING.test(line) ? "code" : "plain";
}

export function looksLikeCode(text: string): boolean {
  const kinds = text
    .split("\n")
    .filter((line) => line.trim())
    .map(classify)
    .filter((kind) => kind !== "neutral");
  if (kinds.length < 2) return false;
  const count = (kind: LineKind) => kinds.filter((k) => k === kind).length;
  return (
    count("code") >= 2 &&
    count("code") / kinds.length >= MIN_CODE_RATIO &&
    count("prose") / kinds.length < MAX_PROSE_RATIO
  );
}

export function guessFence(text: string): string {
  const { language, relevance = 0 } =
    lowlight.highlightAuto(text, { subset: SUBSET }).data ?? {};
  if (!language || relevance < MIN_RELEVANCE) return "";
  return (
    CODE_LANGUAGES.find((candidate) => candidate.highlight === language)
      ?.fence ?? ""
  );
}

function vscodeFence(data: string): string | null {
  if (!data) return null;
  try {
    const mode: unknown = JSON.parse(data)?.mode;
    return typeof mode === "string" ? fenceForVscodeMode(mode) : null;
  } catch {
    return null;
  }
}

export function codePasteEdit(
  value: string,
  selection: TextSelection,
  text: string,
  vscodeData: string,
): TextEdit | null {
  if (!text.trim().includes("\n") || text.includes("```")) return null;
  if (isInsideFence(value, selection.start)) return null;
  const editorFence = vscodeFence(vscodeData);
  if (editorFence === null && !looksLikeCode(text)) return null;
  return insertCodeBlock(
    value,
    selection,
    text,
    editorFence ?? guessFence(text),
  );
}
