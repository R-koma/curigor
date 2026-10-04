import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { InboxIcon } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { Spinner } from "@/components/ui/spinner";

describe("Spinner", () => {
  it("is decorative by default", () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveClass("motion-safe:animate-spin", "size-4");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it.each([
    ["sm", "size-3.5"],
    ["md", "size-4"],
    ["lg", "size-8"],
  ] as const)("%s uses %s", (size, className) => {
    const { container } = render(<Spinner size={size} />);
    expect(container.querySelector("svg")).toHaveClass(className);
  });

  it("announces itself when given a label", () => {
    render(<Spinner label="読み込み中" />);
    expect(
      screen.getByRole("status", { name: "読み込み中" }),
    ).toBeInTheDocument();
  });
});

describe("LoadingOverlay", () => {
  it("shows the message in a status region above the page", () => {
    render(<LoadingOverlay message="ノート作成中..." />);
    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("ノート作成中...");
    expect(region).toHaveClass("fixed", "inset-0", "z-overlay");
  });
});

describe("EmptyState", () => {
  it("renders the title only", () => {
    render(<EmptyState title="該当するノートがありません" />);
    expect(screen.getByText("該当するノートがありません")).toBeInTheDocument();
  });

  it("renders the icon, description and action", () => {
    const { container } = render(
      <EmptyState
        icon={InboxIcon}
        title="まだありません"
        description="ここから作れます"
        action={<button type="button">作る</button>}
      />,
    );
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    expect(screen.getByText("ここから作れます")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "作る" })).toBeInTheDocument();
  });

  it("lets the caller override the spacing", () => {
    const { container } = render(<EmptyState title="空" className="py-8" />);
    expect(container.firstChild).toHaveClass("py-8");
    expect(container.firstChild).not.toHaveClass("py-20");
  });
});
