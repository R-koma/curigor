import { describe, it, expect } from "vitest";
import {
  isTopicCorrectionCard,
  topicCorrectionAnswerText,
  topicEditText,
} from "@/lib/topic-correction";

describe("topicCorrectionAnswerText", () => {
  it("states what was chosen in words the model can read", () => {
    expect(topicCorrectionAnswerText("accept")).toBe(
      "はい、トピックを変更する",
    );
    expect(topicCorrectionAnswerText("decline")).toBe("いいえ、変更しない");
  });
});

describe("isTopicCorrectionCard", () => {
  it("accepts a card with both topics", () => {
    expect(isTopicCorrectionCard({ previous_topic: "A", new_topic: "B" })).toBe(
      true,
    );
  });

  it("rejects an intake card and other shapes", () => {
    expect(isTopicCorrectionCard({ questions: [] })).toBe(false);
    expect(isTopicCorrectionCard({ new_topic: "B" })).toBe(false);
    expect(isTopicCorrectionCard(undefined)).toBe(false);
    expect(isTopicCorrectionCard(null)).toBe(false);
  });
});

describe("topicEditText", () => {
  it("builds the message text for a header edit", () => {
    expect(topicEditText("Linuxの仕組み")).toBe(
      "トピックを「Linuxの仕組み」に変更しました",
    );
  });
});
