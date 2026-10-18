import { describe, it, expect } from "vitest";
import {
  aspectAnchorId,
  findAspectName,
  type AspectMap,
} from "@/lib/aspect-map";

const MAP: AspectMap = {
  root: "二分探索",
  aspects: [
    {
      id: "a1",
      name: "計算量",
      summary: "",
      coverage: "covered",
      children: [
        { id: "a1-1", name: "最悪計算量", summary: "", coverage: "partial" },
      ],
    },
  ],
};

describe("aspect map helpers", () => {
  it("builds an anchor id", () => {
    expect(aspectAnchorId("a1-1")).toBe("aspect-a1-1");
  });

  it("finds nested aspect names", () => {
    expect(findAspectName(MAP, "a1-1")).toBe("最悪計算量");
  });

  it("returns null for unknown ids and missing maps", () => {
    expect(findAspectName(MAP, "a9")).toBeNull();
    expect(findAspectName(null, "a1")).toBeNull();
  });
});
