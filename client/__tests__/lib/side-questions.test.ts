import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchAPI } from "@/lib/api";
import {
  fetchSideQuestions,
  parseNdjson,
  streamNewSideQuestion,
  streamSideFollowUp,
  type SideStreamEvent,
} from "@/lib/side-questions";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  fetchAPI: vi.fn(),
  getToken: vi.fn(async () => "tok"),
}));

function streamOf(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  });
}

const encode = (text: string) => new TextEncoder().encode(text);

async function collect<T>(gen: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const item of gen) out.push(item);
  return out;
}

describe("parseNdjson", () => {
  it("reads a line split across two chunks", async () => {
    const lines = await collect(
      parseNdjson(streamOf([encode('{"type":"ch'), encode('unk"}\n')])),
    );
    expect(lines).toEqual([{ type: "chunk" }]);
  });

  it("reads two lines in one chunk", async () => {
    const lines = await collect(
      parseNdjson(streamOf([encode('{"a":1}\n{"a":2}\n')])),
    );
    expect(lines).toEqual([{ a: 1 }, { a: 2 }]);
  });

  it("reads a last line without a trailing newline", async () => {
    const lines = await collect(
      parseNdjson(streamOf([encode('{"a":1}\n{"a":2}')])),
    );
    expect(lines).toEqual([{ a: 1 }, { a: 2 }]);
  });

  it("reads a UTF-8 character split at a chunk boundary", async () => {
    const bytes = encode('{"content":"索引"}\n');
    const cut = bytes.indexOf(0xe7) + 1;
    const lines = await collect(
      parseNdjson(streamOf([bytes.slice(0, cut), bytes.slice(cut)])),
    );
    expect(lines).toEqual([{ content: "索引" }]);
  });
});

describe("side question requests", () => {
  beforeEach(() => {
    vi.mocked(fetchAPI).mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps the listed side questions to camel case", async () => {
    vi.mocked(fetchAPI).mockResolvedValue({
      side_questions: [
        {
          id: "q1",
          parent_id: null,
          anchor_message_id: "m1",
          anchor_side_message_id: null,
          quote: "索引",
          occurrence: 1,
          depth: 0,
          messages: [{ id: "u1", role: "user", content: "索引とは？" }],
        },
      ],
    });

    const threads = await fetchSideQuestions("s1");

    expect(fetchAPI).toHaveBeenCalledWith(
      "/api/dialogue-sessions/s1/side-questions",
    );
    expect(threads).toEqual([
      {
        id: "q1",
        parentId: null,
        anchorMessageId: "m1",
        anchorSideMessageId: null,
        quote: "索引",
        occurrence: 1,
        depth: 0,
        messages: [{ id: "u1", role: "user", content: "索引とは？" }],
      },
    ]);
  });

  it("streams events of a new side question", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: streamOf([
        encode(
          '{"type":"started","side_question_id":"q1","user_message_id":"u1","answer_message_id":"a1"}\n{"type":"chunk","content":"答"}\n{"type":"end"}\n',
        ),
      ]),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const events: SideStreamEvent[] = await collect(
      streamNewSideQuestion("s1", {
        anchorMessageId: "m1",
        quote: "索引",
        occurrence: 0,
        content: "索引とは？",
      }),
    );

    expect(events).toEqual([
      {
        type: "started",
        sideQuestionId: "q1",
        userMessageId: "u1",
        answerMessageId: "a1",
      },
      { type: "chunk", content: "答" },
      { type: "end" },
    ]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toMatch(/\/api\/dialogue-sessions\/s1\/side-questions$/);
    expect(JSON.parse(String(init.body))).toEqual({
      anchor_message_id: "m1",
      anchor_side_message_id: null,
      quote: "索引",
      occurrence: 0,
      content: "索引とは？",
    });
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer tok",
    );
  });

  it("throws an ApiError with the code on a 4xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        body: null,
        json: async () => ({ code: "session_not_active", detail: "ended" }),
      })),
    );

    const gen = streamSideFollowUp("q1", "続き");

    await expect(gen.next()).rejects.toMatchObject({
      status: 409,
      code: "session_not_active",
    });
    await expect(
      collect(streamSideFollowUp("q1", "続き")),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
