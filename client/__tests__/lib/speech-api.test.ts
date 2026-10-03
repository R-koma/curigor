import { afterEach, describe, expect, it, vi } from "vitest";
import { SpeechError, synthesizeSpeech } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("synthesizeSpeech", () => {
  it("posts the text with the session id and returns the audio bytes", async () => {
    const bytes = new Uint8Array([1, 2, 3]).buffer;
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      arrayBuffer: async () => bytes,
    });
    vi.stubGlobal("fetch", fetchMock);
    const signal = new AbortController().signal;

    const result = await synthesizeSpeech("s-1", "こんにちは。", signal, "tok");

    expect(result).toBe(bytes);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/speech$/);
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(JSON.parse(init.body)).toEqual({
      text: "こんにちは。",
      dialogue_session_id: "s-1",
    });
    expect(init.signal).toBe(signal);
  });

  it("throws a SpeechError carrying the status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 429 }),
    );

    await expect(
      synthesizeSpeech("s-1", "x", undefined, "tok"),
    ).rejects.toMatchObject({ name: "SpeechError", status: 429 });
    await expect(
      synthesizeSpeech("s-1", "x", undefined, "tok"),
    ).rejects.toBeInstanceOf(SpeechError);
  });
});
