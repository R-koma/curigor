import { describe, expect, it, vi } from "vitest";
import { createSegmentedTranscriber } from "@/lib/stt/segmented";
import type { TranscriptSegment } from "@/lib/stt/types";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup() {
  const calls: { wav: Blob; result: ReturnType<typeof deferred<string>> }[] =
    [];
  const changes: TranscriptSegment[][] = [];
  const onError = vi.fn();
  const transcriber = createSegmentedTranscriber({
    transcribe: (wav) => {
      const result = deferred<string>();
      calls.push({ wav, result });
      return result.promise;
    },
    onChange: (segments) => changes.push(segments),
    onError,
  });
  return { transcriber, calls, changes, onError };
}

describe("createSegmentedTranscriber", () => {
  it("encodes the pre-roll and pushed audio as one WAV per segment", async () => {
    const { transcriber, calls } = setup();
    transcriber.begin(new Float32Array(160));
    transcriber.push(new Float32Array(320));
    const ended = transcriber.end();

    expect(calls).toHaveLength(1);
    expect(calls[0].wav.type).toBe("audio/wav");
    expect(calls[0].wav.size).toBe(44 + 480 * 2);
    expect(transcriber.segments()).toEqual([
      { id: 1, text: "", status: "pending" },
    ]);

    calls[0].result.resolve("半分です");
    await ended;
    expect(transcriber.segments()).toEqual([
      { id: 1, text: "半分です", status: "done" },
    ]);
  });

  it("keeps segment order when later segments finish first", async () => {
    const { transcriber, calls } = setup();
    transcriber.begin(new Float32Array(10));
    const first = transcriber.end();
    transcriber.begin(new Float32Array(10));
    const second = transcriber.end();

    calls[1].result.resolve("以上");
    await second;
    calls[0].result.resolve("半分です");
    await first;

    expect(transcriber.segments().map((s) => s.text)).toEqual([
      "半分です",
      "以上",
    ]);
  });

  it("marks a failed segment and reports the error", async () => {
    const { transcriber, calls, onError } = setup();
    transcriber.begin(new Float32Array(10));
    const ended = transcriber.end();
    const error = new Error("boom");
    calls[0].result.reject(error);
    await ended;

    expect(transcriber.segments()[0].status).toBe("failed");
    expect(onError).toHaveBeenCalledWith(error);
  });

  it("ignores results that arrive after reset", async () => {
    const { transcriber, calls } = setup();
    transcriber.begin(new Float32Array(10));
    const ended = transcriber.end();
    transcriber.reset();
    calls[0].result.resolve("遅れて届いた");
    await ended;

    expect(transcriber.segments()).toEqual([]);
  });

  it("settled waits for every pending segment", async () => {
    const { transcriber, calls } = setup();
    transcriber.begin(new Float32Array(10));
    void transcriber.end();
    let settled = false;
    void transcriber.settled().then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);
    calls[0].result.resolve("半分");
    await transcriber.settled();
    expect(settled).toBe(true);
  });

  it("does nothing on end without begin", async () => {
    const { transcriber, calls } = setup();
    await transcriber.end();
    expect(calls).toHaveLength(0);
  });
});
