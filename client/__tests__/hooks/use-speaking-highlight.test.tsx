import { render, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSpeakingHighlight } from "@/hooks/use-speaking-highlight";
import type { SpokenSentence } from "@/hooks/use-speech-playback";

class FakeHighlight {
  ranges: Range[];
  constructor(...ranges: Range[]) {
    this.ranges = ranges;
  }
}

let registry: Map<string, FakeHighlight>;

beforeEach(() => {
  registry = new Map();
  vi.stubGlobal("CSS", { highlights: registry });
  vi.stubGlobal("Highlight", FakeHighlight);
});

afterEach(() => vi.unstubAllGlobals());

function messages() {
  return render(
    <div>
      <div data-speech-key="r1">
        <p>はい。</p>
        <p>次へ。</p>
        <p>はい。</p>
      </div>
    </div>,
  );
}

describe("useSpeakingHighlight", () => {
  it("highlights the sentence being read", () => {
    messages();

    renderHook(() =>
      useSpeakingHighlight({ key: "r1", index: 1, text: "次へ。" }),
    );

    expect(registry.get("speaking")?.ranges[0].toString()).toBe("次へ。");
  });

  it("moves to the later occurrence of a repeated sentence", () => {
    messages();
    const { rerender } = renderHook(
      ({ current }: { current: SpokenSentence | null }) =>
        useSpeakingHighlight(current),
      { initialProps: { current: { key: "r1", index: 0, text: "はい。" } } },
    );
    const first = registry.get("speaking")?.ranges[0].startContainer;

    rerender({ current: { key: "r1", index: 1, text: "次へ。" } });
    rerender({ current: { key: "r1", index: 2, text: "はい。" } });

    expect(registry.get("speaking")?.ranges[0].startContainer).not.toBe(first);
  });

  it("clears the highlight when nothing is being read", () => {
    messages();
    const { rerender } = renderHook(
      ({ current }: { current: SpokenSentence | null }) =>
        useSpeakingHighlight(current),
      {
        initialProps: {
          current: {
            key: "r1",
            index: 0,
            text: "はい。",
          } as SpokenSentence | null,
        },
      },
    );

    rerender({ current: null });

    expect(registry.has("speaking")).toBe(false);
  });

  it("does nothing when the message is not on screen", () => {
    renderHook(() =>
      useSpeakingHighlight({ key: "missing", index: 0, text: "はい。" }),
    );

    expect(registry.has("speaking")).toBe(false);
  });

  it("does nothing without the highlight API", () => {
    vi.stubGlobal("CSS", {});
    messages();

    expect(() =>
      renderHook(() =>
        useSpeakingHighlight({ key: "r1", index: 0, text: "はい。" }),
      ),
    ).not.toThrow();
  });
});
