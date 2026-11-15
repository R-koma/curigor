import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useDeferredDelete } from "@/hooks/use-deferred-delete";

interface ToastOptions {
  action: { label: string; onClick: () => void };
  onAutoClose: () => void;
  onDismiss: () => void;
}

const toastMock = vi.hoisted(() => {
  const fn = vi.fn() as ReturnType<typeof vi.fn> & {
    error: ReturnType<typeof vi.fn>;
    dismiss: ReturnType<typeof vi.fn>;
  };
  fn.error = vi.fn();
  fn.dismiss = vi.fn();
  return fn;
});
vi.mock("sonner", () => ({ toast: toastMock }));

const ITEMS = [{ session_id: "a" }, { session_id: "b" }, { session_id: "c" }];

function lastOptions(): ToastOptions {
  return toastMock.mock.calls.at(-1)![1] as ToastOptions;
}

describe("useDeferredDelete", () => {
  beforeEach(() => {
    toastMock.mockReset();
    toastMock.error.mockReset();
    toastMock.dismiss.mockReset();
  });

  it("hides the row and announces without calling remove yet", () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeferredDelete(ITEMS, remove));
    act(() => result.current.requestDelete(ITEMS[1], "トピック"));
    expect(result.current.visible.map((i) => i.session_id)).toEqual(["a", "c"]);
    expect(remove).not.toHaveBeenCalled();
    expect(toastMock.mock.calls[0][0]).toBe("「トピック」を削除しました");
    expect(lastOptions().action.label).toBe("元に戻す");
  });

  it("calls remove once when the toast closes by itself", async () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeferredDelete(ITEMS, remove));
    act(() => result.current.requestDelete(ITEMS[1], "t"));
    const options = lastOptions();
    await act(async () => {
      options.onAutoClose();
      options.onDismiss();
    });
    expect(remove).toHaveBeenCalledTimes(1);
    expect(remove).toHaveBeenCalledWith(ITEMS[1]);
    expect(result.current.visible.map((i) => i.session_id)).toEqual(["a", "c"]);
  });

  it("restores the row in place on undo and never calls remove", async () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeferredDelete(ITEMS, remove));
    act(() => result.current.requestDelete(ITEMS[1], "t"));
    const options = lastOptions();
    await act(async () => {
      options.action.onClick();
      options.onDismiss();
    });
    expect(result.current.visible.map((i) => i.session_id)).toEqual([
      "a",
      "b",
      "c",
    ]);
    expect(remove).not.toHaveBeenCalled();
  });

  it("drops pending deletions on unmount without calling remove", async () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const { result, unmount } = renderHook(() =>
      useDeferredDelete(ITEMS, remove),
    );
    act(() => result.current.requestDelete(ITEMS[1], "t"));
    const options = lastOptions();
    unmount();
    await act(async () => {
      options.onAutoClose();
      options.onDismiss();
    });
    expect(remove).not.toHaveBeenCalled();
  });

  it("brings the row back and reports when remove fails", async () => {
    const remove = vi.fn().mockRejectedValue(new Error("500"));
    const { result } = renderHook(() => useDeferredDelete(ITEMS, remove));
    act(() => result.current.requestDelete(ITEMS[1], "t"));
    await act(async () => {
      lastOptions().onAutoClose();
    });
    await waitFor(() =>
      expect(result.current.visible.map((i) => i.session_id)).toEqual([
        "a",
        "b",
        "c",
      ]),
    );
    expect(toastMock.error).toHaveBeenCalled();
  });
});
