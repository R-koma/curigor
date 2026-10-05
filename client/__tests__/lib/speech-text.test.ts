import { describe, expect, it } from "vitest";
import {
  MAX_SPEECH_CHARS,
  SentenceSplitter,
  splitIntoSentences,
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
    const splitter = new SentenceSplitter();
    splitter.push("はい。");
    const pieces = splitter.push(`${text}。`);

    expect(pieces[0]).toHaveLength(500);
    expect(pieces.every((p) => p.length <= MAX_SPEECH_CHARS)).toBe(true);
  });
});

describe("speakable fragments", () => {
  it("drops a table separator row and reads table cells with commas", () => {
    expect(toSpeakableText("|---|:--:|")).toBe("");
    expect(toSpeakableText("| 用語 | 意味 |")).toBe("用語、意味");
    expect(
      new SentenceSplitter().push(
        "| 用語 | 意味 |\n|---|:--:|\n| 探索 | さがす |\n",
      ),
    ).toEqual(["用語、意味", "探索、さがす"]);
  });

  it("drops fragments with no letters or digits", () => {
    const splitter = new SentenceSplitter();

    expect(splitter.push("。\n🎉\n……！\n")).toEqual([]);
    expect(splitter.push("3。")).toEqual(["3。"]);
  });
});

describe("splitIntoSentences", () => {
  it("splits a whole message the same way as the stream", () => {
    const streamed = new SentenceSplitter();
    const pieces = [
      ...streamed.push("一つ目で"),
      ...streamed.push("す。二つ目\nで"),
      ...streamed.push("す！"),
      ...streamed.flush(),
    ];

    expect(splitIntoSentences("一つ目です。二つ目\nです！")).toEqual(pieces);
    expect(pieces).toEqual(["一つ目です。", "二つ目", "です！"]);
  });
});

describe("first sentence", () => {
  const long =
    "二分探索というのは、探す範囲を毎回半分に絞っていく方法です。次の文です。";

  it("cuts a long first sentence at the first comma after 10 chars", () => {
    expect(splitIntoSentences(long)).toEqual([
      "二分探索というのは、",
      "探す範囲を毎回半分に絞っていく方法です。",
      "次の文です。",
    ]);
  });

  it("streams the same split as splitIntoSentences", () => {
    const splitter = new SentenceSplitter();
    const streamed = [...long].flatMap((char) => splitter.push(char));
    expect([...streamed, ...splitter.flush()]).toEqual(
      splitIntoSentences(long),
    );
  });

  it("leaves a short first sentence alone", () => {
    expect(splitIntoSentences("はい、そうです。続きです。")).toEqual([
      "はい、そうです。",
      "続きです。",
    ]);
  });

  it("leaves a long first sentence without a usable comma alone", () => {
    const text = "あ、" + "い".repeat(30) + "。";
    expect(splitIntoSentences(text)).toEqual([text]);
  });
});
