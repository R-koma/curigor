import { codeBlock } from "@/lib/compose-insert";

export const MAX_TEXT_FILE_BYTES = 102400;
export const MAX_TEXT_FILE_LINES = 2000;
export const MAX_TEXT_FILES = 5;

export interface TextFile {
  name: string;
  text: string;
  fence: string;
}

export type TextFileResult =
  | { ok: true; file: TextFile }
  | { ok: false; error: string };

const SNIFF_BYTES = 8192;
const ENCODINGS = ["utf-8", "shift_jis"];
const FENCES = new Map([
  ["py", "python"],
  ["js", "javascript"],
  ["mjs", "javascript"],
  ["cjs", "javascript"],
  ["jsx", "javascript"],
  ["ts", "typescript"],
  ["mts", "typescript"],
  ["cts", "typescript"],
  ["tsx", "typescript"],
  ["java", "java"],
  ["c", "c"],
  ["h", "c"],
  ["cpp", "cpp"],
  ["cc", "cpp"],
  ["cxx", "cpp"],
  ["hpp", "cpp"],
  ["hh", "cpp"],
  ["go", "go"],
  ["rs", "rust"],
  ["sql", "sql"],
  ["html", "html"],
  ["htm", "html"],
  ["css", "css"],
  ["sh", "bash"],
  ["bash", "bash"],
  ["zsh", "bash"],
  ["json", "json"],
  ["yaml", "yaml"],
  ["yml", "yaml"],
  ["md", "markdown"],
  ["tex", "latex"],
  ["rb", "ruby"],
  ["php", "php"],
  ["kt", "kotlin"],
  ["swift", "swift"],
  ["cs", "csharp"],
  ["r", "r"],
]);

const tooLarge = (name: string) =>
  `${name} は大きすぎます（100KB・2,000行まで）`;

export function fenceForFileName(name: string): string {
  const extension = /.\.([^./\\]+)$/.exec(name)?.[1]?.toLowerCase();
  return extension ? (FENCES.get(extension) ?? "") : "";
}

export function decodeText(bytes: Uint8Array): string | null {
  if (bytes.subarray(0, SNIFF_BYTES).includes(0)) return null;
  for (const encoding of ENCODINGS) {
    try {
      return new TextDecoder(encoding, { fatal: true })
        .decode(bytes)
        .replace(/^﻿/, "")
        .replace(/\r\n?/g, "\n")
        .replace(/\n+$/, "");
    } catch {}
  }
  return null;
}

export async function readTextFile(file: File): Promise<TextFileResult> {
  if (file.size > MAX_TEXT_FILE_BYTES) {
    return { ok: false, error: tooLarge(file.name) };
  }
  let bytes: Uint8Array;
  try {
    bytes = new Uint8Array(await file.arrayBuffer());
  } catch {
    return { ok: false, error: `${file.name} を読み込めませんでした` };
  }
  const text = decodeText(bytes);
  if (text === null) {
    return {
      ok: false,
      error: `${file.name} はテキストのファイルではないため添付できません`,
    };
  }
  if (text.split("\n").length > MAX_TEXT_FILE_LINES) {
    return { ok: false, error: tooLarge(file.name) };
  }
  return {
    ok: true,
    file: { name: file.name, text, fence: fenceForFileName(file.name) },
  };
}

export function attachmentText(files: TextFile[]): string {
  return files
    .filter((file) => file.text)
    .map(
      (file) =>
        `\`${file.name.replaceAll("`", "")}\`\n${codeBlock(file.text, file.fence)}`,
    )
    .join("\n\n");
}
