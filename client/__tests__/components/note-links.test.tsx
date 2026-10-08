import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoteLinks } from "@/components/notes/note-links";
import type { NoteLink } from "@/lib/note-links";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const fetchAPI = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchAPI: (...args: unknown[]) => fetchAPI(...args),
}));

const toastError = vi.fn();
vi.mock("sonner", () => ({
  toast: { error: (...args: unknown[]) => toastError(...args) },
}));

function link(overrides: Partial<NoteLink> & { id: string }): NoteLink {
  return {
    status: "suggested",
    similarity: 0.7,
    note: {
      id: `note-${overrides.id}`,
      topic: "スケーリング",
      summary: "垂直・水平スケーリングの基本",
      collection_id: "c1",
      collection_name: "システムデザイン",
    },
    ...overrides,
  };
}

beforeEach(() => {
  refresh.mockReset();
  fetchAPI.mockReset();
  fetchAPI.mockResolvedValue(undefined);
  toastError.mockReset();
});

describe("NoteLinks", () => {
  it("renders nothing without links", () => {
    const { container } = render(<NoteLinks noteId="n1" links={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a suggestion with its collection, summary and a link to the note", () => {
    render(<NoteLinks noteId="n1" links={[link({ id: "l1" })]} />);

    expect(screen.getByText("つながりの候補")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "スケーリング" })).toHaveAttribute(
      "href",
      "/notes/note-l1",
    );
    expect(screen.getByText("システムデザイン")).toBeInTheDocument();
    expect(
      screen.getByText("垂直・水平スケーリングの基本"),
    ).toBeInTheDocument();
  });

  it("accepts a suggestion and refreshes the page", async () => {
    render(<NoteLinks noteId="n1" links={[link({ id: "l1" })]} />);

    await userEvent.click(screen.getByRole("button", { name: "つなげる" }));

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1/links/l1", {
        method: "PUT",
        body: JSON.stringify({ status: "accepted" }),
      }),
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("dismisses a suggestion", async () => {
    render(<NoteLinks noteId="n1" links={[link({ id: "l1" })]} />);

    await userEvent.click(screen.getByRole("button", { name: "つなげない" }));

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1/links/l1", {
        method: "PUT",
        body: JSON.stringify({ status: "dismissed" }),
      }),
    );
  });

  it("separates accepted links from suggestions and lets them be removed", async () => {
    render(
      <NoteLinks
        noteId="n1"
        links={[
          link({ id: "l1", status: "accepted" }),
          link({
            id: "l2",
            note: { ...link({ id: "l2" }).note, topic: "CORS" },
          }),
        ]}
      />,
    );

    const accepted = screen.getByText("つながっているノート").parentElement!;
    expect(within(accepted).getByText("スケーリング")).toBeInTheDocument();
    expect(within(accepted).queryByText("CORS")).not.toBeInTheDocument();

    await userEvent.click(
      within(accepted).getByRole("button", { name: "外す" }),
    );
    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1/links/l1", {
        method: "PUT",
        body: JSON.stringify({ status: "dismissed" }),
      }),
    );
  });

  it("tells the user when the update fails", async () => {
    fetchAPI.mockRejectedValue(new Error("boom"));
    render(<NoteLinks noteId="n1" links={[link({ id: "l1" })]} />);

    await userEvent.click(screen.getByRole("button", { name: "つなげる" }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(refresh).not.toHaveBeenCalled();
  });
});
