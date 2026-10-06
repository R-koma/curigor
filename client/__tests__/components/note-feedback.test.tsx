import { describe, it, expect } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { NoteFeedbackPanel } from "@/components/notes/note-feedback-panel";
import type { AspectMap } from "@/lib/aspect-map";
import type { Feedback } from "@/lib/feedback";

const FIRST: Feedback = {
  id: "f1",
  understanding_level: "low",
  strength: "・用語を自分の言葉で言い換えられた",
  improvements: "・計算量の見積もりが曖昧",
  session_type: "learning",
  created_at: "2026-06-01T00:00:00Z",
};

const LATEST: Feedback = {
  id: "f2",
  understanding_level: "high",
  strength: "・計算量を O(log n) と説明できた",
  improvements: "・再帰と反復の違いを確認する",
  session_type: "review",
  created_at: "2026-06-05T00:00:00Z",
};

describe("NoteFeedbackPanel", () => {
  it("explains how to get feedback when there is none", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[]} />);
    expect(
      screen.getByText("フィードバックはまだありません"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("復習を終えると、理解度と改善点がここに表示されます。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "復習する" })).toHaveAttribute(
      "href",
      "/review/n1",
    );
  });

  it("shows the latest evaluation with its date and source", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[FIRST, LATEST]} />);
    const latest = screen.getByRole("article");
    expect(within(latest).getByText("理解度: 高")).toBeInTheDocument();
    expect(within(latest).getByText("2026年6月5日 の復習")).toBeInTheDocument();
    expect(
      within(latest).getByRole("heading", { name: "強み" }),
    ).toBeInTheDocument();
    expect(
      within(latest).getByText("計算量を O(log n) と説明できた"),
    ).toBeInTheDocument();
  });

  it("lists older evaluations under これまでの評価", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[FIRST, LATEST]} />);
    const history = screen.getByRole("region", { name: "これまでの評価" });
    expect(
      within(history).getByText("2026年6月1日 の学習"),
    ).toBeInTheDocument();
    expect(within(history).getByText("理解度: 低")).toBeInTheDocument();
    expect(
      within(history).getByText("計算量の見積もりが曖昧"),
    ).toBeInTheDocument();
  });

  it("omits the history and the source label when not available", () => {
    render(
      <NoteFeedbackPanel
        noteId="n1"
        feedbacks={[{ ...LATEST, session_type: null }]}
      />,
    );
    expect(
      screen.queryByRole("region", { name: "これまでの評価" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("2026年6月5日")).toBeInTheDocument();
  });
});

describe("NoteFeedbackPanel review link", () => {
  it("links the latest improvements to a review of this note", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[FIRST, LATEST]} />);
    const link = screen.getByRole("link", { name: "復習する" });
    expect(link).toHaveAttribute("href", "/review/n1");
    expect(
      screen.getByText("次の復習では、この改善点を重点的に確認します。"),
    ).toBeInTheDocument();
  });

  it("offers no review link when the latest has no improvements", () => {
    render(
      <NoteFeedbackPanel
        noteId="n1"
        feedbacks={[FIRST, { ...LATEST, improvements: "" }]}
      />,
    );
    expect(
      screen.queryByRole("link", { name: "復習する" }),
    ).not.toBeInTheDocument();
  });
});

describe("NoteFeedbackPanel update notice", () => {
  it("shows the notice on the latest card when just updated", () => {
    render(
      <NoteFeedbackPanel noteId="n1" feedbacks={[FIRST, LATEST]} justUpdated />,
    );
    expect(
      within(screen.getByRole("article")).getByRole("status"),
    ).toBeInTheDocument();
  });

  it("shows no notice when there is no feedback", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[]} justUpdated />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("NoteFeedbackCard criteria", () => {
  it("explains what each understanding level means", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[LATEST]} />);
    expect(screen.getByText("理解度の基準")).toBeInTheDocument();
    expect(
      screen.getByText(/具体例や応用にも触れられている/),
    ).toBeInTheDocument();
  });

  it("still renders an unknown level", () => {
    render(
      <NoteFeedbackPanel
        noteId="n1"
        feedbacks={[{ ...LATEST, understanding_level: "unknown" }]}
      />,
    );
    expect(screen.getByText("理解度: unknown")).toBeInTheDocument();
    expect(screen.getByText("理解度の基準")).toBeInTheDocument();
  });
});

describe("NoteFeedbackPanel aspect links", () => {
  const MAP: AspectMap = {
    root: "二分探索",
    aspects: [{ id: "a1", name: "計算量", summary: "", coverage: "partial" }],
  };

  it("links an improvement to its aspect in the aspect map", () => {
    const linked: Feedback = {
      ...LATEST,
      improvements: "再帰と反復の違いを確認する",
      improvement_items: [
        { text: "再帰と反復の違いを確認する", aspect_id: "a1" },
      ],
    };
    render(
      <NoteFeedbackPanel noteId="n1" feedbacks={[linked]} aspectMap={MAP} />,
    );
    expect(screen.getByRole("link", { name: "観点: 計算量" })).toHaveAttribute(
      "href",
      "#aspect-a1",
    );
  });

  it("shows no aspect link for older feedback or a note without an aspect map", () => {
    const linked: Feedback = {
      ...LATEST,
      improvement_items: [
        { text: "再帰と反復の違いを確認する", aspect_id: "a1" },
      ],
    };
    render(
      <NoteFeedbackPanel noteId="n1" feedbacks={[LATEST]} aspectMap={MAP} />,
    );
    expect(
      screen.queryByRole("link", { name: /観点:/ }),
    ).not.toBeInTheDocument();
    cleanup();
    render(
      <NoteFeedbackPanel noteId="n1" feedbacks={[linked]} aspectMap={null} />,
    );
    expect(
      screen.queryByRole("link", { name: /観点:/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("再帰と反復の違いを確認する")).toBeInTheDocument();
  });

  it("links improvements in the older evaluations too", () => {
    const older: Feedback = {
      ...FIRST,
      improvement_items: [{ text: "計算量の見積もりが曖昧", aspect_id: "a1" }],
    };
    render(
      <NoteFeedbackPanel
        noteId="n1"
        feedbacks={[older, LATEST]}
        aspectMap={MAP}
      />,
    );
    const history = screen.getByRole("region", { name: "これまでの評価" });
    expect(
      within(history).getByRole("link", { name: "観点: 計算量", hidden: true }),
    ).toHaveAttribute("href", "#aspect-a1");
  });
});
