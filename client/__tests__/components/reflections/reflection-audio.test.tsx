import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  REFLECTION_LIMIT_MESSAGE,
  ReflectionAudio,
} from "@/components/reflections/reflection-audio";
import { SPEECH_FAILED_MESSAGE } from "@/hooks/use-speech-playback";
import { ApiError, fetchAPI } from "@/lib/api";

const playback = {
  unlock: vi.fn(),
  playAll: vi.fn(),
  stop: vi.fn(),
  hold: vi.fn(),
  release: vi.fn(),
  isSpeaking: false,
  error: null as string | null,
};

vi.mock("@/hooks/use-speech-playback", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/hooks/use-speech-playback")>();
  return { ...actual, useSpeechPlayback: () => playback };
});

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, fetchAPI: vi.fn() };
});

const mockFetch = vi.mocked(fetchAPI);

describe("ReflectionAudio", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    playback.isSpeaking = false;
    playback.error = null;
  });

  it("unlocks audio, fetches the script once and plays its sentences", async () => {
    mockFetch.mockResolvedValue({ sentences: ["一文目。", "二文目。"] });
    render(<ReflectionAudio period="day" start="2026-11-01" />);

    await userEvent.click(screen.getByRole("button", { name: "音声で聞く" }));

    expect(playback.unlock).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/reflections/day/2026-11-01/script",
      { method: "POST" },
    );
    await waitFor(() =>
      expect(playback.playAll).toHaveBeenCalledWith(
        "reflection:day:2026-11-01",
        ["一文目。", "二文目。"],
      ),
    );
  });

  it("shows a playback bar with a stop button while speaking", async () => {
    playback.isSpeaking = true;
    render(<ReflectionAudio period="day" start="2026-11-01" />);

    expect(
      screen.queryByRole("button", { name: "音声で聞く" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "停止" }));
    expect(playback.stop).toHaveBeenCalled();
  });

  it("pauses and resumes with hold and release", async () => {
    playback.isSpeaking = true;
    const { rerender } = render(
      <ReflectionAudio period="day" start="2026-11-01" />,
    );

    await userEvent.click(screen.getByRole("button", { name: "一時停止" }));
    expect(playback.hold).toHaveBeenCalledTimes(1);

    playback.isSpeaking = false;
    rerender(<ReflectionAudio period="day" start="2026-11-01" />);
    await userEvent.click(screen.getByRole("button", { name: "再開" }));
    expect(playback.release).toHaveBeenCalledTimes(1);
  });

  it("shows the reflection limit message on 429", async () => {
    mockFetch.mockRejectedValue(
      new ApiError(429, "daily_reflection_limit_reached", "limit"),
    );
    render(<ReflectionAudio period="day" start="2026-11-01" />);

    await userEvent.click(screen.getByRole("button", { name: "音声で聞く" }));

    expect(
      await screen.findByText(REFLECTION_LIMIT_MESSAGE),
    ).toBeInTheDocument();
    expect(playback.playAll).not.toHaveBeenCalled();
  });

  it("shows the speech failure message on 502", async () => {
    mockFetch.mockRejectedValue(
      new ApiError(502, "reflection_generation_failed", "failed"),
    );
    render(<ReflectionAudio period="day" start="2026-11-01" />);

    await userEvent.click(screen.getByRole("button", { name: "音声で聞く" }));

    expect(await screen.findByText(SPEECH_FAILED_MESSAGE)).toBeInTheDocument();
  });

  it("shows the playback error from the hook", () => {
    playback.error = "今日の読み上げの上限に達しました";
    render(<ReflectionAudio period="day" start="2026-11-01" />);
    expect(
      screen.getByText("今日の読み上げの上限に達しました"),
    ).toBeInTheDocument();
  });

  it("stops playback when the day changes", () => {
    const { rerender } = render(
      <ReflectionAudio period="day" start="2026-11-01" />,
    );
    playback.stop.mockClear();
    rerender(<ReflectionAudio period="day" start="2026-10-31" />);
    expect(playback.stop).toHaveBeenCalled();
  });

  it("ignores a script that arrives after the day changed", async () => {
    let resolve: (value: { sentences: string[] }) => void = () => undefined;
    mockFetch.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const { rerender } = render(
      <ReflectionAudio period="day" start="2026-11-01" />,
    );
    await userEvent.click(screen.getByRole("button", { name: "音声で聞く" }));
    expect(screen.getByRole("status", { name: "原稿を作成中" })).toBeVisible();

    rerender(<ReflectionAudio period="day" start="2026-10-31" />);
    await act(async () => resolve({ sentences: ["一文目。"] }));

    expect(playback.playAll).not.toHaveBeenCalled();
  });
});
