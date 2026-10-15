import { common, createLowlight } from "lowlight";
import { CODE_LANGUAGES, fenceForVscodeMode } from "@/lib/code-languages";
import {
  insertCodeBlock,
  isInsideFence,
  type TextEdit,
  type TextSelection,
} from "@/lib/compose-insert";

type LineKind = "code" | "weak" | "prose" | "plain" | "neutral";

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
const SENTENCE = /[\p{L}\p{N}][.?!。]\s*$/u;
const ASSIGNMENT = /[\w\])]\s*(=|\+=|-=|==|=>|:=)\s*\S/;
const CODE_ENDING = /[;{}]\s*$/;
const WEAK_ENDING = /[:)]\s*$/;
const PROSE_MODES = new Set(["markdown", "plaintext", "latex"]);
const JAPANESE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/gu;

function japaneseRatio(line: string): number {
  const chars = line.replace(/\s/g, "");
  return (chars.match(JAPANESE)?.length ?? 0) / chars.length;
}

function classify(line: string): LineKind {
  if (LATEX.test(line) || MARKDOWN.test(line)) return "prose";
  if (COMMENT.test(line)) return "neutral";
  if (INDENTED.test(line)) return "code";
  if (SENTENCE.test(line) || japaneseRatio(line) > MIN_JAPANESE_RATIO) {
    return "prose";
  }
  if (KEYWORD.test(line) || SHELL_PROMPT.test(line) || CODE_ENDING.test(line)) {
    return "code";
  }
  if (ASSIGNMENT.test(line) || WEAK_ENDING.test(line)) return "weak";
  return "plain";
}

export function looksLikeCode(text: string): boolean {
  const kinds = text
    .split("\n")
    .filter((line) => line.trim())
    .map(classify)
    .filter((kind) => kind !== "neutral");
  if (kinds.length < 2) return false;
  const count = (kind: LineKind) => kinds.filter((k) => k === kind).length;
  const codeLike = count("code") + count("weak");
  return (
    count("code") >= 1 &&
    codeLike >= 2 &&
    codeLike / kinds.length >= MIN_CODE_RATIO &&
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
    if (typeof mode !== "string" || PROSE_MODES.has(mode)) return null;
    return fenceForVscodeMode(mode);
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
  if (!text.trim().includes("\n") || /```|~~~/.test(text)) return null;
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
