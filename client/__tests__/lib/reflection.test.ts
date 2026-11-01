import { describe, expect, it } from "vitest";
import {
  SESSION_TYPE_LABELS,
  addDays,
  pickInitialDay,
  toIsoDate,
  weekStartOf,
} from "@/lib/reflection";

describe("weekStartOf", () => {
  it("returns the Monday of the week", () => {
    expect(weekStartOf("2026-11-01")).toBe("2026-10-26");
    expect(weekStartOf("2026-10-26")).toBe("2026-10-26");
    expect(weekStartOf("2026-10-29")).toBe("2026-10-26");
  });
});

describe("addDays", () => {
  it("crosses month and year boundaries", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-01-01", -1)).toBe("2025-12-31");
    expect(addDays("2026-10-26", 7)).toBe("2026-11-02");
  });
});

describe("toIsoDate", () => {
  it("uses the calendar day in Asia/Tokyo", () => {
    expect(toIsoDate(new Date("2026-10-31T16:00:00Z"))).toBe("2026-11-01");
    expect(toIsoDate(new Date("2026-10-31T14:59:00Z"))).toBe("2026-10-31");
  });
});

describe("SESSION_TYPE_LABELS", () => {
  it("names each session type", () => {
    expect(SESSION_TYPE_LABELS).toEqual({
      learning: "説明して学ぶ",
      explore: "インプット",
      review: "復習",
    });
  });
});

describe("pickInitialDay", () => {
  const week = (learned: string[]) =>
    [26, 27, 28, 29, 30, 31].map((d) => ({
      day: `2026-10-${d}`,
      has_learning: learned.includes(`2026-10-${d}`),
      unread: false,
    }));

  it("picks today when today has learning", () => {
    const days = [
      ...week([]),
      { day: "2026-11-01", has_learning: true, unread: false },
    ];
    expect(pickInitialDay(days, "2026-11-01")).toBe("2026-11-01");
  });

  it("falls back to the last day with learning in the week", () => {
    const days = [
      ...week(["2026-10-27", "2026-10-29"]),
      { day: "2026-11-01", has_learning: false, unread: false },
    ];
    expect(pickInitialDay(days, "2026-11-01")).toBe("2026-10-29");
  });

  it("keeps today when nothing was learned this week", () => {
    const days = [
      ...week([]),
      { day: "2026-11-01", has_learning: false, unread: false },
    ];
    expect(pickInitialDay(days, "2026-11-01")).toBe("2026-11-01");
  });

  it("picks the first day of a past week with no learning", () => {
    const days = [
      ...week([]),
      { day: "2026-11-01", has_learning: false, unread: false },
    ];
    expect(pickInitialDay(days, "2026-11-10")).toBe("2026-10-26");
  });
});
