export type IntakeKey = "topic" | "purpose" | "source" | "prior_knowledge";

export interface IntakeOption {
  label: string;
  description: string;
}

export interface IntakeQuestion {
  key: IntakeKey;
  header: string;
  question: string;
  options: IntakeOption[];
  multi_select: boolean;
  preselected: string[];
}

export interface IntakeCard {
  questions: IntakeQuestion[];
}

export interface IntakeAnswers {
  topic: string;
  purpose: string;
  source: string[];
  prior_knowledge: string;
}

export interface QuestionSelection {
  selected: string[];
  other: string;
  otherActive: boolean;
  skipped: boolean;
}

export type IntakeSelections = Record<IntakeKey, QuestionSelection>;

// サーバーの IntakeAnswers の max_length と一致させる
export const OTHER_MAX_LENGTH = 200;
export const TOPIC_MAX_LENGTH = 60;
export const ALL_SKIPPED_TEXT = "特になし。このまま始めます";

const EMPTY: QuestionSelection = {
  selected: [],
  other: "",
  otherActive: false,
  skipped: false,
};

export function otherMaxLength(key: IntakeKey): number {
  return key === "topic" ? TOPIC_MAX_LENGTH : OTHER_MAX_LENGTH;
}

export function initialSelections(card: IntakeCard): IntakeSelections {
  const selections: IntakeSelections = {
    topic: { ...EMPTY },
    purpose: { ...EMPTY },
    source: { ...EMPTY },
    prior_knowledge: { ...EMPTY },
  };
  for (const q of card.questions) {
    selections[q.key] = {
      ...EMPTY,
      selected: [...q.preselected],
      otherActive: q.options.length === 0,
    };
  }
  return selections;
}

export function toggleOption(
  q: IntakeQuestion,
  s: QuestionSelection,
  label: string,
): QuestionSelection {
  if (!q.multi_select) {
    return { ...s, selected: [label], otherActive: false, skipped: false };
  }
  const selected = s.selected.includes(label)
    ? s.selected.filter((l) => l !== label)
    : [...s.selected, label];
  return { ...s, selected, skipped: false };
}

function otherText(key: IntakeKey, s: QuestionSelection): string {
  return s.otherActive ? s.other.trim().slice(0, otherMaxLength(key)) : "";
}

export function isAnswered(key: IntakeKey, s: QuestionSelection): boolean {
  if (s.skipped) return false;
  return s.selected.length > 0 || otherText(key, s) !== "";
}

export function toIntakeAnswers(
  card: IntakeCard,
  selections: IntakeSelections,
): IntakeAnswers {
  const answers: IntakeAnswers = {
    topic: "",
    purpose: "",
    source: [],
    prior_knowledge: "",
  };
  for (const q of card.questions) {
    const s = selections[q.key];
    if (s.skipped) continue;
    const other = otherText(q.key, s);
    if (q.key === "source") {
      answers.source = other ? [...s.selected, other] : [...s.selected];
    } else {
      answers[q.key] = other || (s.selected[0] ?? "");
    }
  }
  return answers;
}

export function formatIntakeAnswers(
  card: IntakeCard,
  answers: IntakeAnswers,
): string {
  const lines = card.questions.flatMap((q) => {
    const value =
      q.key === "source" ? answers.source.join("、") : answers[q.key];
    return value ? [`${q.header}: ${value}`] : [];
  });
  return lines.length > 0 ? lines.join("\n") : ALL_SKIPPED_TEXT;
}

const SELECTION_NOTE = /（[^）]*）/g;

export const VOICE_INTAKE_CLOSING =
  "まとめて話して、終わったら「以上」と言ってください。";

export function intakeQuestionText(q: IntakeQuestion): string {
  return q.question.replace(SELECTION_NOTE, "");
}

export function intakeSpeechText(lead: string, card: IntakeCard): string {
  return [
    lead,
    ...card.questions.map(intakeQuestionText),
    VOICE_INTAKE_CLOSING,
  ].join("\n");
}
