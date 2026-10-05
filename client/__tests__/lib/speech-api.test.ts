import { afterEach, describe, expect, it, vi } from "vitest";
import { SpeechError, streamSpeech } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("streamSpeech", () => {
  it("posts the speed and returns the body stream", async () => {
    const body = new ReadableStream<Uint8Array>();
    const fetchMock = vi.fn(async () => new Response(body));
    vi.stubGlobal("fetch", fetchMock);
    const signal = new AbortController().signal;

    const stream = await streamSpeech("s-1", "あ。", 1.25, signal, "token");

    expect(stream).toBeInstanceOf(ReadableStream);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(String(url)).toMatch(/\/api\/speech$/);
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer token",
    );
    expect(JSON.parse(init.body as string)).toEqual({
      text: "あ。",
      dialogue_session_id: "s-1",
      speed: 1.25,
    });
    expect(init.signal).toBe(signal);
  });

  it("throws SpeechError with the status on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 429 })),
    );
    const call = streamSpeech("s-1", "あ。", 1, undefined, "token");
    await expect(call).rejects.toMatchObject({
      name: "SpeechError",
      status: 429,
    });
    await expect(call).rejects.toBeInstanceOf(SpeechError);
  });
});
