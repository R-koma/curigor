import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CollectionActions } from "@/components/collections/collection-actions";

const refresh = vi.fn();
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh, push }) }));

const fetchAPI = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchAPI: (...args: unknown[]) => fetchAPI(...args),
}));

const toastError = vi.fn();
vi.mock("sonner", () => ({ toast: { error: (m: string) => toastError(m) } }));

beforeEach(() => {
  refresh.mockReset();
  push.mockReset();
  fetchAPI.mockReset();
  toastError.mockReset();
});

describe("CollectionActions", () => {
  it("renames the collection", async () => {
    fetchAPI.mockResolvedValue(undefined);
    render(<CollectionActions collectionId="c1" name="A" />);

    await userEvent.click(screen.getByRole("button", { name: "名前を変更" }));
    const input = screen.getByLabelText("まとめノート名");
    await userEvent.clear(input);
    await userEvent.type(input, "B");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/collections/c1", {
        method: "PATCH",
        body: JSON.stringify({ name: "B" }),
      }),
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("tells the user when the name is taken", async () => {
    fetchAPI.mockRejectedValue(new Error("API error: 409"));
    render(<CollectionActions collectionId="c1" name="A" />);

    await userEvent.click(screen.getByRole("button", { name: "名前を変更" }));
    await userEvent.type(screen.getByLabelText("まとめノート名"), "2");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "同じ名前のまとめノートがあります",
      ),
    );
  });

  it("deletes the collection and returns to the list", async () => {
    fetchAPI.mockResolvedValue(undefined);
    render(<CollectionActions collectionId="c1" name="A" />);

    await userEvent.click(
      screen.getByRole("button", { name: "まとめノートを削除" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "削除する" }));

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/collections/c1", {
        method: "DELETE",
      }),
    );
    expect(push).toHaveBeenCalledWith("/collections");
  });
});
