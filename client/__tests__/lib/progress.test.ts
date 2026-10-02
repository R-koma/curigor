import { describe, it, expect } from "vitest";
import {
  detectAdvance,
  formatAdvance,
  stageDots,
  stageLabel,
  stageMessage,
  type ProgressAspect,
} from "@/lib/progress";

const aspect = (
  name: string,
  reached_stage: ProgressAspect["reached_stage"],
  is_core = true,
): ProgressAspect => ({ name, is_core, reached_stage });

describe("stageDots / stageMessage", () => {
  it("maps each stage to its dot count and next-step text", () => {
    expect(
      [null, "mentioned", "defined", "reasoned", "applied"].map((s) =>
        stageDots(s as ProgressAspect["reached_stage"]),
      ),
    ).toEqual([0, 1, 2, 3, 4]);
    expect(stageMessage(null)).toBe("まだ話していません");
    expect(stageMessage("mentioned")).toBe(
      "次は、どういうものかを説明してみましょう",
    );
    expect(stageMessage("defined")).toBe(
      "次は、なぜ必要か・どう成り立つかを説明してみましょう",
    );
    expect(stageMessage("reasoned")).toBe("なぜ・仕組みまで説明できました");
    expect(stageMessage("applied")).toBe(
      "目的に沿った使い方まで説明できました",
    );
  });
});

describe("stageLabel", () => {
  it("names each reached stage in a short chip label", () => {
    expect(stageLabel(null)).toBeNull();
    expect(stageLabel("mentioned")).toBe("言及");
    expect(stageLabel("defined")).toBe("定義");
    expect(stageLabel("reasoned")).toBe("なぜ・仕組み");
    expect(stageLabel("applied")).toBe("応用");
  });
});

describe("detectAdvance", () => {
  it("does not notify on the first progress", () => {
    expect(detectAdvance(null, [aspect("A", "reasoned")])).toBeNull();
  });

  it("notifies when an aspect rises to defined or above", () => {
    expect(
      detectAdvance([aspect("A", "mentioned")], [aspect("A", "defined")]),
    ).toEqual({ name: "A", stage: "defined", others: 0 });
  });

  it("does not notify when nothing rose", () => {
    expect(
      detectAdvance([aspect("A", "defined")], [aspect("A", "defined")]),
    ).toBeNull();
  });

  it("does not notify a rise that only reaches mentioned", () => {
    expect(
      detectAdvance([aspect("A", null)], [aspect("A", "mentioned")]),
    ).toBeNull();
  });

  it("does not notify an aspect added to the map at mentioned", () => {
    expect(
      detectAdvance(
        [aspect("A", null)],
        [aspect("A", null), aspect("B", "mentioned", false)],
      ),
    ).toBeNull();
  });

  it("notifies an aspect added to the map at defined or above", () => {
    expect(
      detectAdvance(
        [aspect("A", null)],
        [aspect("A", null), aspect("B", "defined", false)],
      ),
    ).toEqual({ name: "B", stage: "defined", others: 0 });
  });

  it("reports the highest rise and counts the rest", () => {
    expect(
      detectAdvance(
        [aspect("A", "mentioned"), aspect("B", "defined"), aspect("C", null)],
        [
          aspect("A", "defined"),
          aspect("B", "reasoned"),
          aspect("C", "defined"),
        ],
      ),
    ).toEqual({ name: "B", stage: "reasoned", others: 2 });
  });
});

describe("formatAdvance", () => {
  it("states what was reached, using an achievement phrase for defined", () => {
    expect(
      formatAdvance({ name: "値の埋め込み方", stage: "defined", others: 0 }),
    ).toBe("値の埋め込み方: どういうものかを説明できました");
    expect(
      formatAdvance({ name: "値の埋め込み方", stage: "reasoned", others: 0 }),
    ).toBe("値の埋め込み方: なぜ・仕組みまで説明できました");
  });

  it("appends the count of other rises", () => {
    expect(formatAdvance({ name: "A", stage: "applied", others: 2 })).toBe(
      "A: 目的に沿った使い方まで説明できました（ほか 2 件）",
    );
  });
});
