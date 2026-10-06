import { describe, it, expect } from "vitest";
import { topicCorrectionAnswerText } from "@/lib/topic-correction";

describe("topicCorrectionAnswerText", () => {
  it("states what was chosen in words the model can read", () => {
    expect(topicCorrectionAnswerText("accept")).toBe(
      "はい、トピックを変更する",
    );
    expect(topicCorrectionAnswerText("decline")).toBe("いいえ、変更しない");
  });
});
