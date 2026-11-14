import { describe, expect, it } from "vitest";
import {
  SESSION_TYPE_LABELS,
  addDays,
  parseReflectionTarget,
  pickInitialDay,
  reflectionSourceHref,
  reflectionUrl,
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

describe("reflectionSourceHref", () => {
  it("links notes and study memos by session type", () => {
    expect(reflectionSourceHref("learning", "n1")).toBe("/notes/n1");
    expect(reflectionSourceHref("review", "n1")).toBe("/notes/n1");
    expect(reflectionSourceHref("explore", "m1")).toBe("/study-memos/m1");
  });
});

describe("parseReflectionTarget", () => {
  const TODAY = "2026-11-15";
  it.each([
    [{ day: "2026-11-10" }, { kind: "day", day: "2026-11-10" }],
    [{ day: "2026-11-15" }, { kind: "day", day: "2026-11-15" }],
    [{ week: "2026-11-12" }, { kind: "week", weekStart: "2026-11-09" }],
    [{ week: "2026-11-15" }, { kind: "week", weekStart: "2026-11-09" }],
    [
      { day: "2026-11-10", week: "2026-11-02" },
      { kind: "day", day: "2026-11-10" },
    ],
    [{ day: "abc" }, null],
    [{ day: "2026-02-30" }, null],
    [{ day: "2026-11-16" }, null],
    [{ day: "0000-01-01" }, null],
    [{ day: "0001-01-01" }, null],
    [{ week: "0001-01-01" }, null],
    [{ day: "1999-12-31" }, null],
    [{ day: "2000-01-01" }, { kind: "day", day: "2000-01-01" }],
    [{ week: "2026-11-16" }, null],
    [{ day: ["2026-11-10", "2026-11-11"] }, null],
    [{}, null],
  ])("parses %o", (params, expected) => {
    expect(parseReflectionTarget(params, TODAY)).toEqual(expected);
  });
});

describe("reflectionUrl", () => {
  it("builds the url for a day and a week", () => {
    expect(reflectionUrl({ kind: "day", day: "2026-11-10" })).toBe(
      "/reflections?day=2026-11-10",
    );
    expect(reflectionUrl({ kind: "week", weekStart: "2026-11-09" })).toBe(
      "/reflections?week=2026-11-09",
    );
  });
});
