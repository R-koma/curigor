import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import {
  VoiceWaveform,
  WAVEFORM_BAR_COUNT,
} from "@/components/chat/voice-waveform";

vi.mock("@/hooks/use-audio-levels", () => ({
  useAudioLevels: (_stream: MediaStream | null, count: number) =>
    Array.from({ length: count }, (_, i) => (i === count - 1 ? 1 : 0)),
}));

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
  it("draws one bar per level, scaled by loudness", () => {
    render(<VoiceWaveform stream={null} />);

    const waveform = screen.getByRole("img", { name: "音声の波形" });
    const bars = Array.from(waveform.children) as HTMLElement[];
    expect(bars).toHaveLength(WAVEFORM_BAR_COUNT);
    expect(bars[bars.length - 1].style.height).toBe("100%");
    expect(bars[0].style.height).toBe("12%");
  });

  it("lines the bars up against the right edge, newest last", () => {
    render(<VoiceWaveform stream={null} />);

    const waveform = screen.getByRole("img", { name: "音声の波形" });
    expect(waveform).toHaveClass("justify-end");
    const bars = Array.from(waveform.children) as HTMLElement[];
    expect(bars[bars.length - 1].style.height).toBe("100%");
  });

  it("fills the available width with as many bars as fit", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    render(<VoiceWaveform stream={null} />);

    resizeTo(102);

    const waveform = screen.getByRole("img", { name: "音声の波形" });
    expect(waveform.children).toHaveLength(20);

    resizeTo(502);

    expect(waveform.children).toHaveLength(100);
  });

  it("always draws at least one bar", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    render(<VoiceWaveform stream={null} />);

    resizeTo(0);

    expect(
      screen.getByRole("img", { name: "音声の波形" }).children,
    ).toHaveLength(1);
  });

  it("stops observing when it unmounts", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    const { unmount } = render(<VoiceWaveform stream={null} />);

    unmount();

    expect(FakeResizeObserver.disconnected).toBe(true);
  });
});
