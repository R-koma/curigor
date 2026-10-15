import { describe, expect, it } from "vitest";
import {
  attachmentText,
  decodeText,
  fenceForFileName,
  readTextFile,
} from "@/lib/text-file";

const bytes = (...values: number[]) => new Uint8Array(values);
const encode = (text: string) => new TextEncoder().encode(text);

describe("decodeText", () => {
  it("reads UTF-8", () => {
    expect(decodeText(encode("こんにちは"))).toBe("こんにちは");
  });

  it("falls back to Shift_JIS", () => {
    expect(decodeText(bytes(0x82, 0xa0, 0x82, 0xa2, 0x82, 0xa4))).toBe(
      "あいう",
    );
  });

  it("drops a byte order mark", () => {
    expect(decodeText(bytes(0xef, 0xbb, 0xbf, 0x61))).toBe("a");
  });

  it("normalizes line endings and drops trailing newlines", () => {
    expect(decodeText(encode("a\r\nb\rc\n\n"))).toBe("a\nb\nc");
  });

  it("rejects binary content", () => {
    expect(decodeText(bytes(0x25, 0x50, 0x44, 0x46, 0x00, 0x01))).toBeNull();
  });

  it("reads EUC-JP", () => {
    expect(decodeText(bytes(0xa4, 0xa2, 0xa4, 0xa4, 0xa4, 0xa6))).toBe(
      "あいう",
    );
  });

  it("reads UTF-16 with a byte order mark", () => {
    expect(decodeText(bytes(0xff, 0xfe, 0x68, 0x00, 0x69, 0x00))).toBe("hi");
    expect(decodeText(bytes(0xfe, 0xff, 0x00, 0x68, 0x00, 0x69))).toBe("hi");
  });

  it("reads Latin-1 as Windows-1252", () => {
    expect(decodeText(bytes(0x63, 0x61, 0x66, 0xe9))).toBe("café");
  });
});

describe("fenceForFileName", () => {
  it.each([
    ["main.py", "python"],
    ["App.TSX", "typescript"],
    ["index.mjs", "javascript"],
    ["lib.hpp", "cpp"],
    ["run.zsh", "bash"],
    ["data.yml", "yaml"],
    ["notes.md", "markdown"],
    ["paper.tex", "latex"],
    ["table.csv", ""],
    ["README", ""],
    [".bashrc", ""],
  ])("names %s as 「%s」", (name, fence) => {
    expect(fenceForFileName(name)).toBe(fence);
  });
});

describe("readTextFile", () => {
  const file = (content: BlobPart, name = "main.py") =>
    new File([content], name, { type: "text/plain" });

  it("reads a source file with its language", async () => {
    expect(await readTextFile(file("print(1)\n"))).toEqual({
      ok: true,
      file: { name: "main.py", text: "print(1)", fence: "python" },
    });
  });

  it("refuses a file over 100KB", async () => {
    expect(await readTextFile(file("a".repeat(102401), "big.txt"))).toEqual({
      ok: false,
      error: "big.txt は大きすぎます（100KB・2,000行まで）",
    });
  });

  it("refuses a file over 2,000 lines", async () => {
    expect(await readTextFile(file("a\n".repeat(2001), "long.txt"))).toEqual({
      ok: false,
      error: "long.txt は大きすぎます（100KB・2,000行まで）",
    });
  });

  it("accepts exactly 2,000 lines", async () => {
    const result = await readTextFile(file("a\n".repeat(2000), "ok.txt"));
    expect(result.ok).toBe(true);
  });

  it("refuses a binary file", async () => {
    expect(
      await readTextFile(file(bytes(0x25, 0x50, 0x00), "doc.pdf")),
    ).toEqual({
      ok: false,
      error: "doc.pdf はテキストのファイルではないため添付できません",
    });
  });

  it("reports a file that cannot be read", async () => {
    const broken = file("x", "gone.txt");
    broken.arrayBuffer = () => Promise.reject(new Error("gone"));

    expect(await readTextFile(broken)).toEqual({
      ok: false,
      error: "gone.txt を読み込めませんでした",
    });
  });
});

describe("attachmentText", () => {
  it("puts the file name above the code", () => {
    expect(
      attachmentText([{ name: "a.py", text: "x = 1", fence: "python" }]),
    ).toBe("`a.py`\n```python\nx = 1\n```");
  });

  it("joins several files with a blank line and skips empty ones", () => {
    expect(
      attachmentText([
        { name: "a.py", text: "x", fence: "python" },
        { name: "empty.txt", text: "", fence: "" },
        { name: "b.txt", text: "y", fence: "" },
      ]),
    ).toBe("`a.py`\n```python\nx\n```\n\n`b.txt`\n```\ny\n```");
  });

  it("wraps a markdown file that contains a fence in a longer fence", () => {
    expect(
      attachmentText([
        { name: "n.md", text: "```js\nx\n```", fence: "markdown" },
      ]),
    ).toBe("`n.md`\n````markdown\n```js\nx\n```\n````");
  });

  it("drops backticks from a file name", () => {
    expect(attachmentText([{ name: "a`b.txt", text: "x", fence: "" }])).toBe(
      "`ab.txt`\n```\nx\n```",
    );
  });

  it("is empty when every file is empty", () => {
    expect(attachmentText([{ name: "e.txt", text: "", fence: "" }])).toBe("");
  });
});
