import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoteCollectionPicker } from "@/components/notes/note-collection-picker";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const fetchAPI = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchAPI: (...args: unknown[]) => fetchAPI(...args),
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

const COLLECTIONS = {
  collections: [
    {
      id: "c1",
      name: "Linuxのしくみ",
      note_count: 2,
      created_at: "",
      updated_at: "",
    },
  ],
};

beforeEach(() => {
  refresh.mockReset();
  fetchAPI.mockReset();
  fetchAPI.mockImplementation((path: string) =>
    path === "/api/collections"
      ? Promise.resolve(COLLECTIONS)
      : Promise.resolve(undefined),
  );
});

describe("NoteCollectionPicker", () => {
  it("offers the suggestion and joins the existing collection with the same name", async () => {
    render(
      <NoteCollectionPicker
        noteId="n1"
        collectionId={null}
        suggestedCollection="Linuxのしくみ"
      />,
    );

    expect(
      await screen.findByText("「Linuxのしくみ」にまとめますか？"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "入れる" }));

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1/collection", {
        method: "PUT",
        body: JSON.stringify({ collection_id: "c1" }),
      }),
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("creates a new collection when the suggestion is a new name", async () => {
    render(
      <NoteCollectionPicker
        noteId="n1"
        collectionId={null}
        suggestedCollection="詳解 システム・パフォーマンス"
      />,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "入れる" }),
    );

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1/collection", {
        method: "PUT",
        body: JSON.stringify({
          new_collection_name: "詳解 システム・パフォーマンス",
        }),
      }),
    );
  });

  it("dismisses the suggestion", async () => {
    render(
      <NoteCollectionPicker
        noteId="n1"
        collectionId={null}
        suggestedCollection="Linuxのしくみ"
      />,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "入れない" }),
    );

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith(
        "/api/notes/n1/collection-suggestion",
        { method: "DELETE" },
      ),
    );
  });

  it("shows the current collection as a link", async () => {
    render(
      <NoteCollectionPicker
        noteId="n1"
        collectionId="c1"
        suggestedCollection={null}
      />,
    );

    const link = await screen.findByRole("link", { name: "Linuxのしくみ" });
    expect(link).toHaveAttribute("href", "/collections/c1");
  });

  it("removes the note from its collection", async () => {
    render(
      <NoteCollectionPicker
        noteId="n1"
        collectionId="c1"
        suggestedCollection={null}
      />,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "テーマを変更" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "テーマから外す" }),
    );

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1/collection", {
        method: "PUT",
        body: JSON.stringify({}),
      }),
    );
  });

  it("creates a collection from the typed name", async () => {
    render(
      <NoteCollectionPicker
        noteId="n1"
        collectionId={null}
        suggestedCollection={null}
      />,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "テーマに入れる" }),
    );
    await userEvent.type(screen.getByLabelText("新しいテーマ名"), "OS入門");
    await userEvent.click(
      screen.getByRole("button", { name: "作成して入れる" }),
    );

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1/collection", {
        method: "PUT",
        body: JSON.stringify({ new_collection_name: "OS入門" }),
      }),
    );
  });

  it("shows the name of a theme created from the suggestion", async () => {
    const created = {
      collections: [
        ...COLLECTIONS.collections,
        {
          id: "c2",
          name: "新しいテーマ",
          note_count: 1,
          created_at: "",
          updated_at: "",
        },
      ],
    };
    let isCreated = false;
    fetchAPI.mockImplementation(
      (path: string, options?: { method?: string }) => {
        if (options?.method === "PUT") {
          isCreated = true;
          return Promise.resolve(undefined);
        }
        return Promise.resolve(isCreated ? created : COLLECTIONS);
      },
    );
    const { rerender } = render(
      <NoteCollectionPicker
        noteId="n1"
        collectionId={null}
        suggestedCollection="新しいテーマ"
      />,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "入れる" }),
    );
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    rerender(
      <NoteCollectionPicker
        noteId="n1"
        collectionId="c2"
        suggestedCollection={null}
      />,
    );

    expect(
      await screen.findByRole("link", { name: "新しいテーマ" }),
    ).toHaveAttribute("href", "/collections/c2");
  });
});
