"""深さの地図（DepthMap）の生成後処理・マージ・区切り判定。

聞き取り（目的・出典・前提知識）を反映してトピックの中核観点を裏側で決め、
学習対話の問いを「なぜ・仕組み」まで導くための地図。ユーザーには見せない。
"""

import re
import unicodedata
from collections.abc import Sequence

from graph.coverage import CoverageProgress
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation
from graph.state import DepthMapAspectState, DepthMapState, MapAspectProgress, MapStage

MAX_CORE_ASPECTS = 4

_STAGE_ORDER: dict[MapStage, int] = {"mentioned": 0, "defined": 1, "reasoned": 2, "applied": 3}
_STAGES: list[MapStage] = ["mentioned", "defined", "reasoned", "applied"]

STAGE_LABELS: dict[MapStage, str] = {
    "mentioned": "言及のみ",
    "defined": "定義済み",
    "reasoned": "なぜ・仕組みまで説明済み",
    "applied": "目的に沿った応用まで説明済み",
}

WRAP_UP_STAGE: MapStage = "reasoned"


def slugify_aspect_id(name: str, existing_ids: Sequence[str]) -> str:
    """観点名からスラッグを生成する。衝突したら連番を付ける。

    地図の観点 id は LLM に生成させず常にこの関数で決めるため、表記ゆれで
    別観点扱いになる問題が起きない（id は名前が変わっても対話中は不変）。
    """
    normalized = unicodedata.normalize("NFKC", name).strip().lower()
    slug = re.sub(r"[^a-z0-9぀-ヿ一-鿿]+", "-", normalized).strip("-")
    if not slug:
        slug = "aspect"
    candidate = slug
    suffix = 2
    existing = set(existing_ids)
    while candidate in existing:
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate


def build_depth_map(topic: str, drafts: Sequence[DepthMapAspectDraft]) -> DepthMapState:
    """LLM が出した観点案から、id を確定し中核観点を最大 MAX_CORE_ASPECTS 件に絞った地図を組み立てる。

    案の順序を保ったまま先頭から中核を数え、超過分は is_core=False へ落とす。
    1件も中核が無ければ、区切りが永遠に成立しなくなるのを避けるため先頭を中核へ昇格する。
    """
    aspects: list[DepthMapAspectState] = []
    ids: list[str] = []
    core_count = 0
    for draft in drafts:
        aspect_id = slugify_aspect_id(draft.name, ids)
        ids.append(aspect_id)
        is_core = draft.is_core and core_count < MAX_CORE_ASPECTS
        if is_core:
            core_count += 1
        aspects.append(
            {
                "id": aspect_id,
                "name": draft.name,
                "is_core": is_core,
                "defined_question": draft.defined_question,
                "reasoned_question": draft.reasoned_question,
                "applied_question": draft.applied_question,
            }
        )
    if core_count == 0 and aspects:
        aspects[0] = {**aspects[0], "is_core": True}
    return {"topic": topic, "aspects": aspects}


def question_for(aspect: DepthMapAspectState, stage: MapStage) -> str:
    """指定段階の核心の問いを返す。mentioned にはまだ核心の問いが無いので defined を返す。"""
    if stage in ("mentioned", "defined"):
        return aspect["defined_question"]
    if stage == "reasoned":
        return aspect["reasoned_question"]
    return aspect["applied_question"]


def next_stage(current: MapStage | None) -> MapStage:
    order = _STAGE_ORDER[current] if current else -1
    return _STAGES[min(order + 1, len(_STAGES) - 1)]


def resolve_aspect(raw_id: str, depth_map: DepthMapState) -> tuple[str, DepthMapState]:
    """LLM が出した観点参照（id または新規名）を、地図上の id に解決する。

    既知の id・名前のどちらにも一致しなければ新規観点として地図へ追加する（is_core=False）。
    新規観点の各段階の核心の問いは、追加のLLM呼び出しを避けるため名前から定型文で生成する。
    """
    for aspect in depth_map["aspects"]:
        if raw_id == aspect["id"] or raw_id == aspect["name"]:
            return aspect["id"], depth_map

    existing_ids = [a["id"] for a in depth_map["aspects"]]
    new_id = slugify_aspect_id(raw_id, existing_ids)
    new_aspect: DepthMapAspectState = {
        "id": new_id,
        "name": raw_id,
        "is_core": False,
        "defined_question": f"{raw_id}を自分の言葉で定義できるか",
        "reasoned_question": f"{raw_id}がなぜ必要か・どう成り立つかを説明できるか",
        "applied_question": f"{raw_id}を学習ゴールに沿った場面で活かせるか",
    }
    updated: DepthMapState = {"topic": depth_map["topic"], "aspects": [*depth_map["aspects"], new_aspect]}
    return new_id, updated


def merge_map_coverage(
    existing: Sequence[MapAspectProgress],
    observations: Sequence[MapAspectObservation],
    depth_map: DepthMapState,
) -> tuple[list[MapAspectProgress], DepthMapState]:
    """観測を map_covered へ昇格のみでマージする。新規観点があれば地図へ追加してから解決する。

    観点は id で管理するため、graph.coverage.merge_coverage と違い表記ゆれで別観点にならない。
    """
    merged: dict[str, MapStage] = {c["aspect_id"]: c["reached_stage"] for c in existing}
    current_map = depth_map
    for obs in observations:
        aspect_id, current_map = resolve_aspect(obs.aspect_id, current_map)
        current = merged.get(aspect_id)
        if current is None or _STAGE_ORDER[obs.reached_stage] > _STAGE_ORDER[current]:
            merged[aspect_id] = obs.reached_stage
    return [{"aspect_id": aid, "reached_stage": stage} for aid, stage in merged.items()], current_map


def depth_map_progress(covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> CoverageProgress:
    """中核観点のうち WRAP_UP_STAGE（なぜ・仕組み）以上に届いた数を返す。"""
    reached_ids = {c["aspect_id"] for c in covered if _STAGE_ORDER[c["reached_stage"]] >= _STAGE_ORDER[WRAP_UP_STAGE]}
    core = [a for a in depth_map["aspects"] if a["is_core"]]
    reached = [a["name"] for a in core if a["id"] in reached_ids]
    return CoverageProgress(reached_aspects=tuple(reached), target_count=len(core))


def format_map_coverage(covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> str:
    """カバレッジをプロンプト注入用の箇条書きに整形する。空なら空文字。"""
    names = {a["id"]: a["name"] for a in depth_map["aspects"]}
    return "\n".join(
        f"- {names.get(c['aspect_id'], c['aspect_id'])}: {c['reached_stage']}（{STAGE_LABELS[c['reached_stage']]}）"
        for c in covered
    )
