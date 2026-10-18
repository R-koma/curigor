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
}

export interface StudyMemoQuestion {
  question: string;
  answer: string;
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
  aspects: StudyMemoAspectName[];
  glossary_count: number;
  question_count: number;
}

export interface StudyMemoGroup {
  key: string;
  name: string;
  isCore: boolean;
  questions: StudyMemoQuestion[];
  terms: StudyMemoTerm[];
}

function takeUnused<T>(
  items: T[],
  indices: number[] | undefined,
  used: Set<number>,
): T[] {
  const taken: T[] = [];
  for (const i of indices ?? []) {
    if (i < 0 || i >= items.length || used.has(i)) continue;
    used.add(i);
    taken.push(items[i]);
  }
  return taken;
}

export function groupStudyMemo(memo: StudyMemo): StudyMemoGroup[] {
  const usedQuestions = new Set<number>();
  const usedTerms = new Set<number>();
  const groups: StudyMemoGroup[] = [];

  for (const aspect of memo.overview) {
    const questions = takeUnused(
      memo.questions,
      aspect.question_indices,
      usedQuestions,
    );
    const terms = takeUnused(memo.glossary, aspect.term_indices, usedTerms);
    if (questions.length === 0 && terms.length === 0) continue;
    groups.push({
      key: aspect.aspect_id,
      name: aspect.name,
      isCore: aspect.is_core,
      questions,
      terms,
    });
  }

  const otherQuestions = memo.questions.filter((_, i) => !usedQuestions.has(i));
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
