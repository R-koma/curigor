import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAccountActions } from "@/hooks/use-account-actions";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  deleteUser: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));
vi.mock("sonner", () => ({
  toast: { success: mocks.success, error: mocks.error },
}));
vi.mock("@/context/usage-hints-context", () => ({
  useUsageHints: () => ({ reset: vi.fn() }),
}));
vi.mock("@/lib/auth-client", () => ({
  authClient: { deleteUser: mocks.deleteUser, signOut: vi.fn() },
}));

beforeEach(() => vi.clearAllMocks());

describe("deleteAccount", () => {
  it("goes to sign-in after deleting", async () => {
    mocks.deleteUser.mockResolvedValue({
      data: { success: true },
      error: null,
    });
    const { result } = renderHook(() => useAccountActions());

    expect(await result.current.deleteAccount()).toBe(true);
    expect(mocks.success).toHaveBeenCalledWith("アカウントを削除しました");
    expect(mocks.push).toHaveBeenCalledWith("/sign-in");
  });

  it("asks to sign in again when the session is too old", async () => {
    mocks.deleteUser.mockResolvedValue({
      data: null,
      error: { code: "SESSION_EXPIRED", status: 400 },
    });
    const { result } = renderHook(() => useAccountActions());

    expect(await result.current.deleteAccount()).toBe(false);
    expect(mocks.error).toHaveBeenCalledWith(
      "安全のため、ログインし直してから削除してください",
    );
    expect(mocks.push).not.toHaveBeenCalled();
  });

  it.each([
    [
      "an error response",
      () =>
        mocks.deleteUser.mockResolvedValue({
          data: null,
          error: { status: 500 },
        }),
    ],
    [
      "a network failure",
      () => mocks.deleteUser.mockRejectedValue(new TypeError("fetch failed")),
    ],
  ])("reports %s", async (_, arrange) => {
    arrange();
    const { result } = renderHook(() => useAccountActions());

    expect(await result.current.deleteAccount()).toBe(false);
    expect(mocks.error).toHaveBeenCalledWith(
      "削除できませんでした。もう一度お試しください",
    );
    expect(mocks.push).not.toHaveBeenCalled();
  });
});
