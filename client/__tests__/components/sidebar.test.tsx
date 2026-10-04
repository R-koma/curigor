import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "@/components/layout/sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/layout/sidebar-calendar", () => ({
  SidebarCalendar: () => <div data-testid="sidebar-calendar" />,
}));

vi.mock("@/hooks/use-sidebar-width", () => ({
  useSidebarWidth: () => ({
    width: 256,
    isResizing: false,
    startResize: vi.fn(),
  }),
}));

describe("Sidebar", () => {
  it("expands as soon as the trigger icon is hovered, and collapses when the pointer leaves, without pinning", async () => {
    render(<Sidebar />);

    // 折り畳み時はタイトル文言そのものは描画されない（ナブのラベルはツールチップとして常駐する）
    expect(screen.queryByText("Curigor")).not.toBeInTheDocument();

    const trigger = screen.getByLabelText("サイドバーを開く");
    const rail = trigger.closest("aside");
    expect(rail).not.toBeNull();

    fireEvent.mouseEnter(trigger);
    // 開始の遅延はなく即座にマウントされる（見た目のトランジションのみゆっくり）
    expect(screen.getByText("Curigor")).toBeInTheDocument();

    fireEvent.mouseLeave(rail!);
    await waitFor(() => {
      expect(screen.queryByText("Curigor")).not.toBeInTheDocument();
    });
  });

  it("links to the collections page right after the history link", () => {
    render(<Sidebar />);

    const hrefs = screen
      .getAllByRole("link")
      .map((a) => a.getAttribute("href"));
    expect(hrefs.indexOf("/collections")).toBe(hrefs.indexOf("/notes") + 1);
  });

  it("does not expand when hovering elsewhere on the collapsed rail", () => {
    render(<Sidebar />);

    fireEvent.mouseEnter(screen.getByRole("link", { name: "新規" }));
    // トリガーはアイコンのみなので、他のナブ項目をホバーしても開かない
    expect(screen.queryByText("Curigor")).not.toBeInTheDocument();
  });

  it("keeps content mounted for a grace period after the pointer leaves, canceling the close if re-hovered", async () => {
    render(<Sidebar />);

    const trigger = screen.getByLabelText("サイドバーを開く");
    const rail = trigger.closest("aside");
    fireEvent.mouseEnter(trigger);
    expect(await screen.findByText("Curigor")).toBeInTheDocument();

    fireEvent.mouseLeave(rail!);
    // 閉じ待機中はまだマウントされたまま(フェードアウト中)
    expect(screen.getByText("Curigor")).toBeInTheDocument();

    fireEvent.mouseEnter(rail!);
    // 待機中に再ホバーしたので、閉じ待機(350ms)を過ぎても残り続ける
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(screen.getByText("Curigor")).toBeInTheDocument();
  });

  it("pins the sidebar open via the toggle button revealed while hovering, and it stays open after the pointer leaves", async () => {
    const user = userEvent.setup();
    render(<Sidebar />);

    const trigger = screen.getByLabelText("サイドバーを開く");
    const rail = trigger.closest("aside");
    fireEvent.mouseEnter(trigger);
    await screen.findByText("Curigor");

    const pinButton = await screen.findByLabelText("サイドバーを開く", {
      selector: "button",
    });
    await user.click(pinButton);
    expect(
      await screen.findByLabelText("サイドバーを閉じる"),
    ).toBeInTheDocument();

    fireEvent.mouseLeave(rail!);
    await new Promise((resolve) => setTimeout(resolve, 300));
    expect(screen.getByText("Curigor")).toBeInTheDocument();
  });

  it("pins instantly, without the width transition, when clicked while the hover overlay is already open", async () => {
    render(<Sidebar />);

    const trigger = screen.getByLabelText("サイドバーを開く");
    const rail = trigger.closest("aside")!;
    fireEvent.mouseEnter(trigger);
    const pinButton = await screen.findByLabelText("サイドバーを開く", {
      selector: "button",
    });

    fireEvent.click(pinButton);

    // すでにオーバーレイで全幅表示中だったため、56pxへ戻ってから再度広がるアニメーションは起きない
    expect(rail.className).not.toMatch(/transition-\[width\]/);
    expect(
      await screen.findByLabelText("サイドバーを閉じる"),
    ).toBeInTheDocument();
  });

  it("closes immediately when the close button is clicked, even while the pointer is still hovering it", async () => {
    render(<Sidebar />);

    const trigger = screen.getByLabelText("サイドバーを開く");
    fireEvent.mouseEnter(trigger);
    const pinButton = await screen.findByLabelText("サイドバーを開く", {
      selector: "button",
    });
    fireEvent.click(pinButton);

    const closeButton = await screen.findByLabelText("サイドバーを閉じる");
    // ホバーを外していない状態でクリックする（isHovering が残っていても即座に閉じる想定）
    fireEvent.click(closeButton);

    expect(screen.queryByText("Curigor")).not.toBeInTheDocument();
  });

  it("does not reopen from a phantom re-hover on the trigger that reappears at the same spot after closing", async () => {
    render(<Sidebar />);

    const trigger = screen.getByLabelText("サイドバーを開く");
    const rail = trigger.closest("aside")!;
    fireEvent.mouseEnter(trigger);
    const pinButton = await screen.findByLabelText("サイドバーを開く", {
      selector: "button",
    });
    fireEvent.click(pinButton);
    const closeButton = await screen.findByLabelText("サイドバーを閉じる");
    fireEvent.click(closeButton);

    // 閉じるボタンが消え、同じ位置に折り畳み時のトリガーが現れる。カーソルはまだそこに
    // 乗ったままという想定（実マウスではブラウザがここで再ホバーを検知することがある）
    const reappearedTrigger = screen.getByLabelText("サイドバーを開く");
    fireEvent.mouseEnter(reappearedTrigger);
    expect(screen.queryByText("Curigor")).not.toBeInTheDocument();

    // 実際にカーソルが離れれば、以後は通常どおりホバーで開けるようになる
    fireEvent.mouseLeave(rail);
    fireEvent.mouseEnter(reappearedTrigger);
    expect(await screen.findByText("Curigor")).toBeInTheDocument();
  });

  it("stays open after hovering away once pinned via the toggle button", async () => {
    const user = userEvent.setup();
    render(<Sidebar />);

    const trigger = screen.getByLabelText("サイドバーを開く");
    const rail = trigger.closest("aside");
    await user.click(trigger);
    expect(await screen.findByText("Curigor")).toBeInTheDocument();

    fireEvent.mouseLeave(rail!);
    expect(screen.getByText("Curigor")).toBeInTheDocument();
  });
});
