import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import {
  VoiceWaveform,
  WAVEFORM_BAR_COUNT,
} from "@/components/chat/voice-waveform";

class FakeResizeObserver {
  static callback: ResizeObserverCallback | null = null;
  static disconnected = false;

  constructor(callback: ResizeObserverCallback) {
    FakeResizeObserver.callback = callback;
    FakeResizeObserver.disconnected = false;
  }

  observe() {}

  disconnect() {
    FakeResizeObserver.disconnected = true;
  }
}

function resizeTo(width: number) {
  act(() => {
    FakeResizeObserver.callback?.(
      [{ contentRect: { width } } as ResizeObserverEntry],
      {} as ResizeObserver,
    );
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeResizeObserver.callback = null;
});

describe("VoiceWaveform", () => {
  it("draws the newest levels last, scaled by loudness", () => {
    render(<VoiceWaveform history={[0, 0.5, 1]} />);

    const waveform = screen.getByRole("img", { name: "音声の波形" });
    const bars = Array.from(waveform.children) as HTMLElement[];
    expect(bars).toHaveLength(WAVEFORM_BAR_COUNT);
    expect(bars[bars.length - 1].style.height).toBe("100%");
    expect(bars[bars.length - 2].style.height).toBe("50%");
    expect(bars[0].style.height).toBe("12%");
  });

  it("lines the bars up against the right edge", () => {
    render(<VoiceWaveform history={[]} />);

    expect(screen.getByRole("img", { name: "音声の波形" })).toHaveClass(
      "justify-end",
    );
  });

  it("dims the bars where nothing was heard", () => {
    render(<VoiceWaveform history={[0, 1]} />);

    const bars = Array.from(
      screen.getByRole("img", { name: "音声の波形" }).children,
    ) as HTMLElement[];
    expect(bars[bars.length - 2]).toHaveClass("bg-foreground/30");
    expect(bars[bars.length - 1]).toHaveClass("bg-foreground/70");
  });

  it("fades out toward the left edge", () => {
    render(<VoiceWaveform history={[]} />);

    expect(screen.getByRole("img", { name: "音声の波形" }).className).toContain(
      "mask-image",
    );
  });

  it("fills the available width with as many bars as fit", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    render(<VoiceWaveform history={[]} />);

    resizeTo(102);

    const waveform = screen.getByRole("img", { name: "音声の波形" });
    expect(waveform.children).toHaveLength(20);

    resizeTo(502);

    expect(waveform.children).toHaveLength(100);
  });

  it("always draws at least one bar", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    render(<VoiceWaveform history={[]} />);

    resizeTo(0);

    expect(
      screen.getByRole("img", { name: "音声の波形" }).children,
    ).toHaveLength(1);
  });

  it("stops observing when it unmounts", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    const { unmount } = render(<VoiceWaveform history={[]} />);

    unmount();

    expect(FakeResizeObserver.disconnected).toBe(true);
  });
});
