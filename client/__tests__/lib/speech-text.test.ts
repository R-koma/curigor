import { describe, expect, it } from "vitest";
import {
  MAX_SPEECH_CHARS,
  SentenceSplitter,
  toSpeakableText,
} from "@/lib/speech-text";

describe("toSpeakableText", () => {
  it("removes Markdown markers", () => {
    expect(toSpeakableText("## 見出し\n**重要**です")).toBe("見出し 重要です");
  });

  it("keeps the link text and drops the URL", () => {
    expect(toSpeakableText("[公式](https://example.com)を見る")).toBe(
      "公式を見る",
    );
  });

  it("keeps inline code text", () => {
    expect(toSpeakableText("`foo()` を呼ぶ")).toBe("foo() を呼ぶ");
  });

  it("flattens list markers", () => {
    expect(toSpeakableText("- 一つ目\n- 二つ目")).toBe("一つ目 二つ目");
  });

  it("returns an empty string for code blocks and rules only", () => {
    expect(toSpeakableText("```py\nx = 1\n```")).toBe("");
    expect(toSpeakableText("---")).toBe("");
  });
});

describe("SentenceSplitter", () => {
  it("emits a sentence once its end arrives and holds the rest", () => {
    const splitter = new SentenceSplitter();

    expect(splitter.push("二分探索は半分に絞ります。次に")).toEqual([
      "二分探索は半分に絞ります。",
    ]);
    expect(splitter.push("例を見ます。")).toEqual(["次に例を見ます。"]);
  });

  it("joins a sentence split across chunks", () => {
    const splitter = new SentenceSplitter();

    expect(splitter.push("半分に")).toEqual([]);
    expect(splitter.push("絞ります！")).toEqual(["半分に絞ります！"]);
  });

  it("treats a line break as a sentence end", () => {
    expect(new SentenceSplitter().push("見出し\n本文です。")).toEqual([
      "見出し",
      "本文です。",
    ]);
  });

  it("flushes the remainder", () => {
    const splitter = new SentenceSplitter();
    splitter.push("終わりの句点が無い");

    expect(splitter.flush()).toEqual(["終わりの句点が無い"]);
    expect(splitter.flush()).toEqual([]);
  });

  it("skips fenced code blocks", () => {
    const splitter = new SentenceSplitter();

    expect(
      splitter.push("まず説明します。\n```python\nprint(1)\n```\n続きです。"),
    ).toEqual(["まず説明します。", "続きです。"]);
  });

  it("skips a code block that spans chunks", () => {
    const splitter = new SentenceSplitter();

    expect(splitter.push("```py\nx = 1")).toEqual([]);
    expect(splitter.push("\n```\nok。")).toEqual(["ok。"]);
  });

  it("does not emit anything for a response of symbols only", () => {
    const splitter = new SentenceSplitter();

    expect(splitter.push("---\n")).toEqual([]);
    expect(splitter.push("```\ncode\n```")).toEqual([]);
    expect(splitter.flush()).toEqual([]);
  });

  it("splits a sentence longer than the limit without losing text", () => {
    const text = "あ".repeat(1200);
    const pieces = new SentenceSplitter().push(`${text}。`);

    expect(pieces.every((p) => p.length <= MAX_SPEECH_CHARS)).toBe(true);
    expect(pieces.join("")).toBe(`${text}。`);
  });

  it("prefers a comma when cutting a long sentence", () => {
    const text = ("あ".repeat(99) + "、").repeat(6);
    const pieces = new SentenceSplitter().push(`${text}。`);

    expect(pieces[0]).toHaveLength(500);
    expect(pieces.every((p) => p.length <= MAX_SPEECH_CHARS)).toBe(true);
  });
});
