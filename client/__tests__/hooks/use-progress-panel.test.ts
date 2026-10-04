import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { LearningProgress } from "@/hooks/use-chat-websocket";
import { useProgressPanel } from "@/hooks/use-progress-panel";

const withPremise: LearningProgress = {
  reached_aspects: [],
  target_count: 3,
  is_complete: false,
  aspects: [],
  intake: { purpose: "仕事で使う", source: "", prior_knowledge: "" },
};

describe("useProgressPanel", () => {
  it("offers no way to open while there is no panel", () => {
    const { result } = renderHook(() => useProgressPanel(null));

    expect(result.current.open).toBe(false);
    expect(result.current.openPanel).toBeUndefined();
  });

  it("opens on request once there is a panel", () => {
    const { result } = renderHook(() => useProgressPanel(withPremise));

    act(() => result.current.openPanel?.());

    expect(result.current.open).toBe(true);
  });

  it("does not reopen by itself in the next session", () => {
    const { result, rerender } = renderHook(
      ({ progress }) => useProgressPanel(progress),
      { initialProps: { progress: withPremise as LearningProgress | null } },
    );
    act(() => result.current.openPanel?.());

    rerender({ progress: null });
    rerender({ progress: withPremise });

    expect(result.current.open).toBe(false);
  });
});
