import { describe, it, expect, vi, beforeEach } from "vitest";
import { loadResumableMessages, isResumableStatus } from "@/lib/session";
import { fetchAPI, fetchImageObjectURL } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  fetchAPI: vi.fn(),
  fetchImageObjectURL: vi.fn(),
}));

const mockFetchAPI = vi.mocked(fetchAPI);
const mockFetchImageObjectURL = vi.mocked(fetchImageObjectURL);

describe("isResumableStatus", () => {
  it("treats in_progress and disconnect as resumable", () => {
    expect(isResumableStatus("in_progress")).toBe(true);
    expect(isResumableStatus("disconnect")).toBe(true);
  });

  it("rejects terminal statuses", () => {
    expect(isResumableStatus("completed")).toBe(false);
    expect(isResumableStatus("abandoned")).toBe(false);
    expect(isResumableStatus("failed")).toBe(false);
  });
});

describe("loadResumableMessages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps session metadata and text messages", async () => {
    mockFetchAPI.mockResolvedValue({
      session_id: "s1",
      session_type: "review",
      status: "in_progress",
      note_id: "n1",
      messages: [
        { role: "user", content: "hi", message_order: 1, images: [] },
        { role: "assistant", content: "hello", message_order: 2, images: [] },
      ],
    });

    const result = await loadResumableMessages("s1");

    expect(result.sessionType).toBe("review");
    expect(result.status).toBe("in_progress");
    expect(result.noteId).toBe("n1");
    expect(result.messages).toEqual([
      { role: "user", content: "hi", images: undefined },
      { role: "assistant", content: "hello", images: undefined },
    ]);
    expect(mockFetchImageObjectURL).not.toHaveBeenCalled();
  });

  it("converts attached images to authenticated object URLs", async () => {
    mockFetchAPI.mockResolvedValue({
      session_id: "s1",
      session_type: "learning",
      status: "disconnect",
      note_id: null,
      messages: [
        {
          role: "user",
          content: "see this",
          message_order: 1,
          images: [{ id: "img1", mime_type: "image/png", image_order: 0 }],
        },
      ],
    });
    mockFetchImageObjectURL.mockResolvedValue("blob:obj-url");

    const result = await loadResumableMessages("s1");

    expect(mockFetchImageObjectURL).toHaveBeenCalledWith(
      "/api/dialogue-sessions/s1/images/img1",
    );
    expect(result.messages[0].images).toEqual([{ url: "blob:obj-url" }]);
  });

  it("returns the session topic and restores intake cards", async () => {
    const card = {
      questions: [
        {
          key: "source",
          header: "教材",
          question: "q",
          options: [{ label: "書籍", description: "" }],
          multi_select: true,
          preselected: [],
        },
      ],
    };
    mockFetchAPI.mockResolvedValue({
      session_id: "s1",
      session_type: "learning",
      status: "in_progress",
      note_id: null,
      topic: "React Hooks",
      messages: [
        {
          role: "user",
          content: "Reactのフック",
          message_order: 1,
          images: [],
          intake_card: null,
        },
        {
          role: "assistant",
          content: "lead",
          message_order: 2,
          images: [],
          intake_card: card,
        },
      ],
    });

    const result = await loadResumableMessages("s1");

    expect(result.topic).toBe("React Hooks");
    expect(result.messages[0].intakeCard).toBeUndefined();
    expect(result.messages[1].intakeCard).toEqual(card);
  });
});
