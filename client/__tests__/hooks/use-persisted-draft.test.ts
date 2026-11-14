import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { draftKey, usePersistedDraft } from "@/hooks/use-persisted-draft";

const S1 = "curigor:draft:session:s1";
const S2 = "curigor:draft:session:s2";

describe("usePersistedDraft", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("保存した文をキーが決まったときに戻す", () => {
    sessionStorage.setItem(S1, "書きかけ");
    const { result } = renderHook(() => usePersistedDraft(S1));
    expect(result.current[0]).toBe("書きかけ");
  });

  it("初回の描画で保存を消さない", () => {
    sessionStorage.setItem(S1, "書きかけ");
    renderHook(() => usePersistedDraft(S1));
    expect(sessionStorage.getItem(S1)).toBe("書きかけ");
  });

  it("入力すると保存し、空にすると消す", () => {
    const { result } = renderHook(() => usePersistedDraft(S1));
    act(() => result.current[1]("abc"));
    expect(sessionStorage.getItem(S1)).toBe("abc");
    act(() => result.current[1](""));
    expect(sessionStorage.getItem(S1)).toBeNull();
  });

  it("キーが null の間は保存しない", () => {
    const { result } = renderHook(() => usePersistedDraft(null));
    act(() => result.current[1]("abc"));
    expect(result.current[0]).toBe("abc");
    expect(sessionStorage.length).toBe(0);
  });

  it("null から決まったキーへ移ると保存した文を戻す", () => {
    sessionStorage.setItem(S1, "保存した文");
    const { result, rerender } = renderHook(
      ({ k }: { k: string | null }) => usePersistedDraft(k),
      { initialProps: { k: null as string | null } },
    );
    rerender({ k: S1 });
    expect(result.current[0]).toBe("保存した文");
  });

  it("null から決まったキーへ移るとき、打った文があればそれを残して保存する", () => {
    sessionStorage.setItem(S1, "古い文");
    const { result, rerender } = renderHook(
      ({ k }: { k: string | null }) => usePersistedDraft(k),
      { initialProps: { k: null as string | null } },
    );
    act(() => result.current[1]("打った文"));
    rerender({ k: S1 });
    expect(result.current[0]).toBe("打った文");
    expect(sessionStorage.getItem(S1)).toBe("打った文");
  });

  it("キーが変わったら新しいキーの値に置き換える", () => {
    const { result, rerender } = renderHook(
      ({ k }: { k: string | null }) => usePersistedDraft(k),
      { initialProps: { k: S1 as string | null } },
    );
    act(() => result.current[1]("一つ目"));
    rerender({ k: S2 });
    expect(result.current[0]).toBe("");
    expect(sessionStorage.getItem(S1)).toBe("一つ目");
    expect(sessionStorage.getItem(S2)).toBeNull();
  });

  it("persistOverride があればそれを保存する", () => {
    const { rerender } = renderHook(
      ({ o }: { o?: string }) => usePersistedDraft(S1, o),
      { initialProps: {} as { o?: string } },
    );
    rerender({ o: "声の文" });
    expect(sessionStorage.getItem(S1)).toBe("声の文");
    rerender({ o: undefined });
    expect(sessionStorage.getItem(S1)).toBeNull();
  });

  it("sessionStorage が例外を投げても落ちない", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const { result } = renderHook(() => usePersistedDraft(S1));
    act(() => result.current[1]("abc"));
    expect(result.current[0]).toBe("abc");
  });

  it("draftKey が決められたキーを返す", () => {
    expect(draftKey.start("learning")).toBe("curigor:draft:start:learning");
    expect(draftKey.start("explore")).toBe("curigor:draft:start:explore");
    expect(draftKey.session("s1")).toBe("curigor:draft:session:s1");
    expect(draftKey.side("t1")).toBe("curigor:draft:side:t1");
  });
});
