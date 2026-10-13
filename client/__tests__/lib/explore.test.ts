import { describe, expect, it } from "vitest";
import {
  awaitingFirstExplanation,
  exploreAspectRequest,
  exploreProgress,
  isExploreOverview,
  type ExploreOverview,
} from "@/lib/explore";

function aspect(
  id: string,
  overrides: Partial<ExploreOverview["aspects"][number]> = {},
) {
  return {
    aspect_id: id,
    name: id,
    summary: "",
    is_core: true,
    explained: false,
    ...overrides,
  };
}

describe("isExploreOverview", () => {
  it("accepts an object with an aspects array", () => {
    expect(isExploreOverview({ aspects: [] })).toBe(true);
  });

  it("rejects null, a non-object and a missing aspects array", () => {
    expect(isExploreOverview(null)).toBe(false);
    expect(isExploreOverview("x")).toBe(false);
    expect(isExploreOverview({})).toBe(false);
    expect(isExploreOverview({ aspects: "x" })).toBe(false);
  });
});

describe("exploreAspectRequest", () => {
  it("asks to be taught the chosen aspect", () => {
    expect(exploreAspectRequest("計算量")).toBe("「計算量」から教えてください");
  });
});

describe("exploreProgress", () => {
  it("counts explained core aspects against all core aspects", () => {
    const overview = {
      aspects: [
        aspect("a", { explained: true }),
        aspect("b"),
        aspect("c", { is_core: false, explained: true }),
      ],
    };
    expect(exploreProgress(overview)).toEqual({
      reached: 1,
      target: 2,
      complete: false,
    });
  });

  it("is complete once every core aspect is explained", () => {
    const overview = {
      aspects: [
        aspect("a", { explained: true }),
        aspect("b", { is_core: false }),
      ],
    };
    expect(exploreProgress(overview).complete).toBe(true);
  });

  it("falls back to all aspects when none is core, and is never complete when empty", () => {
    expect(
      exploreProgress({ aspects: [aspect("a", { is_core: false })] }),
    ).toEqual({ reached: 0, target: 1, complete: false });
    expect(exploreProgress({ aspects: [] })).toEqual({
      reached: 0,
      target: 0,
      complete: false,
    });
  });
});

describe("awaitingFirstExplanation", () => {
  it("is true while no aspect has been explained", () => {
    expect(awaitingFirstExplanation({ aspects: [aspect("a")] })).toBe(true);
  });

  it("is false once any aspect is explained, and for an empty overview", () => {
    expect(
      awaitingFirstExplanation({
        aspects: [aspect("a", { explained: true }), aspect("b")],
      }),
    ).toBe(false);
    expect(awaitingFirstExplanation({ aspects: [] })).toBe(false);
  });
});
