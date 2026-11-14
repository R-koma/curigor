export interface StudyMemoAspect {
  aspect_id: string;
  name: string;
  is_core: boolean;
  question_indices: number[];
  term_indices: number[];
}

export interface StudyMemoTerm {
  term: string;
  reading: string;
  meaning: string;
  from_side?: boolean;
}

export interface StudyMemoQuestion {
  question: string;
  answer: string;
  quote?: string | null;
  parent_index?: number | null;
  from_side?: boolean;
}

export interface StudyMemoGroupQuestion extends StudyMemoQuestion {
  childDepth: number;
}

export interface StudyMemoOrigin {
  note_id: string;
  note_topic: string;
  improvement: string;
  aspect_id: string | null;
}

export interface StudyMemo {
  id: string;
  topic: string;
  source: string;
  summary: string;
  overview: StudyMemoAspect[];
  glossary: StudyMemoTerm[];
  questions: StudyMemoQuestion[];
  created_at: string;
  origin?: StudyMemoOrigin | null;
}

export interface StudyMemoAspectName {
  name: string;
  is_core: boolean;
}

export interface StudyMemoSummary {
  id: string;
  topic: string;
  source: string;
  created_at: string;
  handed_over: boolean;
  origin_note_id: string | null;
  aspects: StudyMemoAspectName[];
  glossary_count: number;
  question_count: number;
}

export interface StudyMemoGroup {
  key: string;
  name: string;
  isCore: boolean;
  questions: StudyMemoGroupQuestion[];
  terms: StudyMemoTerm[];
}

function withChildDepth(
  memo: StudyMemo,
  indices: number[],
): StudyMemoGroupQuestion[] {
  const depthOf = new Map<number, number>();
  return indices.map((index) => {
    const question = memo.questions[index];
    const parent = question.parent_index;
    const parentDepth =
      parent !== null && parent !== undefined ? depthOf.get(parent) : undefined;
    const childDepth = parentDepth === undefined ? 0 : parentDepth + 1;
    depthOf.set(index, childDepth);
    return { ...question, childDepth };
  });
}

function takeUnused(
  count: number,
  indices: number[] | undefined,
  used: Set<number>,
): number[] {
  const taken: number[] = [];
  for (const i of indices ?? []) {
    if (i < 0 || i >= count || used.has(i)) continue;
    used.add(i);
    taken.push(i);
  }
  return taken;
}

export function groupStudyMemo(memo: StudyMemo): StudyMemoGroup[] {
  const usedQuestions = new Set<number>();
  const usedTerms = new Set<number>();
  const groups: StudyMemoGroup[] = [];

  for (const aspect of memo.overview) {
    const questions = withChildDepth(
      memo,
      takeUnused(memo.questions.length, aspect.question_indices, usedQuestions),
    );
    const terms = takeUnused(
      memo.glossary.length,
      aspect.term_indices,
      usedTerms,
    ).map((i) => memo.glossary[i]);
    if (questions.length === 0 && terms.length === 0) continue;
    groups.push({
      key: aspect.aspect_id,
      name: aspect.name,
      isCore: aspect.is_core,
      questions,
      terms,
    });
  }

  const otherQuestions = withChildDepth(
    memo,
    memo.questions.flatMap((_, i) => (usedQuestions.has(i) ? [] : [i])),
  );
  const otherTerms = memo.glossary.filter((_, i) => !usedTerms.has(i));
  if (otherQuestions.length > 0 || otherTerms.length > 0) {
    groups.push({
      key: "other",
      name: groups.length > 0 ? "観点に入らなかった疑問と用語" : "疑問と用語",
      isCore: false,
      questions: otherQuestions,
      terms: otherTerms,
    });
  }
  return groups;
}

export interface NoteStudyMemo {
  id: string;
  topic: string;
  created_at: string;
  feedback_id: string | null;
  improvement_index: number | null;
  improvement: string | null;
  aspect_id: string | null;
}

export function memosForImprovement(
  memos: readonly NoteStudyMemo[],
  feedbackId: string,
  index: number,
): NoteStudyMemo[] {
  return memos.filter(
    (m) => m.feedback_id === feedbackId && m.improvement_index === index,
  );
}

export function exploreFromImprovementHref(
  noteId: string,
  feedbackId: string,
  index: number,
): string {
  return `/learn?mode=explore&note=${noteId}&feedback=${feedbackId}&item=${index}`;
}
