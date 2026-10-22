import { describe, it, expect } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { NoteFeedbackCard } from "@/components/notes/note-feedback-card";
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

  it("shows the headline and keeps the detail folded until it is opened", () => {
    const withHeadline: Feedback = {
      ...LATEST,
      improvement_items: [
        {
          headline: "再帰と反復はどう違う？",
          text: "再帰と反復の違いを確認する",
          aspect_id: "a1",
        },
      ],
    };
    render(
      <NoteFeedbackPanel
        noteId="n1"
        feedbacks={[withHeadline]}
        aspectMap={MAP}
        studyMemos={[]}
      />,
    );
    const latest = screen.getByRole("article");
    const detail = within(latest).getByText("再帰と反復の違いを確認する");
    const disclosure = detail.closest("details");
    expect(disclosure).not.toHaveAttribute("open");
    expect(detail).not.toBeVisible();
    expect(
      within(disclosure as HTMLElement)
        .getByText("再帰と反復はどう違う？")
        .closest("summary"),
    ).not.toBeNull();
    expect(
      within(latest).getByRole("link", { name: "観点: 計算量" }),
    ).toBeVisible();
    expect(
      within(latest).getByRole("link", { name: "AIと理解する" }),
    ).toBeVisible();
  });

  it("shows the whole text for feedback without a headline", () => {
    render(
      <NoteFeedbackPanel noteId="n1" feedbacks={[LATEST]} studyMemos={[]} />,
    );
    const text = within(screen.getByRole("article")).getByText(
      "再帰と反復の違いを確認する",
    );
    expect(text.closest("details")).toBeNull();
  });

  it("offers AIと理解する on each improvement of the latest feedback only", () => {
    render(
      <NoteFeedbackPanel
        noteId="n1"
        feedbacks={[FIRST, LATEST]}
        studyMemos={[]}
      />,
    );
    const latest = screen.getByRole("article");
    expect(
      within(latest).getByRole("link", { name: "AIと理解する" }),
    ).toHaveAttribute("href", "/learn?mode=explore&note=n1&feedback=f2&item=0");
    const history = screen.getByRole("region", { name: "これまでの評価" });
    expect(
      within(history).queryByRole("link", { name: "AIと理解する" }),
    ).not.toBeInTheDocument();
    expect(
      within(latest).getAllByRole("link", { name: "AIと理解する" }),
    ).toHaveLength(1);
  });

  it("gives the understand link a tappable area on touch devices", () => {
    render(
      <NoteFeedbackPanel noteId="n1" feedbacks={[LATEST]} studyMemos={[]} />,
    );
    const link = screen.getAllByRole("link", { name: "AIと理解する" })[0];
    expect(link).toHaveClass("pointer-coarse:min-h-11");
  });

  it("shows no understand links without studyMemos", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[LATEST]} />);
    expect(
      screen.queryByRole("link", { name: "AIと理解する" }),
    ).not.toBeInTheDocument();
  });

  it("links to the existing memo and offers もう一度理解する when a memo exists", () => {
    render(
      <NoteFeedbackPanel
        noteId="n1"
        feedbacks={[LATEST]}
        studyMemos={[
          {
            id: "m9",
            topic: "再帰",
            created_at: "2026-06-06T00:00:00Z",
            feedback_id: "f2",
            improvement_index: 0,
            improvement: null,
            aspect_id: null,
          },
        ]}
      />,
    );
    expect(
      screen.getByRole("link", { name: "学習メモを見る" }),
    ).toHaveAttribute("href", "/study-memos/m9");
    expect(
      screen.getByRole("link", { name: "もう一度理解する" }),
    ).toHaveAttribute("href", "/learn?mode=explore&note=n1&feedback=f2&item=0");
    expect(
      screen.queryByRole("link", { name: "AIと理解する" }),
    ).not.toBeInTheDocument();
  });
});

describe("NoteFeedbackCard review results", () => {
  const results: NonNullable<Feedback["review_results"]> = [
    {
      point_id: "p1",
      point: "要点A",
      question: "問いA",
      status: "not_explained",
    },
    {
      point_id: "p2",
      point: "要点B",
      question: "問いB",
      status: "explained_with_hint",
      aspect_id: "a1",
    },
  ];
  const MAP: AspectMap = {
    root: "二分探索",
    aspects: [{ id: "a1", name: "計算量", summary: "", coverage: "covered" }],
  };

  it("shows each review result with question, point and status", () => {
    render(
      <NoteFeedbackCard
        feedback={{ ...LATEST, review_results: results }}
        aspectMap={MAP}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "要点ごとの結果" }),
    ).toBeInTheDocument();
    expect(screen.getByText("問いA")).toBeInTheDocument();
    expect(screen.getByText("要点A")).toBeInTheDocument();
    expect(screen.getByText("説明できなかった")).toBeInTheDocument();
    expect(screen.getByText("ヒントで説明できた")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /計算量/ })).toHaveAttribute(
      "href",
      "#aspect-a1",
    );
  });

  it.each([null, undefined, []])(
    "hides the result list when review_results is %j",
    (review_results) => {
      render(<NoteFeedbackCard feedback={{ ...LATEST, review_results }} />);
      expect(
        screen.queryByRole("heading", { name: "要点ごとの結果" }),
      ).not.toBeInTheDocument();
    },
  );
});

describe("NoteFeedbackHistory review results", () => {
  const older: Feedback = {
    ...FIRST,
    session_type: "review",
    review_results: [
      {
        point_id: "p1",
        point: "前回の要点",
        question: "前回の問い",
        status: "not_explained",
      },
    ],
  };
  const latest: Feedback = {
    ...LATEST,
    review_results: [
      {
        point_id: "p1",
        point: "今回の要点",
        question: "今回の問い",
        status: "explained",
      },
    ],
  };

  it("shows the per-point results of an older review", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[older, latest]} />);
    const history = screen.getByRole("region", { name: "これまでの評価" });
    expect(
      within(history).getByRole("heading", {
        name: "要点ごとの結果",
        level: 4,
        hidden: true,
      }),
    ).toBeInTheDocument();
    expect(within(history).getByText("前回の問い")).toBeInTheDocument();
    expect(within(history).getByText("前回の要点")).toBeInTheDocument();
    expect(within(history).queryByText("今回の問い")).not.toBeInTheDocument();
  });

  it("gives each result list its own heading id", () => {
    const { container } = render(
      <NoteFeedbackPanel noteId="n1" feedbacks={[older, latest]} />,
    );
    const headings = screen.getAllByRole("heading", {
      name: "要点ごとの結果",
      hidden: true,
    });
    expect(headings).toHaveLength(2);
    expect(new Set(headings.map((h) => h.id)).size).toBe(2);
    for (const heading of headings) {
      expect(
        container.querySelector(`[aria-labelledby="${heading.id}"]`),
      ).not.toBeNull();
    }
  });

  it("shows no result list for older evaluations without results", () => {
    render(<NoteFeedbackPanel noteId="n1" feedbacks={[FIRST, latest]} />);
    const history = screen.getByRole("region", { name: "これまでの評価" });
    expect(
      within(history).queryByRole("heading", {
        name: "要点ごとの結果",
        hidden: true,
      }),
    ).not.toBeInTheDocument();
  });
});
