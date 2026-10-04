import { describe, expect, it } from "vitest";
import {
  COVERAGE_DISPLAY,
  FEEDBACK_DISPLAY,
  URGENCY_DISPLAY,
  getUrgency,
} from "@/lib/status-display";

const NOW = new Date(2026, 9, 4, 12, 0);

function at(day: number, hour: number, minute: number): string {
  return new Date(2026, 9, day, hour, minute).toISOString();
}

describe("getUrgency", () => {
  it.each([
    ["the previous day at 23:59", at(3, 23, 59), "overdue"],
    ["today at 00:00", at(4, 0, 0), "today"],
    ["today at 23:59", at(4, 23, 59), "today"],
    ["tomorrow at 00:00", at(5, 0, 0), "tomorrow"],
    ["tomorrow at 23:59", at(5, 23, 59), "tomorrow"],
    ["the day after tomorrow at 00:00", at(6, 0, 0), "later"],
  ] as const)("classifies %s as %s", (_, value, expected) => {
    expect(getUrgency(value, NOW)).toBe(expected);
  });
});

describe("URGENCY_DISPLAY", () => {
  it("keeps the labels and maps urgency to tones", () => {
    expect(URGENCY_DISPLAY.overdue).toMatchObject({
      label: "期限切れ",
      tone: "danger",
    });
    expect(URGENCY_DISPLAY.today).toMatchObject({
      label: "今日",
      tone: "caution",
    });
    expect(URGENCY_DISPLAY.tomorrow).toMatchObject({
      label: "明日",
      tone: "warning",
    });
    expect(URGENCY_DISPLAY.later).toMatchObject({
      label: "それ以降",
      tone: "success",
    });
  });

  it("colors only the left border", () => {
    for (const display of Object.values(URGENCY_DISPLAY)) {
      expect(display.leftBorder).toMatch(/^border-l-/);
    }
  });
});

describe("COVERAGE_DISPLAY", () => {
  it("maps coverage to labels and tones", () => {
    expect(COVERAGE_DISPLAY.covered).toMatchObject({
      label: "カバー済み",
      tone: "success",
    });
    expect(COVERAGE_DISPLAY.partial).toMatchObject({
      label: "部分的",
      tone: "warning",
    });
    expect(COVERAGE_DISPLAY.uncovered).toMatchObject({
      label: "未カバー",
      tone: "neutral",
    });
  });

  it("gives every coverage an icon", () => {
    for (const display of Object.values(COVERAGE_DISPLAY)) {
      expect(display.icon).toBeDefined();
    }
  });
});

describe("FEEDBACK_DISPLAY", () => {
  it("maps feedback kinds to tones and icons", () => {
    expect(FEEDBACK_DISPLAY.positive.tone).toBe("success");
    expect(FEEDBACK_DISPLAY.improvement.tone).toBe("warning");
    expect(FEEDBACK_DISPLAY.positive.icon).toBeDefined();
    expect(FEEDBACK_DISPLAY.improvement.icon).toBeDefined();
  });
});
