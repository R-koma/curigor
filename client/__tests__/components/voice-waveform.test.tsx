import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  VoiceWaveform,
  WAVEFORM_BAR_COUNT,
} from "@/components/chat/voice-waveform";

vi.mock("@/hooks/use-audio-levels", () => ({
  useAudioLevels: (_stream: MediaStream | null, count: number) =>
    Array.from({ length: count }, (_, i) => (i === count - 1 ? 1 : 0)),
}));

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
});
