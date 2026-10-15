import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComposePreview } from "@/components/chat/compose-preview";

describe("ComposePreview", () => {
  it("shows how a formula will look", async () => {
    const { container } = render(<ComposePreview value="答えは $x^2$" />);

    expect(
      await screen.findByRole("region", { name: "表示の確認" }),
    ).toBeInTheDocument();
    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("shows an unfinished code block as code", async () => {
    const { container } = render(<ComposePreview value={"```py\nx = 1"} />);

    await screen.findByRole("region", { name: "表示の確認" });
    expect(container.querySelector("pre code")?.textContent).toContain("x = 1");
  });

  it("shows nothing for plain text", () => {
    render(<ComposePreview value="ただの文です" />);

    expect(screen.queryByRole("region", { name: "表示の確認" })).toBeNull();
  });

  it("skips the preview for a very long draft", () => {
    render(<ComposePreview value={`$x$\n${"a".repeat(20001)}`} />);

    expect(screen.queryByRole("region", { name: "表示の確認" })).toBeNull();
  });

  it("disappears as soon as the input is cleared", async () => {
    const { rerender } = render(<ComposePreview value="$x$" />);
    await screen.findByRole("region", { name: "表示の確認" });

    rerender(<ComposePreview value="" />);

    expect(screen.queryByRole("region", { name: "表示の確認" })).toBeNull();
  });
});
