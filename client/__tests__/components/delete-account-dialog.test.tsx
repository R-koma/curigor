import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DeleteAccountDialog } from "@/components/layout/delete-account-dialog";

async function typeEmail(email = "ryoma@example.com") {
  await userEvent.type(
    screen.getByLabelText(/メールアドレス（ryoma@example.com）を入力/),
    email,
  );
}

const mocks = vi.hoisted(() => ({ deleteAccount: vi.fn() }));

vi.mock("@/hooks/use-account-actions", () => ({
  useAccountActions: () => ({ deleteAccount: mocks.deleteAccount }),
}));

beforeEach(() => vi.clearAllMocks());

function renderDialog(onOpenChange = vi.fn()) {
  render(
    <DeleteAccountDialog
      email="ryoma@example.com"
      open
      onOpenChange={onOpenChange}
    />,
  );
  return onOpenChange;
}

describe("DeleteAccountDialog", () => {
  it("explains that everything is deleted for good", () => {
    renderDialog();
    expect(
      screen.getByRole("alertdialog", { name: "アカウントを削除しますか？" }),
    ).toHaveTextContent(
      "アカウントと、ノート・まとめノート・学習メモ・対話の履歴・画像がすべて削除されます。元に戻せません",
    );
  });

  it("does nothing on cancel", async () => {
    const onOpenChange = renderDialog();
    await userEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(mocks.deleteAccount).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("disables the buttons while deleting", async () => {
    let finish: (deleted: boolean) => void = () => {};
    mocks.deleteAccount.mockReturnValue(
      new Promise<boolean>((resolve) => (finish = resolve)),
    );
    const onOpenChange = renderDialog();
    await typeEmail();

    await userEvent.click(screen.getByRole("button", { name: "削除する" }));

    expect(screen.getByRole("button", { name: "削除する" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "キャンセル" })).toBeDisabled();
    expect(onOpenChange).not.toHaveBeenCalled();
    finish(false);
  });

  it("closes and lets the user retry after a failure", async () => {
    mocks.deleteAccount.mockResolvedValue(false);
    const onOpenChange = renderDialog();
    await typeEmail();

    await userEvent.click(screen.getByRole("button", { name: "削除する" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    const input = screen.getByLabelText(/メールアドレス/);
    expect(input).toBeEnabled();
    expect(input).toHaveValue("");
    await typeEmail();
    expect(screen.getByRole("button", { name: "削除する" })).toBeEnabled();
  });

  it("keeps delete disabled until the email address is typed", async () => {
    renderDialog();
    const remove = screen.getByRole("button", { name: "削除する" });
    expect(remove).toBeDisabled();

    await typeEmail("ryoma@example.co");
    expect(remove).toBeDisabled();
    await userEvent.click(remove);
    expect(mocks.deleteAccount).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText(/メールアドレス/), "m");
    expect(remove).toBeEnabled();
  });

  it("accepts the address regardless of case and surrounding spaces", async () => {
    renderDialog();
    await typeEmail(" Ryoma@Example.com ");
    expect(screen.getByRole("button", { name: "削除する" })).toBeEnabled();
  });

  it("clears the typed address when cancelled", async () => {
    const onOpenChange = renderDialog();
    await typeEmail();
    await userEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(screen.getByLabelText(/メールアドレス/)).toHaveValue("");
  });
});
