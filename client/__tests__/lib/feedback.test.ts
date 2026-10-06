import { describe, it, expect } from "vitest";
import type { AspectMap } from "@/lib/aspect-map";
import {
  feedbackImprovements,
  feedbackSourceLabel,
  formatFeedbackDate,
  latestImprovementCount,
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

describe("latestImprovementCount", () => {
  it("counts the improvements of the newest feedback", () => {
    const older = {
      ...fb("a", "2026-06-01T00:00:00Z"),
      improvements: "・一\n・二\n・三",
    };
    const newer = { ...fb("b", "2026-06-05T00:00:00Z"), improvements: "・一" };
    expect(latestImprovementCount([newer, older])).toBe(1);
    expect(latestImprovementCount([older, newer])).toBe(1);
  });

  it("returns 0 without feedback", () => {
    expect(latestImprovementCount([])).toBe(0);
  });
});

const MAP: AspectMap = {
  root: "二分探索",
  aspects: [{ id: "a1", name: "計算量", summary: "", coverage: "covered" }],
};

describe("feedbackImprovements", () => {
  it("resolves each item's aspect from the aspect map", () => {
    const feedback: Feedback = {
      ...fb("a", "2026-06-01T00:00:00Z"),
      improvements: "見積もり\n用語",
      improvement_items: [
        { text: "見積もり", aspect_id: "a1" },
        { text: "用語", aspect_id: null },
      ],
    };
    expect(feedbackImprovements(feedback, MAP)).toEqual([
      { text: "見積もり", aspect: { id: "a1", name: "計算量" } },
      { text: "用語", aspect: null },
    ]);
  });

  it("drops the aspect when the map is missing or does not know the id", () => {
    const feedback: Feedback = {
      ...fb("a", "2026-06-01T00:00:00Z"),
      improvement_items: [
        { text: "見積もり", aspect_id: "a1" },
        { text: "別", aspect_id: "a9" },
      ],
    };
    expect(feedbackImprovements(feedback, null).map((i) => i.aspect)).toEqual([
      null,
      null,
    ]);
    expect(feedbackImprovements(feedback, MAP).map((i) => i.aspect)).toEqual([
      { id: "a1", name: "計算量" },
      null,
    ]);
  });

  it("falls back to the improvements text for feedback saved before items existed", () => {
    for (const improvement_items of [null, undefined]) {
      const feedback: Feedback = {
        ...fb("a", "2026-06-01T00:00:00Z"),
        improvements: "・一つ目\n・二つ目",
        improvement_items,
      };
      expect(feedbackImprovements(feedback, MAP)).toEqual([
        { text: "一つ目", aspect: null },
        { text: "二つ目", aspect: null },
      ]);
    }
  });
});
