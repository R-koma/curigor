import { describe, it, expect, vi, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useProgressAdvanceNotice } from "@/hooks/use-progress-advance-notice";
import type { LearningProgress } from "@/hooks/use-chat-websocket";
import type { MapStage } from "@/lib/progress";

const progressAt = (stage: MapStage | null): LearningProgress => ({
  reached_aspects: [],
  target_count: 1,
  is_complete: false,
  aspects: [{ name: "値の埋め込み方", is_core: true, reached_stage: stage }],
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useProgressAdvanceNotice", () => {
  it("stays silent on the first progress, then announces a rise and clears it", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ progress }) => useProgressAdvanceNotice(progress, 4000),
      { initialProps: { progress: progressAt(null) } },
    );
    expect(result.current).toBeNull();

    rerender({ progress: progressAt("defined") });
    expect(result.current).toBe(
      "値の埋め込み方: どういうものかを説明できました",
    );

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(result.current).toBeNull();
  });

  it("does not compare against a previous session after progress resets", () => {
    const { result, rerender } = renderHook(
      ({ progress }: { progress: LearningProgress | null }) =>
        useProgressAdvanceNotice(progress),
      {
        initialProps: { progress: progressAt(null) as LearningProgress | null },
      },
    );

    rerender({ progress: null });
    rerender({ progress: progressAt("reasoned") });

    expect(result.current).toBeNull();
  });

  it("drops a pending notice when progress resets to another session", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ progress }: { progress: LearningProgress | null }) =>
        useProgressAdvanceNotice(progress, 4000),
      {
        initialProps: { progress: progressAt(null) as LearningProgress | null },
      },
    );
    rerender({ progress: progressAt("defined") });
    expect(result.current).not.toBeNull();

    rerender({ progress: null });
    rerender({ progress: progressAt(null) });

    expect(result.current).toBeNull();
  });

  it("stays silent without aspects", () => {
    const legacy: LearningProgress = {
      reached_aspects: [],
      target_count: 3,
      is_complete: false,
    };
    const { result, rerender } = renderHook(
      ({ progress }) => useProgressAdvanceNotice(progress),
      { initialProps: { progress: legacy } },
    );
    rerender({ progress: { ...legacy, reached_aspects: ["計算量"] } });

    expect(result.current).toBeNull();
  });
});
