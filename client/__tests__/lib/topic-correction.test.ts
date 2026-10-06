import { describe, it, expect } from "vitest";
import {
  isTopicCorrectionCard,
  topicCorrectionAnswerText,
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
