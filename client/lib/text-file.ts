import { codeBlock } from "@/lib/compose-insert";
import { isMessageTooLong, MAX_MESSAGE_LENGTH } from "@/lib/message-length";

const MAX_BYTES_PER_CHAR = 4;
export const MAX_TEXT_FILE_BYTES = MAX_MESSAGE_LENGTH * MAX_BYTES_PER_CHAR;
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
const UTF16_BOMS: [number, number, string][] = [
  [0xff, 0xfe, "utf-16le"],
  [0xfe, 0xff, "utf-16be"],
];
const JAPANESE_ENCODINGS = ["shift_jis", "euc-jp"];
const JAPANESE_CHARS = /[\u3040-\u30ff\u4e00-\u9fff]/g;
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
  `${name} は大きすぎます（${MAX_MESSAGE_LENGTH.toLocaleString("ja-JP")}字・2,000行まで）`;

export function fenceForFileName(name: string): string {
  const extension = /.\.([^./\\]+)$/.exec(name)?.[1]?.toLowerCase();
  return extension ? (FENCES.get(extension) ?? "") : "";
}

function decode(bytes: Uint8Array, encoding: string): string | null {
  try {
    return new TextDecoder(encoding, { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}

function japaneseScore(text: string): number {
  return text.match(JAPANESE_CHARS)?.length ?? 0;
}

function rawText(bytes: Uint8Array): string | null {
  const utf16 = UTF16_BOMS.find(
    ([first, second]) => bytes[0] === first && bytes[1] === second,
  );
  if (utf16) return decode(bytes, utf16[2]);
  if (bytes.subarray(0, SNIFF_BYTES).includes(0)) return null;
  const utf8 = decode(bytes, "utf-8");
  if (utf8 !== null) return utf8;
  const japanese = JAPANESE_ENCODINGS.map((encoding) => decode(bytes, encoding))
    .filter((text) => text !== null)
    .sort((a, b) => japaneseScore(b) - japaneseScore(a))[0];
  if (japanese && japaneseScore(japanese) > 0) return japanese;
  return decode(bytes, "windows-1252");
}

export function decodeText(bytes: Uint8Array): string | null {
  return (
    rawText(bytes)
      ?.replace(/^\uFEFF/, "")
      .replace(/\r\n?/g, "\n")
      .replace(/\n+$/, "") ?? null
  );
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
  if (isMessageTooLong(text) || text.split("\n").length > MAX_TEXT_FILE_LINES) {
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
