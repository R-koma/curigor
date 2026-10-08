import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import NotePage from "@/app/(main)/notes/[id]/page";

vi.mock("next/headers", () => ({
  headers: async () => new Headers(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/components/notes/note-header", () => ({ NoteHeader: () => null }));
vi.mock("@/components/notes/note-collection-picker", () => ({
  NoteCollectionPicker: () => null,
}));
vi.mock("@/components/notes/note-edit-form", () => ({
  NoteEditForm: () => <div>edit form</div>,
}));
vi.mock("@/components/notes/note-feedback-summary", () => ({
  NoteFeedbackSummary: () => null,
}));
vi.mock("@/lib/api", () => ({
  getToken: async () => "token",
  fetchAPI: vi.fn(async (path: string) => {
    if (path.endsWith("/feedbacks")) {
      return {
        feedbacks: [
          {
            id: "f1",
            understanding_level: "low",
            strength: "",
            improvements: "計算量の見積もり",
            improvement_items: [{ text: "計算量の見積もり", aspect_id: "a1" }],
            session_type: "learning",
            created_at: "2026-06-01T00:00:00Z",
          },
        ],
      };
    }
    if (path.endsWith("/revisions")) return { revisions: [] };
    if (path.endsWith("/links")) return { links: [] };
    return {
      id: "n1",
      topic: "二分探索",
      content: "本文",
      summary: "要約",
      status: "active",
      category: null,
      collection_id: null,
      suggested_collection: null,
      aspect_map: {
        root: "二分探索",
        aspects: [
          { id: "a1", name: "計算量", summary: "", coverage: "partial" },
        ],
      },
      intake: null,
      created_at: "2026-06-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
      review_count: 0,
    };
  }),
}));

async function renderPage(edit?: string) {
  render(
    await NotePage({
      params: Promise.resolve({ id: "n1" }),
      searchParams: Promise.resolve({ edit }),
    }),
  );
}

describe("NotePage aspect links", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("links an improvement to its aspect while viewing", async () => {
    await renderPage();
    expect(screen.getByRole("link", { name: "観点: 計算量" })).toHaveAttribute(
      "href",
      "#aspect-a1",
    );
    expect(document.querySelector("#aspect-a1")).not.toBeNull();
  });

  it("shows no aspect link while editing, since the aspect map is hidden", async () => {
    await renderPage("1");
    expect(screen.getByText("edit form")).toBeInTheDocument();
    expect(screen.getByText("計算量の見積もり")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /観点:/ }),
    ).not.toBeInTheDocument();
  });
});
