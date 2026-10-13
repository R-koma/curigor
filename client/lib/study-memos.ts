export interface StudyMemoAspect {
  aspect_id: string;
  name: string;
  summary: string;
  is_core: boolean;
  explained: boolean;
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
  overview: StudyMemoAspect[];
  glossary: StudyMemoTerm[];
  questions: StudyMemoQuestion[];
  created_at: string;
}

export interface StudyMemoSummary {
  id: string;
  topic: string;
  source: string;
  created_at: string;
}
