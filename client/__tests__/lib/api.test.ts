import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchAPI,
  getToken,
  transcribeAudio,
  TranscriptionError,
} from "@/lib/api";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
});

describe("getToken", () => {
  it("returns token from auth endpoint", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token: "test-jwt" }),
    });

    const token = await getToken();
    expect(token).toBe("test-jwt");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/auth/token",
      { headers: undefined },
    );
  });

  it("forwards cookie header when provided", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token: "test-jwt" }),
    });

    await getToken("session=abc");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/auth/token",
      { headers: { Cookie: "session=abc" } },
    );
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });

    await expect(getToken()).rejects.toThrow("Token fetch failed: 401");
  });
});

describe("fetchAPI", () => {
  it("attaches Bearer token and Content-Type header", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ data: "test" }),
    });

    await fetchAPI("/api/notes", { token: "my-token" });

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/notes",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer my-token",
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("returns parsed JSON on success", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: 1, topic: "Test" }),
    });

    const result = await fetchAPI<{ id: number; topic: string }>(
      "/api/notes/1",
      { token: "t" },
    );
    expect(result).toEqual({ id: 1, topic: "Test" });
  });

  it("returns undefined for 204 No Content", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const result = await fetchAPI("/api/notes/1", {
      method: "DELETE",
      token: "t",
    });
    expect(result).toBeUndefined();
  });

  it("throws on error status", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });

    await expect(fetchAPI("/api/notes/999", { token: "t" })).rejects.toThrow(
      "API error: 404",
    );
  });

  it("fetches token automatically when not provided", async () => {
    // First call: getToken
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token: "auto-token" }),
    });
    // Second call: actual API request
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ notes: [] }),
    });

    await fetchAPI("/api/notes");

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch).toHaveBeenLastCalledWith(
      "http://localhost:8000/api/notes",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer auto-token",
        }),
      }),
    );
  });
});

describe("transcribeAudio", () => {
  it("posts the recording as multipart with the session id", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ text: "二分探索" }),
    });
    const recording = new Blob(["voice"], { type: "audio/webm;codecs=opus" });

    const text = await transcribeAudio("session-1", recording, "test-jwt");

    expect(text).toBe("二分探索");
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/transcriptions");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ Authorization: "Bearer test-jwt" });
    const form = init.body as FormData;
    expect(form.get("dialogue_session_id")).toBe("session-1");
    expect((form.get("audio") as File).name).toBe("recording.webm");
  });

  it("names mp4 recordings with the mp4 extension", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ text: "" }),
    });

    await transcribeAudio(
      "session-1",
      new Blob(["voice"], { type: "audio/mp4" }),
      "test-jwt",
    );

    const form = mockFetch.mock.calls[0][1].body as FormData;
    expect((form.get("audio") as File).name).toBe("recording.mp4");
  });

  it("sends WAV with a .wav name and the prompt", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ text: "以上" }),
    });

    await transcribeAudio(
      "s-1",
      new Blob([new Uint8Array(4)], { type: "audio/wav" }),
      "token",
      "「以上」で締めくくります",
    );

    const form = mockFetch.mock.calls[0][1].body as FormData;
    expect((form.get("audio") as File).name).toBe("recording.wav");
    expect(form.get("prompt")).toBe("「以上」で締めくくります");
  });

  it("throws TranscriptionError carrying the status", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 429 });

    const error = await transcribeAudio(
      "session-1",
      new Blob(["voice"], { type: "audio/webm" }),
      "test-jwt",
    ).catch((err: unknown) => err);

    expect(error).toBeInstanceOf(TranscriptionError);
    expect((error as TranscriptionError).status).toBe(429);
  });

  it("omits the session id before a session exists", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ text: "二分探索" }),
    });

    await transcribeAudio(
      null,
      new Blob(["voice"], { type: "audio/webm" }),
      "test-jwt",
    );

    const form = mockFetch.mock.calls[0][1].body as FormData;
    expect(form.has("dialogue_session_id")).toBe(false);
    expect(form.get("audio")).not.toBeNull();
  });
});
