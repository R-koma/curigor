import { describe, it, expect } from "vitest";
import {
  feedbackSourceLabel,
  formatFeedbackDate,
  newestFirst,
  splitFeedbackItems,
  type Feedback,
} from "@/lib/feedback";

function fb(id: string, created_at: string): Feedback {
  return {
    id,
    understanding_level: "medium",
    strength: "",
    improvements: "",
    session_type: "review",
    created_at,
  };
}

describe("splitFeedbackItems", () => {
  it("splits lines and strips bullet markers and blanks", () => {
    expect(splitFeedbackItems("・一つ目\n- 二つ目\n\n  * 三つ目  ")).toEqual([
      "一つ目",
      "二つ目",
      "三つ目",
    ]);
  });
});

describe("formatFeedbackDate", () => {
  it("formats in Japan time regardless of the runtime time zone", () => {
    expect(formatFeedbackDate("2026-05-31T16:00:00Z")).toBe("2026年6月1日");
  });
});

describe("feedbackSourceLabel", () => {
  it("labels learning and review sessions", () => {
    expect(feedbackSourceLabel("learning")).toBe("学習");
    expect(feedbackSourceLabel("review")).toBe("復習");
  });

  it("returns null when the session is unknown or missing", () => {
    expect(feedbackSourceLabel(null)).toBeNull();
    expect(feedbackSourceLabel("synthesis")).toBeNull();
  });
});

describe("newestFirst", () => {
  it("orders by created_at descending without mutating the input", () => {
    const input = [
      fb("a", "2026-06-01T00:00:00Z"),
      fb("b", "2026-06-05T00:00:00+00:00"),
      fb("c", "2026-06-03T09:00:00+09:00"),
    ];
    expect(newestFirst(input).map((f) => f.id)).toEqual(["b", "c", "a"]);
    expect(input.map((f) => f.id)).toEqual(["a", "b", "c"]);
  });
});
