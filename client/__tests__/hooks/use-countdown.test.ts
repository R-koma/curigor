import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCountdown } from "@/hooks/use-countdown";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useCountdown", () => {
  it("starts at zero", () => {
    const { result } = renderHook(() => useCountdown(60));
    expect(result.current.remaining).toBe(0);
  });

  it("counts down once a second after restart and stops at zero", () => {
    const { result } = renderHook(() => useCountdown(3));
    act(() => result.current.restart());
    expect(result.current.remaining).toBe(3);
    for (const expected of [2, 1, 0, 0]) {
      act(() => vi.advanceTimersByTime(1000));
      expect(result.current.remaining).toBe(expected);
    }
  });

  it("restarts from the full length", () => {
    const { result } = renderHook(() => useCountdown(60));
    act(() => result.current.restart());
    act(() => vi.advanceTimersByTime(10_000));
    act(() => result.current.restart());
    expect(result.current.remaining).toBe(60);
  });

  it("stops its timer on unmount", () => {
    const { result, unmount } = renderHook(() => useCountdown(60));
    act(() => result.current.restart());
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("catches up when the page was suspended and becomes visible again", () => {
    const { result } = renderHook(() => useCountdown(60));
    act(() => result.current.restart());
    act(() => {
      vi.setSystemTime(Date.now() + 30_000);
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(result.current.remaining).toBe(30);
  });

  it("removes its visibility listener on unmount", () => {
    const remove = vi.spyOn(document, "removeEventListener");
    const { unmount } = renderHook(() => useCountdown(60));
    unmount();
    expect(remove).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );
    remove.mockRestore();
  });
});
