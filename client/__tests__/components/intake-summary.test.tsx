import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { IntakeSummarySection } from "@/components/chat/intake-summary";

describe("IntakeSummarySection", () => {
  it("lists the answered premise under fixed labels", () => {
    render(
      <IntakeSummarySection
        intake={{
          purpose: "基礎知識を身につける",
          source: "入門書",
          prior_knowledge: "初めて学ぶ",
        }}
      />,
    );

    const section = screen.getByRole("region", { name: "学習の前提" });
    expect(within(section).getByText("目的")).toBeInTheDocument();
    expect(
      within(section).getByText("基礎知識を身につける"),
    ).toBeInTheDocument();
    expect(within(section).getByText("教材")).toBeInTheDocument();
    expect(within(section).getByText("入門書")).toBeInTheDocument();
    expect(within(section).getByText("今の理解")).toBeInTheDocument();
    expect(within(section).getByText("初めて学ぶ")).toBeInTheDocument();
  });

  it("omits rows that were skipped", () => {
    render(
      <IntakeSummarySection
        intake={{ purpose: "", source: "入門書", prior_knowledge: "" }}
      />,
    );

    expect(screen.queryByText("目的")).not.toBeInTheDocument();
    expect(screen.queryByText("今の理解")).not.toBeInTheDocument();
    expect(screen.getByText("入門書")).toBeInTheDocument();
  });

  it("is display only", () => {
    render(
      <IntakeSummarySection
        intake={{ purpose: "仕事で使う", source: "", prior_knowledge: "" }}
      />,
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
