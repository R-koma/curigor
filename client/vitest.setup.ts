import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import {
  installMatchMedia,
  resetMediaQueries,
} from "./__tests__/stubs/match-media";

// アプリはルートに TooltipProvider を持つので、テストの render も同じ前提で描画する。
vi.mock("@testing-library/react", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@testing-library/react")>();
  const { TooltipProvider } = await import("@/components/ui/tooltip");
  return {
    ...actual,
    render: (
      ui: Parameters<typeof actual.render>[0],
      options?: Parameters<typeof actual.render>[1],
    ) => actual.render(ui, { wrapper: TooltipProvider, ...options }),
  };
});

// Radix UI (Tooltip/Popper) uses ResizeObserver internally; jsdom does not provide it.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// jsdom は matchMedia を持たない。既定はすべて不一致（PC・マウス）。
if (typeof window !== "undefined") installMatchMedia();

// Node 25+ ships a global localStorage that, without --localstorage-file, shadows jsdom's.
if (
  typeof window !== "undefined" &&
  typeof window.localStorage?.clear !== "function"
) {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key) => store.get(key) ?? null,
    key: (index) => [...store.keys()][index] ?? null,
    removeItem: (key) => {
      store.delete(key);
    },
    setItem: (key, value) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: storage,
    configurable: true,
  });
  Object.defineProperty(window, "localStorage", {
    value: storage,
    configurable: true,
  });
}

afterEach(() => {
  cleanup();
  resetMediaQueries();
});
