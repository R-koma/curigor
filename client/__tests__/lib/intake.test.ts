import { describe, it, expect } from "vitest";
import {
  ALL_SKIPPED_TEXT,
  formatIntakeAnswers,
  initialSelections,
  isAnswered,
  toIntakeAnswers,
  toggleOption,
  type IntakeCard,
} from "@/lib/intake";

const card: IntakeCard = {
  questions: [
    {
      key: "purpose",
      header: "目的",
      question: "今回、何ができるようになりたいですか？",
      options: [
        { label: "仕事で使う", description: "" },
        { label: "面接対策", description: "" },
      ],
      multi_select: false,
      preselected: ["仕事で使う"],
    },
    {
      key: "source",
      header: "教材",
      question: "何を使って学びますか？",
      options: [
        { label: "書籍", description: "" },
        { label: "動画", description: "" },
      ],
      multi_select: true,
      preselected: [],
    },
    {
      key: "prior_knowledge",
      header: "今の理解",
      question: "今どのくらい知っていますか？",
      options: [{ label: "初めて学ぶ", description: "" }],
      multi_select: false,
      preselected: [],
    },
  ],
};

describe("initialSelections", () => {
  it("applies preselected labels", () => {
    const s = initialSelections(card);
    expect(s.purpose.selected).toEqual(["仕事で使う"]);
    expect(s.source.selected).toEqual([]);
  });
});

describe("toggleOption", () => {
  it("replaces the choice for single select and clears other/skip", () => {
    const q = card.questions[0];
    const next = toggleOption(
      q,
      {
        selected: ["仕事で使う"],
        other: "x",
        otherActive: true,
        skipped: true,
      },
      "面接対策",
    );
    expect(next).toEqual({
      selected: ["面接対策"],
      other: "x",
      otherActive: false,
      skipped: false,
    });
  });

  it("toggles for multi select", () => {
    const q = card.questions[1];
    const once = toggleOption(q, initialSelections(card).source, "書籍");
    const twice = toggleOption(q, once, "動画");
    const removed = toggleOption(q, twice, "書籍");
    expect(twice.selected).toEqual(["書籍", "動画"]);
    expect(removed.selected).toEqual(["動画"]);
  });
});

describe("toIntakeAnswers", () => {
  it("uses the other text for single select when active", () => {
    const s = initialSelections(card);
    s.purpose = {
      selected: [],
      other: "  社内勉強会で話す ",
      otherActive: true,
      skipped: false,
    };
    expect(toIntakeAnswers(card, s).purpose).toBe("社内勉強会で話す");
  });

  it("combines choices and other text for multi select", () => {
    const s = initialSelections(card);
    s.source = {
      selected: ["書籍"],
      other: "社内Wiki",
      otherActive: true,
      skipped: false,
    };
    expect(toIntakeAnswers(card, s).source).toEqual(["書籍", "社内Wiki"]);
  });

  it("returns empty values for skipped or empty-other questions", () => {
    const s = initialSelections(card);
    s.purpose = {
      selected: ["仕事で使う"],
      other: "",
      otherActive: false,
      skipped: true,
    };
    s.prior_knowledge = {
      selected: [],
      other: "   ",
      otherActive: true,
      skipped: false,
    };
    const a = toIntakeAnswers(card, s);
    expect(a.purpose).toBe("");
    expect(a.prior_knowledge).toBe("");
    expect(isAnswered(s.prior_knowledge)).toBe(false);
  });

  it("truncates other text to the server limit", () => {
    const s = initialSelections(card);
    s.purpose = {
      selected: [],
      other: "あ".repeat(250),
      otherActive: true,
      skipped: false,
    };
    expect(toIntakeAnswers(card, s).purpose).toHaveLength(200);
  });
});

describe("formatIntakeAnswers", () => {
  it("lists answered questions by header", () => {
    const text = formatIntakeAnswers(card, {
      purpose: "仕事で使う",
      source: ["書籍", "動画"],
      prior_knowledge: "",
    });
    expect(text).toBe("目的: 仕事で使う\n教材: 書籍、動画");
  });

  it("uses a fixed sentence when everything is skipped", () => {
    expect(
      formatIntakeAnswers(card, {
        purpose: "",
        source: [],
        prior_knowledge: "",
      }),
    ).toBe(ALL_SKIPPED_TEXT);
  });
});
