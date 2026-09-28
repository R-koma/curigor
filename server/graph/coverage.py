"""観点カバレッジ（covered_aspects）のマージ・整形。

「既出観点の再質問禁止」を直近メッセージの読解だけに頼らせないため、
観点ごとの到達度を state に累積し、毎ターンのプロンプトに注入する。
"""

from collections.abc import Sequence
from dataclasses import dataclass

from graph.output_schemas import AspectObservation
from graph.state import CoveredAspect, ReachedDepth

_DEPTH_ORDER: dict[ReachedDepth, int] = {
    "mentioned": 0,
    "defined": 1,
    "exemplified": 2,
    "applied": 3,
}

DEPTH_LABELS: dict[ReachedDepth, str] = {
    "mentioned": "言及のみ",
    "defined": "定義済み",
    "exemplified": "具体例・動作原理まで説明済み",
    "applied": "応用・他概念との関係まで説明済み",
}

WRAP_UP_MIN_ASPECTS = 3
_WRAP_UP_DEPTH: ReachedDepth = "exemplified"


@dataclass(frozen=True)
class CoverageProgress:
    reached_aspects: tuple[str, ...]
    target_count: int

    @property
    def is_complete(self) -> bool:
        return len(self.reached_aspects) >= self.target_count


def coverage_progress(covered: Sequence[CoveredAspect], focus_aspects: Sequence[str] | None) -> CoverageProgress:
    """到達目標（exemplified 以上）に届いた観点と、区切りを提案する基準数を返す。

    `focus_aspects` があればその全観点、無ければ `WRAP_UP_MIN_ASPECTS` 個の到達を完了とする。
    """
    reached = [a["aspect"] for a in covered if _DEPTH_ORDER[a["reached_depth"]] >= _DEPTH_ORDER[_WRAP_UP_DEPTH]]
    if focus_aspects:
        reached_set = set(reached)
        return CoverageProgress(
            reached_aspects=tuple(a for a in focus_aspects if a in reached_set),
            target_count=len(focus_aspects),
        )
    return CoverageProgress(reached_aspects=tuple(reached), target_count=WRAP_UP_MIN_ASPECTS)


def merge_coverage(
    existing: Sequence[CoveredAspect],
    observations: Sequence[AspectObservation],
) -> list[CoveredAspect]:
    """既存カバレッジへ今ターンの観測をマージする。

    昇格のみ（一度到達した深さを下げない）。観点の並びは既出順を保つ
    （プロンプトの観点選定基準「既出順」がこの並びに依存する）。
    """
    merged: dict[str, ReachedDepth] = {a["aspect"]: a["reached_depth"] for a in existing}
    for obs in observations:
        current = merged.get(obs.aspect)
        if current is None or _DEPTH_ORDER[obs.reached_depth] > _DEPTH_ORDER[current]:
            merged[obs.aspect] = obs.reached_depth
    return [{"aspect": aspect, "reached_depth": depth} for aspect, depth in merged.items()]


def format_covered_aspects(covered: Sequence[CoveredAspect]) -> str:
    """カバレッジをプロンプト注入用の箇条書きに整形する。空なら空文字。"""
    return "\n".join(f"- {a['aspect']}: {a['reached_depth']}（{DEPTH_LABELS[a['reached_depth']]}）" for a in covered)
