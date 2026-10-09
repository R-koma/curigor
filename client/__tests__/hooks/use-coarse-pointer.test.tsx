import { describe, it, expect } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useCoarsePointer } from "@/hooks/use-coarse-pointer";
import { COARSE_POINTER, setMediaQuery } from "../stubs/match-media";

describe("useCoarsePointer", () => {
  it("is false on a fine pointer (the default)", () => {
    const { result } = renderHook(() => useCoarsePointer());
    expect(result.current).toBe(false);
  });

  it("is true when the primary pointer is coarse", () => {
    setMediaQuery(COARSE_POINTER, true);
    const { result } = renderHook(() => useCoarsePointer());
    expect(result.current).toBe(true);
  });

  it("follows a change of the media query", () => {
    const { result } = renderHook(() => useCoarsePointer());
    expect(result.current).toBe(false);
    act(() => setMediaQuery(COARSE_POINTER, true));
    expect(result.current).toBe(true);
  });
});
