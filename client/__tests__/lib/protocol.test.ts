import { afterEach, describe, expect, it, vi } from "vitest";
import { reloadForNewProtocol } from "@/lib/protocol";

afterEach(() => {
  sessionStorage.clear();
});

describe("reloadForNewProtocol", () => {
  it("reloads", () => {
    const reload = vi.fn();

    expect(reloadForNewProtocol(reload, 1_000_000)).toBe(true);

    expect(reload).toHaveBeenCalledOnce();
  });

  it("does not reload again within a minute", () => {
    const reload = vi.fn();
    reloadForNewProtocol(reload, 1_000_000);

    expect(reloadForNewProtocol(reload, 1_030_000)).toBe(false);
    expect(reloadForNewProtocol(reload, 1_061_000)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("does not reload when the storage is unavailable", () => {
    const reload = vi.fn();
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(reloadForNewProtocol(reload)).toBe(false);
    expect(reload).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});
