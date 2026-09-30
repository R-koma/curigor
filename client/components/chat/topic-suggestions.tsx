"use client";

const SUGGESTIONS = [
  "仕事で React のフックを使うので学びたい",
  "SRE のエラーバジェットを人に説明できるようになりたい",
  "TCP と UDP の違いを腑に落としたい",
  "複利の仕組みを家計管理に活かしたい",
];

interface TopicSuggestionsProps {
  onSelect: (text: string) => void;
}

export function TopicSuggestions({ onSelect }: TopicSuggestionsProps) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="入力例">
      {SUGGESTIONS.map((text) => (
        <button
          key={text}
          type="button"
          onClick={() => onSelect(text)}
          className="cursor-pointer rounded-full border bg-background px-3.5 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:border-blue-500/50 hover:bg-blue-500/5 hover:text-foreground"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
