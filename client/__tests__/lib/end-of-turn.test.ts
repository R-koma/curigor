import { describe, expect, it } from "vitest";
import {
  asksToResume,
  contentLength,
  endsTurn,
  joinSegments,
  stripEndWord,
  turnIsComplete,
} from "@/lib/end-of-turn";
import type { TranscriptSegment } from "@/lib/stt/types";

const done = (id: number, text: string): TranscriptSegment => ({
  id,
  text,
  status: "done",
});

describe("endsTurn", () => {
  it.each([
    "以上",
    "以上。",
    "説明は以上です以上",
    "半分に絞ります。以上！",
    "以上 ",
  ])("accepts %s", (text) => expect(endsTurn(text)).toBe(true));

  it.each(["以上のことから", "以上です", "異常なし", ""])(
    "rejects %s",
    (text) => expect(endsTurn(text)).toBe(false),
  );
});

describe("stripEndWord", () => {
  it("removes the trailing word and its punctuation", () => {
    expect(stripEndWord("半分に絞ります。以上。")).toBe("半分に絞ります");
    expect(stripEndWord("以上")).toBe("");
  });

  it.each([
    ["以上」", ""],
    ["「以上」", ""],
    ["以上。」", ""],
    ["半分です。「以上」", "半分です"],
  ])("removes quoted %s", (text, expected) => {
    expect(stripEndWord(text)).toBe(expected);
  });

  it.each([
    "以上",
    "以上。",
    "以上」",
    "「以上」",
    "以上。」",
    "半分に絞ります。以上！",
    "『以上』。",
  ])("leaves no closing word after stripping %s", (text) => {
    expect(endsTurn(text)).toBe(true);
    expect(endsTurn(stripEndWord(text))).toBe(false);
  });

  it("keeps an inner 以上", () => {
    expect(stripEndWord("以上のことから半分です")).toBe(
      "以上のことから半分です",
    );
  });
});

describe("joinSegments", () => {
  it("joins done segments in order and skips failed and pending ones", () => {
    expect(
      joinSegments([
        done(1, "二分探索は"),
        { id: 2, text: "", status: "failed" },
        done(3, "半分に絞る"),
        { id: 4, text: "", status: "pending" },
      ]),
    ).toBe("二分探索は半分に絞る");
  });

  it("turns a period after a particle at a segment boundary into a comma", () => {
    expect(
      joinSegments([
        done(1, "特定のフレームワークについて学びたいと考えている。"),
        done(2, "MECEや。"),
        done(3, "5W1H、そして仮説思考について教えてほしい。"),
      ]),
    ).toBe(
      "特定のフレームワークについて学びたいと考えている。MECEや、5W1H、そして仮説思考について教えてほしい。",
    );
  });

  it("keeps periods that end a sentence", () => {
    expect(
      joinSegments([
        done(1, "教えて。"),
        done(2, "そうですね。"),
        done(3, "次です。"),
      ]),
    ).toBe("教えて。そうですね。次です。");
  });

  it("keeps periods after こと and voiced te-form requests", () => {
    expect(
      joinSegments([
        done(1, "大事なのは確かめること。"),
        done(2, "もっと。"),
        done(3, "これを読んで。"),
        done(4, "心配しないで。"),
        done(5, "次です。"),
      ]),
    ).toBe(
      "大事なのは確かめること。もっと。これを読んで。心配しないで。次です。",
    );
  });

  it("still turns periods after と and で particles into commas", () => {
    expect(
      joinSegments([
        done(1, "AとBと。"),
        done(2, "東京で。"),
        done(3, "会う。"),
      ]),
    ).toBe("AとBと、東京で、会う。");
  });

  it("keeps the period of the last done segment", () => {
    expect(joinSegments([done(1, "二分探索は"), done(2, "MECEや。")])).toBe(
      "二分探索はMECEや。",
    );
  });

  it("judges the last segment among done segments only", () => {
    expect(
      joinSegments([
        done(1, "MECEや。"),
        { id: 2, text: "", status: "failed" },
        done(3, "5W1H。"),
        { id: 4, text: "", status: "pending" },
      ]),
    ).toBe("MECEや、5W1H。");
  });

  it("leaves question and exclamation marks alone", () => {
    expect(joinSegments([done(1, "それは？"), done(2, "半分です。")])).toBe(
      "それは？半分です。",
    );
  });

  it("drops the period when the next segment starts with a particle", () => {
    expect(
      joinSegments([
        done(1, "それはヘルスチェック。"),
        done(2, "と呼ばれる仕組みです。"),
        done(3, "必要とするとき。"),
        done(4, "の、振り分けです。"),
        done(5, "ログイン状態の共有。"),
        done(6, "などにメリットがある。"),
      ]),
    ).toBe(
      "それはヘルスチェックと呼ばれる仕組みです。必要とするときの、振り分けです。ログイン状態の共有などにメリットがある。",
    );
  });

  it("drops the period instead of adding a comma after a particle", () => {
    expect(joinSegments([done(1, "MECEや。"), done(2, "などです。")])).toBe(
      "MECEやなどです。",
    );
  });

  it("keeps the period before words that can open a sentence", () => {
    expect(
      joinSegments([
        done(1, "半分です。"),
        done(2, "とりあえず次です。"),
        done(3, "でも違う。"),
        done(4, "で、次です。"),
        done(5, "はい。"),
        done(6, "もう一度。"),
        done(7, "のちほど。"),
      ]),
    ).toBe(
      "半分です。とりあえず次です。でも違う。で、次です。はい。もう一度。のちほど。",
    );
  });

  it("ignores trailing whitespace at a segment boundary", () => {
    expect(joinSegments([done(1, "MECEや。 "), done(2, "5W1H。")])).toBe(
      "MECEや、5W1H。",
    );
  });
});

