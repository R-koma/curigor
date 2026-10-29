// 日本語は単語の間に空白が無く、任意の文字の間で折り返されるため、文節ごとに包んで切れ目でだけ折り返す
export default function Phrases({ phrases }: { phrases: string[] }) {
  return phrases.map((phrase) => (
    <span key={phrase} className="inline-block">
      {phrase}
    </span>
  ));
}
