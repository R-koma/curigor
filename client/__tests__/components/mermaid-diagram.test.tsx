import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeProvider } from "next-themes";
import mermaid from "mermaid";
import { MermaidDiagram } from "@/components/ui/mermaid-diagram";

vi.mock("mermaid", () => ({
  default: { initialize: vi.fn(), render: vi.fn() },
}));

const FLOW = "graph TD\n  A --> B";

describe("MermaidDiagram", () => {
  beforeEach(() => {
    vi.mocked(mermaid.initialize).mockReset();
    vi.mocked(mermaid.render).mockReset();
  });

  it("shows a progress line while the diagram is being drawn", async () => {
    let finish: () => void = () => {};
    vi.mocked(mermaid.render).mockReturnValue(
      new Promise((resolve) => {
        finish = () =>
          resolve({ svg: "<svg></svg>", diagramType: "flowchart" });
      }),
    );
    render(<MermaidDiagram code={FLOW} />);

    expect(screen.getByText("図を描いています…")).toBeInTheDocument();
    await vi.waitFor(() => expect(mermaid.render).toHaveBeenCalled());
    finish();
    expect(await screen.findByRole("img", { name: "図" })).toBeInTheDocument();
  });

  it("inserts the drawn SVG with strict security", async () => {
    vi.mocked(mermaid.render).mockResolvedValue({
      svg: '<svg data-testid="flow"></svg>',
      diagramType: "flowchart",
    });
    render(<MermaidDiagram code={FLOW} />);

    expect(await screen.findByTestId("flow")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "図" })).toBeInTheDocument();
    expect(mermaid.render).toHaveBeenCalledWith(
      expect.stringMatching(/^mermaid-/),
      FLOW,
    );
    expect(mermaid.initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "default",
      }),
    );
  });

  it("falls back to the source when the diagram cannot be drawn", async () => {
    vi.mocked(mermaid.render).mockRejectedValue(new Error("Parse error"));
    render(<MermaidDiagram code={FLOW} />);

    expect(
      await screen.findByText("図を表示できませんでした"),
    ).toBeInTheDocument();
    expect(screen.getByText(/A --> B/).tagName).toBe("CODE");
    expect(screen.queryByText("図を描いています…")).toBeNull();
  });

  it("draws with the dark theme when the app is dark", async () => {
    vi.mocked(mermaid.render).mockResolvedValue({
      svg: "<svg></svg>",
      diagramType: "flowchart",
    });
    render(
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
        <MermaidDiagram code={FLOW} />
      </ThemeProvider>,
    );

    await screen.findByRole("img", { name: "図" });
    expect(mermaid.initialize).toHaveBeenCalledWith(
      expect.objectContaining({ theme: "dark" }),
    );
  });
});