describe("joinSegments + stripEndWord", () => {
  it("drops the comma left before 以上", () => {
    expect(
      stripEndWord(joinSegments([done(1, "MECEや。"), done(2, "以上。")])),
    ).toBe("MECEや");
  });
});

describe("turnIsComplete", () => {
  it("needs the last segment to end with 以上", () => {
    expect(turnIsComplete([done(1, "半分です"), done(2, "以上")])).toBe(true);
    expect(turnIsComplete([done(1, "以上"), done(2, "続きです")])).toBe(false);
  });

  it("waits for pending segments", () => {
    expect(
      turnIsComplete([{ id: 1, text: "", status: "pending" }, done(2, "以上")]),
    ).toBe(false);
  });

  it("does not complete when the last segment failed", () => {
    expect(
      turnIsComplete([done(1, "以上"), { id: 2, text: "", status: "failed" }]),
    ).toBe(false);
    expect(turnIsComplete([])).toBe(false);
  });
});

describe("asksToResume", () => {
  it.each([
    "続けて",
    "続けて。",
    "うん、続けて",
    "続けてください",
    "続けて下さい！",
  ])("accepts %s as the last segment", (text) => {
    expect(asksToResume([done(1, "えっと"), done(2, text)])).toBe(true);
  });

  it.each(["続けてみます", "続けるには", "続けてほしいのは別の話です", ""])(
    "rejects %s",
    (text) => expect(asksToResume([done(1, text)])).toBe(false),
  );

  it("only looks at the last segment", () => {
    expect(asksToResume([done(1, "続けて"), done(2, "やっぱり質問")])).toBe(
      false,
    );
  });

  it("waits for pending segments and ignores a failed last one", () => {
    expect(
      asksToResume([done(1, "続けて"), { id: 2, text: "", status: "pending" }]),
    ).toBe(false);
    expect(
      asksToResume([done(1, "続けて"), { id: 2, text: "", status: "failed" }]),
    ).toBe(false);
  });
});

describe("contentLength", () => {
  it("counts done segments without punctuation or spaces", () => {
    expect(
      contentLength([
        done(1, "えっと、"),
        { id: 2, text: "", status: "failed" },
        done(3, " 別の例で。"),
      ]),
    ).toBe(7);
  });

  it("is zero for no segments", () => {
    expect(contentLength([])).toBe(0);
  });
});
