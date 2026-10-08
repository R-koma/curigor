import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NavbarTopic } from "@/components/chat/navbar-topic";

const toastError = vi.fn();
vi.mock("sonner", () => ({ toast: { error: (m: string) => toastError(m) } }));

const LONG_TOPIC =
  "オペレーティングシステムのプロセススケジューリングとコンテキストスイッチの仕組み";

beforeEach(() => {
  toastError.mockReset();
});

async function openEditorWith(value: string, onEdit = vi.fn(() => true)) {
  render(<NavbarTopic topic="TCP" onEdit={onEdit} />);
  await userEvent.click(screen.getByRole("button", { name: "トピックを編集" }));
  const input = screen.getByRole("textbox", { name: "学習トピック" });
  await userEvent.clear(input);
  await userEvent.type(input, value);
  return { input, onEdit };
}

describe("NavbarTopic", () => {
  it("renders the topic without a tooltip or title attribute", () => {
    render(<NavbarTopic topic={LONG_TOPIC} />);

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(LONG_TOPIC);
    expect(heading).not.toHaveAttribute("title");
    expect(heading).not.toHaveAttribute("tabindex");
  });
});

describe("NavbarTopic editing", () => {
  it("shows no edit button without onEdit", () => {
    render(<NavbarTopic topic="TCP" />);

    expect(
      screen.queryByRole("button", { name: "トピックを編集" }),
    ).not.toBeInTheDocument();
  });

  it("asks for confirmation before applying an edit", async () => {
    const { input, onEdit } = await openEditorWith("UDP");
    await userEvent.type(input, "{Enter}");

    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent("「TCP」から「UDP」に変更します");
    expect(dialog).toHaveTextContent("到達度はリセットされます");
    expect(onEdit).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "変更する" }));
    expect(onEdit).toHaveBeenCalledWith("UDP");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("TCP");
  });

  it("keeps the typed value when the confirmation is cancelled", async () => {
    const { input } = await openEditorWith("UDP");
    await userEvent.type(input, "{Enter}");

    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "キャンセル",
      }),
    );

    expect(screen.getByRole("textbox", { name: "学習トピック" })).toHaveValue(
      "UDP",
    );
  });

  it.each(["   ", " tcp "])("cannot save %j", async (value) => {
    await openEditorWith(value);

    expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
  });

  it("closes the editor on Escape", async () => {
    render(<NavbarTopic topic="TCP" onEdit={vi.fn(() => true)} />);
    await userEvent.click(
      screen.getByRole("button", { name: "トピックを編集" }),
    );

    await userEvent.keyboard("{Escape}");

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("TCP");
  });

  it("keeps the editor open and tells the user when the edit could not be sent", async () => {
    const { input } = await openEditorWith(
      "UDP",
      vi.fn(() => false),
    );
    await userEvent.type(input, "{Enter}");
    await userEvent.click(screen.getByRole("button", { name: "変更する" }));

    expect(toastError).toHaveBeenCalledWith(
      "接続が切れています。もう一度お試しください",
    );
    expect(screen.getByRole("textbox", { name: "学習トピック" })).toHaveValue(
      "UDP",
    );
  });

  it("returns to the heading when editing becomes unavailable", async () => {
    const { rerender } = render(
      <NavbarTopic topic="TCP" onEdit={vi.fn(() => true)} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "トピックを編集" }),
    );

    rerender(<NavbarTopic topic="TCP" />);

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("TCP");

    rerender(<NavbarTopic topic="TCP" onEdit={vi.fn(() => true)} />);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("does not reopen a stale confirmation after editing became unavailable", async () => {
    const { rerender } = render(
      <NavbarTopic topic="TCP" onEdit={vi.fn(() => true)} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "トピックを編集" }),
    );
    const input = screen.getByRole("textbox", { name: "学習トピック" });
    await userEvent.clear(input);
    await userEvent.type(input, "UDP{Enter}");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();

    rerender(<NavbarTopic topic="TCP" />);
    rerender(<NavbarTopic topic="TCP" onEdit={vi.fn(() => true)} />);
    await userEvent.click(
      screen.getByRole("button", { name: "トピックを編集" }),
    );

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("limits the topic to 60 characters", async () => {
    render(<NavbarTopic topic="TCP" onEdit={vi.fn(() => true)} />);
    await userEvent.click(
      screen.getByRole("button", { name: "トピックを編集" }),
    );

    expect(
      screen.getByRole("textbox", { name: "学習トピック" }),
    ).toHaveAttribute("maxLength", "60");
  });
});
