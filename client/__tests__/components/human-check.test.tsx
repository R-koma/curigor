import { act, render } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/script", () => ({
  default: ({ onReady }: { onReady?: () => void }) => {
    onReady?.();
    return null;
  },
}));

import {
  HumanCheck,
  type HumanCheckHandle,
  TOKEN_TIMEOUT_MS,
} from "@/components/auth/human-check";

type Options = Record<string, (...args: unknown[]) => unknown> & {
  sitekey?: unknown;
};

function fakeTurnstile() {
  let options: Options = {};
  const turnstile = {
    render: vi.fn((_el: HTMLElement, opts: Options) => {
      options = opts;
      return "widget-1";
    }),
    execute: vi.fn(),
    reset: vi.fn(),
    remove: vi.fn(),
  };
  return { turnstile, options: () => options };
}

let fake: ReturnType<typeof fakeTurnstile>;

beforeEach(() => {
  fake = fakeTurnstile();
  window.turnstile = fake.turnstile;
});

afterEach(() => {
  delete window.turnstile;
  vi.useRealTimers();
});

function renderCheck() {
  const ref = createRef<HumanCheckHandle>();
  const view = render(<HumanCheck ref={ref} siteKey="site-key" />);
  return { ref, ...view };
}

describe("HumanCheck", () => {
  it("renders the widget to run only on request and only show itself when needed", () => {
    renderCheck();
    expect(fake.turnstile.render).toHaveBeenCalledTimes(1);
    expect(fake.options()).toMatchObject({
      sitekey: "site-key",
      execution: "execute",
      appearance: "interaction-only",
    });
  });

  it("resolves the token Turnstile returns", async () => {
    const { ref } = renderCheck();
    const token = ref.current!.getToken();
    expect(fake.turnstile.execute).toHaveBeenCalledWith("widget-1");
    act(() => {
      fake.options().callback("token-1");
    });
    await expect(token).resolves.toBe("token-1");
  });

  it("resets the widget before asking for another token", async () => {
    const { ref } = renderCheck();
    const first = ref.current!.getToken();
    act(() => {
      fake.options().callback("token-1");
    });
    await first;
    expect(fake.turnstile.reset).not.toHaveBeenCalled();

    const second = ref.current!.getToken();
    expect(fake.turnstile.reset).toHaveBeenCalledWith("widget-1");
    act(() => {
      fake.options().callback("token-2");
    });
    await expect(second).resolves.toBe("token-2");
  });

  it("rejects when Turnstile reports an error", async () => {
    const { ref } = renderCheck();
    const token = ref.current!.getToken();
    act(() => {
      fake.options()["error-callback"]();
    });
    await expect(token).rejects.toThrow();
  });

  it("rejects when no token arrives in time", async () => {
    vi.useFakeTimers();
    const { ref } = renderCheck();
    const token = ref.current!.getToken();
    const assertion = expect(token).rejects.toThrow("timed out");
    act(() => {
      vi.advanceTimersByTime(TOKEN_TIMEOUT_MS);
    });
    await assertion;
  });

  it("rejects when the script has not loaded", async () => {
    delete window.turnstile;
    const { ref } = renderCheck();
    await expect(ref.current!.getToken()).rejects.toThrow("not ready");
  });

  it("removes the widget on unmount", () => {
    const { unmount } = renderCheck();
    unmount();
    expect(fake.turnstile.remove).toHaveBeenCalledWith("widget-1");
  });
});
