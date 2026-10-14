import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SessionHeader } from "@/components/chat/session-header";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const PROGRESS = {
  reached_aspects: ["A"],
  target_count: 3,
  is_complete: false,
  aspects: [{ name: "A", is_core: true, reached_stage: "defined" as const }],
};

describe("SessionHeader", () => {
  it("offers a way back to the dashboard that is hidden from md", () => {
    render(
      <SessionHeader topic="再帰" endLabel="ノートを作成" onEnd={vi.fn()} />,
    );
    const back = screen.getByRole("link", { name: "ダッシュボードへ戻る" });
    expect(back).toHaveAttribute("href", "/dashboard");
    expect(back.className).toContain("md:hidden");
  });

  it("renders the progress pill once, so its popover is not duplicated", () => {
    render(
      <SessionHeader
        topic="再帰"
        progress={PROGRESS}
        endLabel="ノートを作成"
        onEnd={vi.fn()}
      />,
    );
    expect(
      screen.getAllByRole("button", { name: "観点ごとの到達度を表示" }),
    ).toHaveLength(1);
    expect(screen.getByText("1/3")).toBeInTheDocument();
  });

  it("collapses the end button to its icon below md, and labels it when highlighted", () => {
    const { rerender } = render(
      <SessionHeader topic="再帰" endLabel="ノートを作成" onEnd={vi.fn()} />,
    );
    expect(screen.getByText("ノートを作成").className).toContain("sr-only");
    rerender(
      <SessionHeader
        topic="再帰"
        endLabel="ノートを作成"
        endHighlighted
        onEnd={vi.fn()}
      />,
    );
    expect(screen.getByText("ノートを作成").className).not.toContain("sr-only");
  });

  it("puts the advance notice and the reconnecting indicator under the row below md", () => {
    render(
      <SessionHeader
        topic="再帰"
        progress={PROGRESS}
        notice="「A」を説明できました"
        isReconnecting
        endLabel="ノートを作成"
        onEnd={vi.fn()}
      />,
    );
    const strip = screen.getByTestId("session-status");
    expect(strip.className).toContain("absolute");
    expect(strip.className).toContain("md:contents");
    expect(strip).toHaveTextContent("「A」を説明できました");
    expect(strip).toHaveTextContent("再接続中");
  });

  it("shows the leading icon and the badge around the topic", () => {
    render(
      <SessionHeader
        topic="再帰"
        leading={<span data-testid="leading" />}
        badge={<span>復習</span>}
        endLabel="ノートを更新"
        onEnd={vi.fn()}
      />,
    );
    expect(screen.getByTestId("leading")).toBeInTheDocument();
    expect(screen.getByText("復習")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "再帰" })).toBeInTheDocument();
  });
});
