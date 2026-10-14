import { describe, expect, it } from "vitest";
import {
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
