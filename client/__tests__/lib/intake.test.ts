import { describe, it, expect } from "vitest";
import {
  ALL_SKIPPED_TEXT,
  formatIntakeAnswers,
  initialSelections,
  intakeQuestionText,
  intakeSpeechText,
  isIntakeCard,
  otherMaxLength,
  VOICE_INTAKE_CLOSING,
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
    expect(isAnswered("prior_knowledge", s.prior_knowledge)).toBe(false);
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
      topic: "",
      purpose: "仕事で使う",
      source: ["書籍", "動画"],
      prior_knowledge: "",
    });
    expect(text).toBe("目的: 仕事で使う\n教材: 書籍、動画");
  });

  it("uses a fixed sentence when everything is skipped", () => {
    expect(
      formatIntakeAnswers(card, {
        topic: "",
        purpose: "",
        source: [],
        prior_knowledge: "",
      }),
    ).toBe(ALL_SKIPPED_TEXT);
  });
});

describe("intakeQuestionText", () => {
  it("drops the selection note meant for the clickable card", () => {
    expect(
      intakeQuestionText({
        ...card.questions[1],
        question: "何を使って学びますか？（複数選択可）",
      }),
    ).toBe("何を使って学びますか？");
  });
});

describe("intakeSpeechText", () => {
  it("reads the lead, every question and the closing line in order", () => {
    expect(
      intakeSpeechText("始める前に教えてください。", card).split("\n"),
    ).toEqual([
      "始める前に教えてください。",
      ...card.questions.map((q) => q.question),
      VOICE_INTAKE_CLOSING,
    ]);
  });
});

describe("topic question", () => {
  const topicCard: IntakeCard = {
    questions: [
      {
        key: "topic",
        header: "トピック",
        question: "何について学びますか？",
        options: [{ label: "Linuxの仕組み", description: "" }],
        multi_select: false,
        preselected: [],
      },
      ...card.questions,
    ],
  };

  it("starts empty and answers with the chosen candidate", () => {
    const s = initialSelections(topicCard);
    expect(s.topic.selected).toEqual([]);

    s.topic = { ...s.topic, selected: ["Linuxの仕組み"] };
    expect(toIntakeAnswers(topicCard, s).topic).toBe("Linuxの仕組み");
  });

  it("answers with free text, limited to the topic length", () => {
    const s = initialSelections(topicCard);
    s.topic = {
      selected: [],
      other: "あ".repeat(100),
      otherActive: true,
      skipped: false,
    };

    expect(toIntakeAnswers(topicCard, s).topic).toHaveLength(60);
    expect(otherMaxLength("topic")).toBe(60);
    expect(otherMaxLength("purpose")).toBe(200);
  });

  it("leaves the topic empty when skipped or when the card has no topic question", () => {
    const s = initialSelections(topicCard);
    s.topic = { ...s.topic, skipped: true };

    expect(toIntakeAnswers(topicCard, s).topic).toBe("");
    expect(toIntakeAnswers(card, initialSelections(card)).topic).toBe("");
  });

  it("puts the topic first in the formatted answers", () => {
    const s = initialSelections(topicCard);
    s.topic = { ...s.topic, selected: ["Linuxの仕組み"] };
    s.purpose = { ...s.purpose, selected: ["面接対策"] };

    expect(formatIntakeAnswers(topicCard, toIntakeAnswers(topicCard, s))).toBe(
      "トピック: Linuxの仕組み\n目的: 面接対策",
    );
  });
});

describe("isIntakeCard", () => {
  it("accepts a card with a questions array", () => {
    expect(isIntakeCard({ questions: [] })).toBe(true);
  });

  it("rejects a topic correction card and other shapes", () => {
    expect(isIntakeCard({ previous_topic: "A", new_topic: "B" })).toBe(false);
    expect(isIntakeCard({ questions: "x" })).toBe(false);
    expect(isIntakeCard(undefined)).toBe(false);
    expect(isIntakeCard(null)).toBe(false);
  });
});
