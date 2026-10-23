import { describe, expect, it } from "vitest";
import type { ChatMessage } from "@/hooks/use-chat-websocket";
import { canStopGeneration } from "@/lib/stop-generation";

const user = (extra: Partial<ChatMessage> = {}): ChatMessage => ({
  role: "user",
  content: "u",
  ...extra,
});
const ai = (extra: Partial<ChatMessage> = {}): ChatMessage => ({
  role: "assistant",
  content: "a",
  ...extra,
});
const card = {
  question: "q",
  options: [],
} as unknown as ChatMessage["intakeCard"];
const correction = {
  question: "q",
} as unknown as ChatMessage["topicCorrectionCard"];

describe("canStopGeneration", () => {
  it("allows stopping an ordinary message in flight", () => {
    expect(canStopGeneration([user(), ai(), user()], true, 1)).toBe(true);
  });

  it("allows stopping while a partial reply streams", () => {
    expect(canStopGeneration([user(), ai(), user(), ai()], true, 1)).toBe(true);
  });

  it("does not allow stopping when nothing is generating", () => {
    expect(canStopGeneration([user(), ai(), user()], false, 1)).toBe(false);
  });

  it("does not allow stopping the opening turn", () => {
    expect(canStopGeneration([user()], true, 1)).toBe(false);
    expect(canStopGeneration([user(), ai()], true, 1)).toBe(false);
    expect(canStopGeneration([ai(), user()], true, 2)).toBe(false);
  });

  it("does not allow stopping an intake answer, a reply to the card, a topic correction answer or a topic edit", () => {
    expect(
      canStopGeneration(
        [user(), ai(), user({ intakeAnswered: true })],
        true,
        1,
      ),
    ).toBe(false);
    expect(
      canStopGeneration([user(), ai({ intakeCard: card }), user()], true, 1),
    ).toBe(false);
    expect(
      canStopGeneration(
        [user(), ai(), user({ topicCorrectionAnswered: true })],
        true,
        1,
      ),
    ).toBe(false);
    expect(
      canStopGeneration(
        [user(), ai({ topicCorrectionCard: correction }), user()],
        true,
        1,
      ),
    ).toBe(false);
    expect(
      canStopGeneration([user(), ai(), user({ topicEdit: true })], true, 1),
    ).toBe(false);
  });
});
