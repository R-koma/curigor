# 聞き取り＋深さの地図 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学習開始時にチャットで目的・出典・前提知識を聞き取り、それをもとに裏側で「深さの地図」（トピックの中核観点＋段階ごとの核心の問い）を生成し、以後の学習対話の質問をその地図に沿わせる。

**Architecture:** `learning_dialogue` ノードを `intake_complete` state キーの有無・値で3方向に振り分ける薄いルーターにする（グラフのエッジ・`GRAPH_VERSION` は無変更）。旧セッション（キー欠損）は既存の `prepare_turn`/`respond` を無変更のまま実行し、`evals/eval.py` の regression・pinned replay は影響を受けない。新セッションは聞き取り（`_intake.py`）→ 地図生成（`depth_map.py`）→ 地図駆動の対話（`_map_dialogue.py`）と進む。

**Tech Stack:** Python 3.13 / FastAPI / LangGraph / Pydantic structured output（既存スタックのまま。新規依存なし）。フロント側は Next.js の既存フォームから1つの入力欄を削除するのみ。

**Spec:** `docs/superpowers/specs/2026-09-29-intake-depth-map-design.md`

## Global Constraints

- 行長 119 文字、Python 3.13 ターゲット、ruff（E, W, F, I, B, UP）+ mypy strict（`server/`）
- コメントは「コードから復元できない事実」のみ。CLAUDE.md に書いてある知識をコード側に複製しない
- `LearningState` の新規フィールドはすべて `NotRequired`。読む側は `.get()` で欠損許容する
- 毎ターン置き換わる state フィールドは、値が無いターンにも明示的に書く（`wrap_up_offered` と同じ流儀）
- ノード内の追加 LLM 呼び出し（ストリーミング対象外）には `INTERNAL_LLM_TAG` を付ける
- `GRAPH_VERSION` は変更しない（トポロジー不変）
- `evals/eval.py` が直接 import する `TurnPlan` / `prepare_turn` / `respond` / `learning_dialogue`（`graph/nodes/learning_dialogue.py`）のシグネチャ・挙動は無変更
- DB を使うテストは無し（このプランの変更は DB に触れない。既存の `server/tests/unit/` パターン=pytest + モック禁止だが、ここで書くのはすべて LLM 呼び出しをモックする純粋ロジック/ノードのユニットテスト）
- コミットメッセージ末尾: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`

## Review Focus

- 旧セッション（デプロイ前に開始済み、`intake_complete` キー欠損）を resume したとき、聞き取りに誤って入らず legacy 経路のまま継続すること
- 聞き取り中に「わかりません」等の不知表明が来ても抽出LLMの構造化出力が落ちず、次ターンへ空値で持ち越されること
- ユーザーが最初の返信で目的・出典・前提知識を一度に全部話した場合、聞き取りが1ターンで完了し、地図生成と最初の学習質問が同じ応答内で1メッセージとして返ること
- 深さの地図生成で LLM が中核観点を4件より多く返しても、コード側が先頭4件に決定的に絞ること
- 地図に無い話題が対話中に出たとき、新規観点として追加されるが区切り判定（`depth_map_progress`）の分母（中核観点数）には影響しないこと

---

## File Structure

```
server/graph/
  state.py                       # 変更: 新規 TypedDict / LearningState フィールド追加
  output_schemas.py              # 変更: 新規 Pydantic モデル追加
  depth_map.py                   # 新規: 地図の構築・マージ・区切り判定（純粋関数）
  prompts/
    question.py                  # 変更: build_mode_section を切り出し公開
    intake.py                    # 新規: 聞き取りの質問生成 + 構造化抽出プロンプト
    depth_map.py                 # 新規: 地図生成プロンプト
    map_turn_analysis.py         # 新規: 地図駆動の事前分析プロンプト
    map_question.py              # 新規: 地図駆動の応答生成プロンプト（question.py のモード構造を再利用）
    learning_planner.py          # 削除
  nodes/
    _shared.py                   # 新規: recent_messages_block（学習系ノード共通）
    _intake_analysis.py          # 新規: 聞き取り1ターンの構造化抽出
    _map_turn_analysis.py        # 新規: 地図駆動の事前分析
    _map_dialogue.py             # 新規: 地図駆動の対話（prepare_map_turn / respond_map）
    _intake.py                   # 新規: 聞き取りフェーズのターン処理
    learning_start.py            # 変更: 聞き取りの最初の問いを返すよう書き換え
    learning_dialogue.py         # 変更: ルーターに変更。既存 TurnPlan/prepare_turn/respond は無変更
api/websocket/
  chat.py                        # 変更: _learning_progress が depth_map の有無で分岐

client/app/(main)/learn/
  page.tsx                       # 変更: 学習ゴール入力欄を削除（トピックのみのフォームに）
```

---

### Task 1: `build_mode_section` を切り出す（安全なリファクタ）

既存の `_build_predecided_section` はモード本文の組み立てを `DialogueTurnAnalysis` 専用にしている。地図駆動の対話からも同じモード本文（訂正/展開/深掘りの指示・例）を再利用したいので、プリミティブ引数を取る公開関数に分離する。出力は既存と完全に同一になるよう設計する（`PROMPT_FINGERPRINT` は変化しない）。

**Files:**
- Modify: `server/graph/prompts/question.py`
- Test: `server/tests/unit/graph/test_question_prompt.py`

**Interfaces:**
- Produces: `build_mode_section(*, response_mode: ResponseMode, selected_aspect_label: str, error_summary: str = "", extra_hint: str = "") -> str`（`graph.prompts.question` から export。他タスクが import する）

- [ ] **Step 1: 既存のフィンガープリントを退避するテストを書く（リグレッション防止の網）**

`server/tests/unit/graph/test_question_prompt.py` の末尾に追記:

```python
class TestBuildModeSection:
    def test_matches_legacy_predecided_section_output(self) -> None:
        analysis = DialogueTurnAnalysis(
            observations=[],
            has_misconception=True,
            error_summary="並行処理を仕組みそのものとして述べている",
            response_mode="reinforce",
            selected_aspect="プロセスの管理",
        )
        legacy = question._build_predecided_section(analysis)
        via_helper = question.build_mode_section(
            response_mode=analysis.response_mode,
            selected_aspect_label=analysis.selected_aspect,
            error_summary=analysis.error_summary,
        )
        assert legacy == via_helper

    def test_extra_hint_is_appended_when_present(self) -> None:
        rendered = question.build_mode_section(
            response_mode="deepen",
            selected_aspect_label="キュー",
            extra_hint="### この観点の核心（地図より）\nなぜ FIFO が必要か",
        )
        assert rendered.endswith("なぜ FIFO が必要か")

    def test_no_hint_appended_when_extra_hint_empty(self) -> None:
        with_empty = question.build_mode_section(response_mode="expand", selected_aspect_label="キュー")
        legacy = question._build_predecided_section(
            DialogueTurnAnalysis(
                observations=[], has_misconception=False, response_mode="expand", selected_aspect="キュー"
            )
        )
        assert with_empty == legacy
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_question_prompt.py -v -k BuildModeSection`
Expected: FAIL（`build_mode_section` が存在しない）

- [ ] **Step 3: `build_mode_section` を実装し `_build_predecided_section` をそれ経由に書き換える**

`server/graph/prompts/question.py` の `_build_predecided_section` 定義を以下に置き換える（前後の関数・定数は変更しない）:

```python
def build_mode_section(
    *,
    response_mode: ResponseMode,
    selected_aspect_label: str,
    error_summary: str = "",
    extra_hint: str = "",
) -> str:
    """モード本文（既出観点の扱い・訂正/展開/深掘りの指示・例）を組み立てる。

    `_build_predecided_section`（この対話の legacy パス）と地図駆動の対話
    （`graph/prompts/map_question.py`）の両方から使う共通ロジック。
    """
    header_lines = [
        "## 応答モード（事前分析による決定）",
        f"この応答は「{_PREDECIDED_MODE_LABELS[response_mode]}」で行うと決定済み。モードと観点を再選択せず、この決定に従う。",
        f"焦点を当てる観点: {selected_aspect_label}",
    ]
    if response_mode == "reinforce" and error_summary:
        header_lines.append(f"検出された誤り: {error_summary}")
    header = "\n".join(header_lines) + "\n"
    parts = [
        _DIALOGUE_RULES_COVERED,
        header,
        *_PREDECIDED_MODE_BODIES[response_mode],
        _DIALOGUE_RULES_NO_MENU,
        _MODE_EXAMPLES[response_mode],
    ]
    if extra_hint:
        parts.append(extra_hint)
    return "\n".join(parts)


def _build_predecided_section(analysis: DialogueTurnAnalysis) -> str:
    return build_mode_section(
        response_mode=analysis.response_mode,
        selected_aspect_label=analysis.selected_aspect,
        error_summary=analysis.error_summary,
    )
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_question_prompt.py -v`
Expected: PASS（全件。既存の `_prompt_fingerprint` 系テストも含めて無変更で通ること）

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/prompts/question.py tests/unit/graph/test_question_prompt.py
git commit -m "refactor(graph): extract build_mode_section from question prompt"
```

---

### Task 2: state に新規フィールドを追加する

**Files:**
- Modify: `server/graph/state.py`

**Interfaces:**
- Produces:
  - `MapStage = Literal["mentioned", "defined", "reasoned", "applied"]`
  - `class DepthMapAspectState(TypedDict): id: str; name: str; is_core: bool; defined_question: str; reasoned_question: str; applied_question: str`
  - `class DepthMapState(TypedDict): topic: str; aspects: list[DepthMapAspectState]`
  - `class MapAspectProgress(TypedDict): aspect_id: str; reached_stage: MapStage`
  - `LearningState` に `intake_complete`, `intake_turns`, `learning_source`, `prior_knowledge`, `depth_map`, `map_covered` を追加（すべて `NotRequired`）
  - `TurnAnalysisRecord` に `selected_aspect_id: NotRequired[str]` を追加

このタスクに専用テストは無い（型定義のみ）。後続タスクの mypy strict チェックが正しさを検証する。

- [ ] **Step 1: `graph/state.py` を編集する**

`ReachedDepth` の定義の直後、`class CoveredAspect` の前に追加:

```python
MapStage = Literal["mentioned", "defined", "reasoned", "applied"]
"""深さの地図の到達段階。既存 ReachedDepth（mentioned/defined/exemplified/applied）とは独立させる。

exemplified（具体例または動作原理）を reasoned（なぜ・仕組み）に置き換え、
具体例1つで到達扱いになる浅い基準をなくすための地図専用の段階。
"""


class DepthMapAspectState(TypedDict):
    id: str
    name: str
    is_core: bool
    defined_question: str
    reasoned_question: str
    applied_question: str


class DepthMapState(TypedDict):
    topic: str
    aspects: list[DepthMapAspectState]


class MapAspectProgress(TypedDict):
    aspect_id: str
    reached_stage: MapStage
```

`TurnAnalysisRecord` に1行追加（`wrap_up` の直後）:

```python
    selected_aspect_id: NotRequired[str]
```

`LearningState` に追加（`wrap_up_offered` の直後）:

```python
    intake_complete: NotRequired[bool]
    intake_turns: NotRequired[int]
    learning_source: NotRequired[str]
    prior_knowledge: NotRequired[str]
    depth_map: NotRequired[DepthMapState]
    map_covered: NotRequired[list[MapAspectProgress]]
```

- [ ] **Step 2: 型チェックを実行する**

Run: `cd server && uv run mypy graph/state.py`
Expected: `Success: no issues found`

- [ ] **Step 3: Commit**

```bash
cd server && git add graph/state.py
git commit -m "feat(graph): add depth map state fields"
```

---

### Task 3: 新規 Pydantic モデルを追加する

**Files:**
- Modify: `server/graph/output_schemas.py`

**Interfaces:**
- Produces:
  - `class IntakeExtraction(BaseModel): purpose: str = ""; source: str = ""; prior_knowledge: str = ""; ready_to_start: bool`
  - `class DepthMapAspectDraft(BaseModel): name: str; is_core: bool; defined_question: str; reasoned_question: str; applied_question: str`
  - `class DepthMapGeneration(BaseModel): aspects: list[DepthMapAspectDraft]`
  - `class MapAspectObservation(BaseModel): aspect_id: str; reached_stage: Literal["mentioned", "defined", "reasoned", "applied"]`
  - `class MapDialogueTurnAnalysis(BaseModel): observations: list[MapAspectObservation]; has_misconception: bool; error_summary: str = ""; response_mode: ResponseMode; selected_aspect_id: str`

- [ ] **Step 1: `graph/output_schemas.py` の末尾に追加する**

```python
class IntakeExtraction(BaseModel):
    """学習開始前の聞き取り1ターンの構造化抽出。"""

    purpose: str = Field("", description="今回の学習で達成したいこと。直近のユーザー発言に言及が無ければ空文字")
    source: str = Field("", description="学習材料の出典（書籍名・講座名等）。言及が無ければ空文字")
    prior_knowledge: str = Field("", description="トピックについて今何を知っているか。言及が無ければ空文字")
    ready_to_start: bool = Field(
        ..., description="ユーザーが聞き取りを打ち切って学習を始めたい意思を示しているか"
    )


class DepthMapAspectDraft(BaseModel):
    name: str = Field(..., description="観点名（日本語の短い名詞句）")
    is_core: bool = Field(..., description="学習ゴールの達成に不可欠な中核観点か")
    defined_question: str = Field(..., description="「定義」段階で問うべき核心（自分の言葉で定義できるか）")
    reasoned_question: str = Field(
        ...,
        description="「なぜ・仕組み」段階で問うべき核心。日常の具体例ではなく、必要性や動作原理そのものを問う",
    )
    applied_question: str = Field(
        ..., description="「目的に沿った応用」段階で問うべき核心。学習ゴールと結びつけた具体的な活用場面"
    )


class DepthMapGeneration(BaseModel):
    aspects: list[DepthMapAspectDraft] = Field(..., description="3〜7件。中核観点は最大4件まで")


class MapAspectObservation(BaseModel):
    aspect_id: str = Field(
        ...,
        description="言及・説明された観点の id。地図に無い新しい観点なら、id の代わりに"
        "分かりやすい仮の名前（日本語可）を入れてよい。コード側で正式な id に変換する",
    )
    reached_stage: Literal["mentioned", "defined", "reasoned", "applied"] = Field(
        ...,
        description="直近のユーザー発言でこの観点が到達した段階。mentioned=名前のみ / "
        "defined=定義を自分の言葉で述べた / reasoned=なぜ必要か・どう動くかを述べた"
        "（日常の具体例を1つ挙げただけでは reasoned にしない）/ "
        "applied=学習ゴールに沿った具体的な活用場面まで述べた",
    )


class MapDialogueTurnAnalysis(BaseModel):
    """地図駆動の学習対話 1 ターンの事前分析。DialogueTurnAnalysis の地図版。"""

    observations: list[MapAspectObservation] = Field(default_factory=list)
    has_misconception: bool = Field(..., description="直近のユーザー発言に、訂正を要する誤り・混同が含まれるか")
    error_summary: str = Field("", description="has_misconception が true のとき、誤りの内容を1文で")
    response_mode: ResponseMode = Field(..., description="次の AI 応答のモード")
    selected_aspect_id: str = Field(
        ..., description="次の応答で焦点を当てる観点の id。observations と同じ解決規則に従う"
    )
```

- [ ] **Step 2: 型チェックを実行する**

Run: `cd server && uv run mypy graph/output_schemas.py`
Expected: `Success: no issues found`

- [ ] **Step 3: Commit**

```bash
cd server && git add graph/output_schemas.py
git commit -m "feat(graph): add depth map and intake pydantic schemas"
```

---

### Task 4: `recent_messages_block` を共有ヘルパーへ切り出す

`graph/nodes/learning_dialogue.py` の `_turn_context` が直近6件整形をインラインで持っている。聞き取り・地図駆動ノードからも同じ整形が要るため、共有ヘルパーに切り出す（出力は既存と同一）。

**Files:**
- Create: `server/graph/nodes/_shared.py`
- Modify: `server/graph/nodes/learning_dialogue.py`
- Test: `server/tests/unit/graph/test_shared.py`

**Interfaces:**
- Produces: `recent_messages_block(state: LearningState, limit: int = 6) -> str`
- Consumes: `LearningState`（`graph.state`）

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_shared.py`:

```python
from typing import cast
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.nodes._shared import recent_messages_block
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _state(messages: list) -> LearningState:
    return cast(
        LearningState,
        {
            "user_id": "user-abc",
            "dialogue_session_id": SESSION_ID,
            "note_id": NOTE_ID,
            "messages": messages,
            "topic": "二分探索",
            "turn_count": 2,
            "should_generate_note": False,
            "session_type": "learning",
        },
    )


class TestRecentMessagesBlock:
    def test_labels_human_and_ai_messages(self) -> None:
        messages = [HumanMessage(content="こんにちは"), AIMessage(content="こんにちは、始めましょう")]
        rendered = recent_messages_block(_state(messages))
        assert rendered == "ユーザー: こんにちは\nAI: こんにちは、始めましょう"

    def test_limits_to_last_n_messages(self) -> None:
        messages = [HumanMessage(content=f"m{i}") for i in range(8)]
        rendered = recent_messages_block(_state(messages), limit=6)
        assert "m2" in rendered and "m7" in rendered
        assert "m0" not in rendered and "m1" not in rendered

    def test_empty_messages_returns_empty_string(self) -> None:
        assert recent_messages_block(_state([])) == ""
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_shared.py -v`
Expected: FAIL（`graph.nodes._shared` が存在しない）

- [ ] **Step 3: `_shared.py` を実装する**

`server/graph/nodes/_shared.py`:

```python
"""学習系対話ノード（legacy / 聞き取り / 地図駆動）で共有する小さなヘルパー。"""

from graph.state import LearningState


def recent_messages_block(state: LearningState, limit: int = 6) -> str:
    return "\n".join(
        f"{'ユーザー' if msg.type == 'human' else 'AI'}: {msg.content}" for msg in state["messages"][-limit:]
    )
```

- [ ] **Step 4: `learning_dialogue.py` の `_turn_context` をこのヘルパー経由に書き換える**

`server/graph/nodes/learning_dialogue.py` の import に `from graph.nodes._shared import recent_messages_block` を追加し、`_turn_context` を以下に置き換える:

```python
def _turn_context(state: LearningState) -> tuple[str, dict[str, str]]:
    recent_messages = recent_messages_block(state)
    plan_fields = format_learning_plan_fields(
        learning_goal=state.get("learning_goal"),
        focus_aspects=state.get("focus_aspects"),
    )
    return recent_messages, plan_fields
```

- [ ] **Step 5: 新規テストと既存の learning_dialogue テストを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_shared.py tests/unit/graph/test_learning_dialogue.py -v`
Expected: PASS（全件。既存テストの出力が変わらないこと）

- [ ] **Step 6: Commit**

```bash
cd server && git add graph/nodes/_shared.py graph/nodes/learning_dialogue.py tests/unit/graph/test_shared.py
git commit -m "refactor(graph): extract recent_messages_block into a shared helper"
```

---

### Task 5: 深さの地図の純粋関数（`graph/depth_map.py`）

**Files:**
- Create: `server/graph/depth_map.py`
- Test: `server/tests/unit/graph/test_depth_map.py`

**Interfaces:**
- Consumes: `CoverageProgress`（`graph.coverage`）、`DepthMapAspectDraft` / `MapAspectObservation`（`graph.output_schemas`）、`DepthMapAspectState` / `DepthMapState` / `MapAspectProgress` / `MapStage`（`graph.state`）
- Produces:
  - `MAX_CORE_ASPECTS = 4`
  - `WRAP_UP_STAGE: MapStage = "reasoned"`
  - `STAGE_LABELS: dict[MapStage, str]`
  - `slugify_aspect_id(name: str, existing_ids: Sequence[str]) -> str`
  - `build_depth_map(topic: str, drafts: Sequence[DepthMapAspectDraft]) -> DepthMapState`
  - `question_for(aspect: DepthMapAspectState, stage: MapStage) -> str`
  - `next_stage(current: MapStage | None) -> MapStage`
  - `resolve_aspect(raw_id: str, depth_map: DepthMapState) -> tuple[str, DepthMapState]`
  - `merge_map_coverage(existing: Sequence[MapAspectProgress], observations: Sequence[MapAspectObservation], depth_map: DepthMapState) -> tuple[list[MapAspectProgress], DepthMapState]`
  - `depth_map_progress(covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> CoverageProgress`
  - `format_map_coverage(covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_depth_map.py`:

```python
from graph.depth_map import (
    build_depth_map,
    depth_map_progress,
    format_map_coverage,
    merge_map_coverage,
    next_stage,
    question_for,
    resolve_aspect,
    slugify_aspect_id,
)
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation
from graph.state import DepthMapAspectState, DepthMapState, MapAspectProgress


def _draft(name: str, is_core: bool) -> DepthMapAspectDraft:
    return DepthMapAspectDraft(
        name=name,
        is_core=is_core,
        defined_question=f"{name}を定義できるか",
        reasoned_question=f"{name}のなぜ・仕組み",
        applied_question=f"{name}の応用",
    )


class TestSlugifyAspectId:
    def test_slugifies_japanese_name(self) -> None:
        assert slugify_aspect_id("システムコール", []) != ""

    def test_avoids_collision_with_existing_ids(self) -> None:
        first = slugify_aspect_id("キュー", [])
        second = slugify_aspect_id("キュー", [first])
        assert first != second


class TestBuildDepthMap:
    def test_caps_core_aspects_at_four(self) -> None:
        drafts = [_draft(f"観点{i}", True) for i in range(6)]
        depth_map = build_depth_map("トピック", drafts)
        core = [a for a in depth_map["aspects"] if a["is_core"]]
        assert len(core) == 4
        assert [a["name"] for a in core] == ["観点0", "観点1", "観点2", "観点3"]

    def test_promotes_first_aspect_to_core_when_none_marked(self) -> None:
        drafts = [_draft("観点A", False), _draft("観点B", False)]
        depth_map = build_depth_map("トピック", drafts)
        assert depth_map["aspects"][0]["is_core"] is True

    def test_assigns_stable_unique_ids(self) -> None:
        depth_map = build_depth_map("トピック", [_draft("キュー", True), _draft("キュー", False)])
        ids = [a["id"] for a in depth_map["aspects"]]
        assert len(ids) == len(set(ids))


class TestQuestionForAndNextStage:
    def test_mentioned_and_defined_use_defined_question(self) -> None:
        aspect = build_depth_map("t", [_draft("キュー", True)])["aspects"][0]
        assert question_for(aspect, "mentioned") == question_for(aspect, "defined") == "キューを定義できるか"

    def test_reasoned_and_applied_use_their_own_question(self) -> None:
        aspect = build_depth_map("t", [_draft("キュー", True)])["aspects"][0]
        assert question_for(aspect, "reasoned") == "キューのなぜ・仕組み"
        assert question_for(aspect, "applied") == "キューの応用"

    def test_next_stage_progression(self) -> None:
        assert next_stage(None) == "mentioned"
        assert next_stage("mentioned") == "defined"
        assert next_stage("defined") == "reasoned"
        assert next_stage("reasoned") == "applied"
        assert next_stage("applied") == "applied"


class TestResolveAspect:
    def test_matches_by_id_or_name(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        aspect_id = depth_map["aspects"][0]["id"]
        resolved_by_id, unchanged = resolve_aspect(aspect_id, depth_map)
        resolved_by_name, _ = resolve_aspect("キュー", depth_map)
        assert resolved_by_id == resolved_by_name == aspect_id
        assert unchanged == depth_map

    def test_unknown_reference_adds_a_new_non_core_aspect(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        new_id, updated = resolve_aspect("スタック", depth_map)
        added = next(a for a in updated["aspects"] if a["id"] == new_id)
        assert added["name"] == "スタック"
        assert added["is_core"] is False
        assert len(updated["aspects"]) == 2


class TestMergeMapCoverage:
    def test_upgrade_only(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        aspect_id = depth_map["aspects"][0]["id"]
        existing: list[MapAspectProgress] = [{"aspect_id": aspect_id, "reached_stage": "reasoned"}]
        observations = [MapAspectObservation(aspect_id=aspect_id, reached_stage="defined")]
        merged, unchanged_map = merge_map_coverage(existing, observations, depth_map)
        assert merged == [{"aspect_id": aspect_id, "reached_stage": "reasoned"}]
        assert unchanged_map == depth_map

    def test_unknown_observation_grows_the_map_and_is_recorded(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        observations = [MapAspectObservation(aspect_id="スタック", reached_stage="defined")]
        merged, updated_map = merge_map_coverage([], observations, depth_map)
        assert len(updated_map["aspects"]) == 2
        new_id = updated_map["aspects"][1]["id"]
        assert merged == [{"aspect_id": new_id, "reached_stage": "defined"}]


class TestDepthMapProgress:
    def test_counts_only_core_aspects_at_or_beyond_reasoned(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True), _draft("スタック", True), _draft("木", False)])
        ids = [a["id"] for a in depth_map["aspects"]]
        covered: list[MapAspectProgress] = [
            {"aspect_id": ids[0], "reached_stage": "reasoned"},
            {"aspect_id": ids[1], "reached_stage": "defined"},
            {"aspect_id": ids[2], "reached_stage": "applied"},
        ]
        progress = depth_map_progress(covered, depth_map)
        assert progress.reached_aspects == ("キュー",)
        assert progress.target_count == 2
        assert progress.is_complete is False

    def test_is_complete_when_all_core_aspects_reach_reasoned(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True), _draft("スタック", True)])
        ids = [a["id"] for a in depth_map["aspects"]]
        covered: list[MapAspectProgress] = [
            {"aspect_id": ids[0], "reached_stage": "reasoned"},
            {"aspect_id": ids[1], "reached_stage": "applied"},
        ]
        assert depth_map_progress(covered, depth_map).is_complete is True

    def test_non_core_extension_aspects_do_not_affect_completion(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        ids = [a["id"] for a in depth_map["aspects"]]
        _, grown_map = resolve_aspect("スタック", depth_map)
        covered: list[MapAspectProgress] = [{"aspect_id": ids[0], "reached_stage": "reasoned"}]
        progress = depth_map_progress(covered, grown_map)
        assert progress.target_count == 1
        assert progress.is_complete is True


class TestFormatMapCoverage:
    def test_empty_returns_empty_string(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        assert format_map_coverage([], depth_map) == ""

    def test_renders_name_and_stage_label(self) -> None:
        depth_map = build_depth_map("t", [_draft("キュー", True)])
        aspect_id = depth_map["aspects"][0]["id"]
        covered: list[MapAspectProgress] = [{"aspect_id": aspect_id, "reached_stage": "defined"}]
        assert format_map_coverage(covered, depth_map) == "- キュー: defined（定義済み）"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_depth_map.py -v`
Expected: FAIL（`graph.depth_map` が存在しない）

- [ ] **Step 3: `graph/depth_map.py` を実装する**

```python
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
```

- [ ] **Step 4: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_depth_map.py -v && uv run mypy graph/depth_map.py`
Expected: PASS / `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/depth_map.py tests/unit/graph/test_depth_map.py
git commit -m "feat(graph): add depth map build/merge/progress logic"
```

---

### Task 6: 地図生成プロンプト（`graph/prompts/depth_map.py`）

**Files:**
- Create: `server/graph/prompts/depth_map.py`
- Test: `server/tests/unit/graph/test_depth_map_prompt.py`

**Interfaces:**
- Produces: `build_depth_map_prompt(*, topic: str, purpose: str, source: str, prior_knowledge: str) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_depth_map_prompt.py`:

```python
from graph.prompts.depth_map import build_depth_map_prompt


class TestBuildDepthMapPrompt:
    def test_interpolates_topic_and_known_fields(self) -> None:
        rendered = build_depth_map_prompt(
            topic="システムコール", purpose="strace で調査できるようになりたい", source="Linuxのしくみ", prior_knowledge="OSの授業を受けた"
        )
        assert "システムコール" in rendered
        assert "strace で調査できるようになりたい" in rendered
        assert "Linuxのしくみ" in rendered
        assert "OSの授業を受けた" in rendered

    def test_unspecified_fields_use_placeholder(self) -> None:
        rendered = build_depth_map_prompt(topic="キュー", purpose="", source="", prior_knowledge="")
        assert "未指定" in rendered

    def test_warns_against_shallow_example_only_reasoning(self) -> None:
        rendered = build_depth_map_prompt(topic="キュー", purpose="", source="", prior_knowledge="")
        assert "日常の具体例を挙げさせるだけの問いにしない" in rendered
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_depth_map_prompt.py -v`
Expected: FAIL

- [ ] **Step 3: `graph/prompts/depth_map.py` を実装する**

```python
"""深さの地図の生成プロンプト（聞き取り完了時に1回だけ呼ぶ）。"""

from graph.prompts._base import UNSPECIFIED_PLACEHOLDER, inject_charter

DEPTH_MAP_GENERATION_PROMPT = inject_charter(
    """\
## 役割
あなたはソフトウェア開発者向け学習設計の専門家です。
「{topic}」というトピックについて、学習者が自分の言葉で深く説明できるようになるための
観点（中核となる問いの単位）を設計します。

## 学習者の情報
- 学習ゴール（目的）: {purpose}
- 学習材料の出典: {source}
- 前提知識: {prior_knowledge}

## タスク
トピックを 3〜7 個の観点に分解してください。各観点について:

1. `name`: 観点名（日本語の短い名詞句）
2. `is_core`: 学習ゴールの達成に不可欠な中核観点なら true。中核は最大4個まで。
   目的が「未指定」の場合は、トピックの理解に一般的に不可欠な観点を中核とする
3. `defined_question`: この観点を自分の言葉で定義できるかを問う核心
4. `reasoned_question`: なぜこの仕組みが必要か・どう動くかを問う核心。
   **日常の具体例を挙げさせるだけの問いにしない**。「〜する場面を1つ挙げて」のような
   浅い例示ではなく、「なぜ〇〇ではなく△△という設計になっているのか」
   「〇〇が無いと何が困るのか」のように、必要性や動作原理そのものを問う
5. `applied_question`: 学習ゴールに沿った具体的な活用場面を問う核心。
   学習ゴールが「未指定」の場合は、トピックが実務で使われる一般的な場面を問う

## 厳守事項
{{NO_FABRICATION}}
- 前提知識に含まれる内容は、より深い段階（なぜ・仕組み、応用）から始めてよい
- 出典が分かる場合、その水準・範囲に合わせる（入門書なら基礎観点を厚く、専門書なら発展的観点も含める）
"""
)


def build_depth_map_prompt(*, topic: str, purpose: str, source: str, prior_knowledge: str) -> str:
    return DEPTH_MAP_GENERATION_PROMPT.format(
        topic=topic,
        purpose=purpose or UNSPECIFIED_PLACEHOLDER,
        source=source or UNSPECIFIED_PLACEHOLDER,
        prior_knowledge=prior_knowledge or UNSPECIFIED_PLACEHOLDER,
    )
```

- [ ] **Step 4: テストを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_depth_map_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/prompts/depth_map.py tests/unit/graph/test_depth_map_prompt.py
git commit -m "feat(graph): add depth map generation prompt"
```

---

### Task 7: 聞き取りプロンプト（`graph/prompts/intake.py`）

**Files:**
- Create: `server/graph/prompts/intake.py`
- Test: `server/tests/unit/graph/test_intake_prompt.py`

**Interfaces:**
- Produces:
  - `INTAKE_MAX_TURNS = 3`
  - `build_intake_prompt(*, topic: str, purpose: str, source: str, prior_knowledge: str, recent_messages: str) -> str`
  - `build_intake_extraction_prompt(*, topic: str, purpose: str, source: str, prior_knowledge: str, recent_messages: str) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_intake_prompt.py`:

```python
from graph.prompts.intake import INTAKE_MAX_TURNS, build_intake_extraction_prompt, build_intake_prompt


class TestBuildIntakePrompt:
    def test_topic_is_not_treated_as_a_user_statement(self) -> None:
        rendered = build_intake_prompt(topic="システムコール", purpose="", source="", prior_knowledge="", recent_messages="")
        assert "UI 入力値" in rendered

    def test_unanswered_fields_are_marked(self) -> None:
        rendered = build_intake_prompt(topic="キュー", purpose="", source="", prior_knowledge="", recent_messages="")
        assert rendered.count("未回答") == 3

    def test_known_fields_are_interpolated(self) -> None:
        rendered = build_intake_prompt(
            topic="キュー", purpose="面接対策", source="", prior_knowledge="", recent_messages="ユーザー: hi"
        )
        assert "面接対策" in rendered
        assert "ユーザー: hi" in rendered

    def test_empty_recent_messages_uses_placeholder(self) -> None:
        rendered = build_intake_prompt(topic="キュー", purpose="", source="", prior_knowledge="", recent_messages="")
        assert "（まだなし）" in rendered


class TestBuildIntakeExtractionPrompt:
    def test_interpolates_topic_and_history(self) -> None:
        rendered = build_intake_extraction_prompt(
            topic="キュー", purpose="", source="", prior_knowledge="", recent_messages="ユーザー: 面接対策です"
        )
        assert "キュー" in rendered
        assert "面接対策です" in rendered


def test_intake_max_turns_is_small() -> None:
    assert 1 <= INTAKE_MAX_TURNS <= 5
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_intake_prompt.py -v`
Expected: FAIL

- [ ] **Step 3: `graph/prompts/intake.py` を実装する**

```python
"""聞き取り（目的・出典・前提知識）のプロンプト（learning_start / _intake.py 用）。"""

from graph.prompts._base import inject_charter

INTAKE_MAX_TURNS = 3

INTAKE_PROMPT = inject_charter(
    """\
## 役割
あなたはフレンドリーで傾聴力のある優秀なメンターです。常にユーザーの目線で寄り添うことを心がけてください。

## トピック
{topic}

（重要な前提）
- ユーザーの最初のメッセージは UI 入力のトピック名そのものであり、トピックに関する説明・知識・興味の表明ではない
- 「トピック」は UI 入力値である。ユーザーが「お伝えいただいた」「共有していただいた」と扱ってはならない
- ユーザーが触れていないトピックの内容（定義・分野説明・例示）を、LLM 側で先回りして提示しない

## これまでに分かっていること
- 目的（何ができるようになりたいか）: {purpose}
- 学習材料の出典: {source}
- 前提知識（今何を知っているか）: {prior_knowledge}

## 対話履歴（直近のみ）
{recent_messages}

## タスク
上記のうち「未回答」の項目だけを、1つの自然な問いにまとめて尋ねてください。
すでに分かっている項目を聞き返さないこと。

## ルール
- 1レスポンスにつき質問は1つ（複数の項目を尋ねる場合も、1つの文にまとめる）
- 「未回答」がひとつも無い場合は、聞き取りを終えて学習を始める短い一言を返す
- ユーザーが「早く始めたい」「特にない」のように答えを避けた場合は、深追いせず
  「大丈夫です、進めましょう」の趣旨で応じ、聞き取りを打ち切ってよい意思を尊重する
- 全項目が「未回答」なら、聞き取り全体をスキップしてよい選択肢も伝える
  （例:「特になければ、このまま始めても大丈夫です」）
- 日本語で応答する
- 「正しい」「間違い」のような評価はしない

## 例（すべて未回答の初回）
ユーザー: 「システムコール」（UI 入力のトピック名。3項目とも未回答）
AI: 「システムコールを学びたいんですね。
     今回、何かできるようになりたいことや気になっているきっかけはありますか？
     （特になければ、このまま始めても大丈夫です）」

## 例（目的のみ未回答）
既知: 出典=「Linuxのしくみ」、前提知識=「OSの授業を受けたことがある程度」
AI: 「『Linuxのしくみ』で学習されているんですね。OSの授業を受けたことがあるとのこと、
     心強いです。今回はどんなことができるようになりたいですか？」
"""
)

INTAKE_EXTRACTION_PROMPT = inject_charter(
    """\
あなたは学習セッション開始前の聞き取りを分析する専門家です。
ユーザーが「{topic}」を学ぼうとしています。直近のユーザー発言から、
IntakeExtraction スキーマに従って構造化して出力してください。

## これまでに分かっていること
- 目的: {purpose}
- 学習材料の出典: {source}
- 前提知識: {prior_knowledge}

## 対話履歴（直近のみ）
{recent_messages}

## タスク
1. `purpose` / `source` / `prior_knowledge`: 直近のユーザー発言に新しい情報があれば抽出する。
   言及が無い項目は空文字。「これまでに分かっていること」に既にある内容の言い換えは抽出しない
2. `ready_to_start`: ユーザーが聞き取りを打ち切って学習を始めたい意思（「特にない」「早く始めたい」等）
   を示しているか

## 厳守事項
{{NO_FABRICATION}}
"""
)


def _known(value: str) -> str:
    return value or "未回答"


def build_intake_prompt(*, topic: str, purpose: str, source: str, prior_knowledge: str, recent_messages: str) -> str:
    return INTAKE_PROMPT.format(
        topic=topic,
        purpose=_known(purpose),
        source=_known(source),
        prior_knowledge=_known(prior_knowledge),
        recent_messages=recent_messages or "（まだなし）",
    )


def build_intake_extraction_prompt(
    *, topic: str, purpose: str, source: str, prior_knowledge: str, recent_messages: str
) -> str:
    return INTAKE_EXTRACTION_PROMPT.format(
        topic=topic,
        purpose=_known(purpose),
        source=_known(source),
        prior_knowledge=_known(prior_knowledge),
        recent_messages=recent_messages or "（まだなし）",
    )
```

- [ ] **Step 4: テストを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_intake_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/prompts/intake.py tests/unit/graph/test_intake_prompt.py
git commit -m "feat(graph): add intake question and extraction prompts"
```

---

### Task 8: 聞き取りの構造化抽出ノード（`graph/nodes/_intake_analysis.py`）

**Files:**
- Create: `server/graph/nodes/_intake_analysis.py`
- Test: `server/tests/unit/graph/test_intake_analysis.py`

**Interfaces:**
- Consumes: `build_intake_extraction_prompt`（`graph.prompts.intake`）、`llm_structured` / `INTERNAL_LLM_TAG`（`graph.llm`）、`IntakeExtraction`（`graph.output_schemas`）
- Produces: `async def extract_intake(state: LearningState, *, recent_messages: str) -> IntakeExtraction | None`

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_intake_analysis.py`（`test_turn_analysis.py` と同じモック方式）:

```python
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from graph.nodes._intake_analysis import extract_intake
from graph.output_schemas import IntakeExtraction
from graph.state import LearningState

_STATE = cast(
    LearningState,
    {
        "user_id": "user-abc",
        "dialogue_session_id": UUID("00000000-0000-0000-0000-000000000002"),
        "note_id": UUID("00000000-0000-0000-0000-000000000001"),
        "messages": [],
        "topic": "システムコール",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "learning",
    },
)


async def _run(mock_invoke: AsyncMock) -> IntakeExtraction | None:
    mock_runnable = MagicMock(ainvoke=mock_invoke)
    mock_llm_structured = MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config.return_value = mock_runnable
    with patch("graph.nodes._intake_analysis.llm_structured", mock_llm_structured):
        return await extract_intake(_STATE, recent_messages="ユーザー: 面接対策です")


class TestExtractIntake:
    async def test_returns_extraction_on_success(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="", ready_to_start=False)
        result = await _run(AsyncMock(return_value=extraction))
        assert result is extraction

    async def test_returns_none_on_llm_failure(self) -> None:
        result = await _run(AsyncMock(side_effect=RuntimeError("llm down")))
        assert result is None

    async def test_returns_none_on_unexpected_payload(self) -> None:
        result = await _run(AsyncMock(return_value={"purpose": "面接対策"}))
        assert result is None

    async def test_prompt_includes_topic_and_history(self) -> None:
        extraction = IntakeExtraction(purpose="", source="", prior_knowledge="", ready_to_start=False)
        mock_invoke = AsyncMock(return_value=extraction)
        await _run(mock_invoke)
        prompt = mock_invoke.call_args.args[0][0].content
        assert "システムコール" in prompt
        assert "面接対策です" in prompt
        assert mock_invoke.call_args.kwargs["config"]["run_name"] == "extract-intake"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_intake_analysis.py -v`
Expected: FAIL

- [ ] **Step 3: `_intake_analysis.py` を実装する**

```python
"""聞き取り1ターンの構造化抽出（learning_dialogue の聞き取りフェーズ用）。

失敗しても聞き取りターン自体は止めず、None を返して呼び出し側に今回は抽出できなかった
扱いをさせる（_turn_analysis.py と同じフォールバック方針）。
"""

import logging

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.output_schemas import IntakeExtraction
from graph.prompts.intake import build_intake_extraction_prompt
from graph.state import LearningState

logger = logging.getLogger(__name__)


async def extract_intake(state: LearningState, *, recent_messages: str) -> IntakeExtraction | None:
    prompt = build_intake_extraction_prompt(
        topic=state["topic"],
        purpose=state.get("learning_goal") or "",
        source=state.get("learning_source") or "",
        prior_knowledge=state.get("prior_knowledge") or "",
        recent_messages=recent_messages,
    )
    runnable = llm_structured.with_structured_output(IntakeExtraction).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke([SystemMessage(content=prompt)], config={"run_name": "extract-intake"})
    except Exception:
        logger.warning("intake extraction failed", exc_info=True)
        return None
    if not isinstance(result, IntakeExtraction):
        logger.warning("intake extraction returned unexpected type %s", type(result).__name__)
        return None
    return result
```

- [ ] **Step 4: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_intake_analysis.py -v && uv run mypy graph/nodes/_intake_analysis.py`
Expected: PASS / `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/nodes/_intake_analysis.py tests/unit/graph/test_intake_analysis.py
git commit -m "feat(graph): add intake extraction node"
```

---

### Task 9: 地図駆動の事前分析（プロンプト＋ノード）

**Files:**
- Create: `server/graph/prompts/map_turn_analysis.py`
- Create: `server/graph/nodes/_map_turn_analysis.py`
- Test: `server/tests/unit/graph/test_map_turn_analysis.py`

**Interfaces:**
- Consumes: `format_map_coverage`（`graph.depth_map`）、`MapDialogueTurnAnalysis`（`graph.output_schemas`）、`DepthMapState` / `MapAspectProgress`（`graph.state`）
- Produces:
  - `build_map_turn_analysis_prompt(*, topic: str, recent_messages: str, plan_fields: dict[str, str], depth_map: DepthMapState, map_covered: list[MapAspectProgress]) -> str`
  - `async def analyze_map_dialogue_turn(state: LearningState, *, recent_messages: str, plan_fields: dict[str, str], depth_map: DepthMapState, map_covered: list[MapAspectProgress]) -> MapDialogueTurnAnalysis | None`

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_map_turn_analysis.py`:

```python
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from graph.depth_map import build_depth_map
from graph.nodes._map_turn_analysis import analyze_map_dialogue_turn
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation, MapDialogueTurnAnalysis
from graph.state import LearningState, MapAspectProgress

_STATE = cast(
    LearningState,
    {
        "user_id": "user-abc",
        "dialogue_session_id": UUID("00000000-0000-0000-0000-000000000002"),
        "note_id": UUID("00000000-0000-0000-0000-000000000001"),
        "messages": [],
        "topic": "システムコール",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "learning",
    },
)

_PLAN_FIELDS = {"learning_goal": "未指定", "focus_aspects": "未指定"}

_DEPTH_MAP = build_depth_map(
    "システムコール",
    [
        DepthMapAspectDraft(
            name="システムコールの定義",
            is_core=True,
            defined_question="定義できるか",
            reasoned_question="なぜ必要か",
            applied_question="どう活かすか",
        )
    ],
)
_ASPECT_ID = _DEPTH_MAP["aspects"][0]["id"]


async def _run(mock_invoke: AsyncMock, *, covered: list[MapAspectProgress] | None = None) -> MapDialogueTurnAnalysis | None:
    mock_runnable = MagicMock(ainvoke=mock_invoke)
    mock_llm_structured = MagicMock()
    mock_llm_structured.with_structured_output.return_value.with_config.return_value = mock_runnable
    with patch("graph.nodes._map_turn_analysis.llm_structured", mock_llm_structured):
        return await analyze_map_dialogue_turn(
            _STATE,
            recent_messages="ユーザー: システムコールとは…",
            plan_fields=_PLAN_FIELDS,
            depth_map=_DEPTH_MAP,
            map_covered=covered or [],
        )


class TestAnalyzeMapDialogueTurn:
    async def test_returns_analysis_on_success(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="defined")],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id=_ASPECT_ID,
        )
        result = await _run(AsyncMock(return_value=analysis))
        assert result is analysis

    async def test_returns_none_on_llm_failure(self) -> None:
        result = await _run(AsyncMock(side_effect=RuntimeError("llm down")))
        assert result is None

    async def test_prompt_lists_aspect_ids_and_topic(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        mock_invoke = AsyncMock(return_value=analysis)
        await _run(mock_invoke)
        prompt = mock_invoke.call_args.args[0][0].content
        assert "システムコール" in prompt
        assert _ASPECT_ID in prompt
        assert mock_invoke.call_args.kwargs["config"]["run_name"] == "map-turn-analysis"

    async def test_a_flagged_misconception_forces_reinforce(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[],
            has_misconception=True,
            error_summary="誤り",
            response_mode="deepen",
            selected_aspect_id=_ASPECT_ID,
        )
        result = await _run(AsyncMock(return_value=analysis))
        assert result is not None
        assert result.response_mode == "reinforce"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_map_turn_analysis.py -v`
Expected: FAIL

- [ ] **Step 3: `graph/prompts/map_turn_analysis.py` を実装する**

```python
"""地図駆動の学習対話 1 ターンの事前分析プロンプト。graph/prompts/turn_analysis.py の地図版。"""

from graph.depth_map import format_map_coverage
from graph.prompts._base import inject_charter
from graph.state import DepthMapState, MapAspectProgress

MAP_TURN_ANALYSIS_PROMPT = inject_charter(
    """\
あなたは学習対話の 1 ターンを分析する専門家です。
ユーザーが「{topic}」について自分の言葉で説明しています。
直近のユーザー発言を分析し、MapDialogueTurnAnalysis スキーマに従って構造化して出力してください。

## 学習プラン
- 学習ゴール: {learning_goal}
- 重視する観点: {focus_aspects}

## この学習の観点地図
{aspect_list}

## これまでにカバー済みの観点と到達度（過去ターン累積）
{coverage_block}

## 対話履歴（直近のみ）
{recent_messages}

## タスク
以下の順に判定する。2 を飛ばして 4 に進まない。

1. `observations`: 直近のユーザー発言で言及・説明された観点と、その発言で到達した段階
   - mentioned=名前を挙げただけ / defined=定義を自分の言葉で述べた /
     reasoned=なぜ必要か・どう動くかを述べた（日常の具体例を1つ挙げただけでは reasoned にしない）/
     applied=学習ゴールに沿った具体的な活用場面まで述べた
   - `aspect_id` は「この学習の観点地図」に載っている id をそのまま使う。
     地図に無い話題なら、id の代わりに分かりやすい仮の名前（日本語可）を入れてよい
2. `has_misconception`: 直近のユーザー発言に、訂正を要する誤り・混同が含まれるか
   - 述べられている内容が正しいかを、段階とは別に必ず検査する
   - 説明が浅い・言葉足らずなだけで、述べられている範囲は正しいものは誤りではない
3. `error_summary`: `has_misconception` が true なら、何がどう違うのかを 1 文で。false なら空文字
4. `response_mode`: 次の AI 応答のモード
   - `has_misconception` が true → 必ず reinforce
   - false のときだけ、段階で次のどちらかを選ぶ
     - deepen: 直近の説明が単一観点で reasoned 段階に届いていない
     - expand: 直近の説明が十分。複数観点が一度に列挙され各観点に最低限の定義があれば、
       個々の観点が defined 止まりでも expand を優先する
   - 到達目標は reasoned（なぜ・仕組みまで述べた）
5. `selected_aspect_id`: 次の応答で焦点を当てる観点を1つ
   - reinforce のときは、誤りを含む観点を選ぶ
   - それ以外の選定基準: 中核観点の未到達 > 到達度が reasoned に最も届いていない既出観点 > 既出順
   - observations と同じ解決規則で id または仮の名前を使う

## 厳守事項
{{NO_FABRICATION}}
"""
)

_EMPTY_COVERAGE_PLACEHOLDER = "（まだなし）"


def _format_aspect_list(depth_map: DepthMapState) -> str:
    return "\n".join(f"- id: {a['id']} / {a['name']}" + ("（中核）" if a["is_core"] else "") for a in depth_map["aspects"])


def build_map_turn_analysis_prompt(
    *,
    topic: str,
    recent_messages: str,
    plan_fields: dict[str, str],
    depth_map: DepthMapState,
    map_covered: list[MapAspectProgress],
) -> str:
    coverage_block = format_map_coverage(map_covered, depth_map) or _EMPTY_COVERAGE_PLACEHOLDER
    return MAP_TURN_ANALYSIS_PROMPT.format(
        topic=topic,
        recent_messages=recent_messages,
        aspect_list=_format_aspect_list(depth_map),
        coverage_block=coverage_block,
        **plan_fields,
    )
```

- [ ] **Step 4: `graph/nodes/_map_turn_analysis.py` を実装する**

```python
"""地図駆動の学習対話 1 ターンの事前分析（観測 + 応答モード決定）。graph/nodes/_turn_analysis.py の地図版。"""

import logging

from langchain_core.messages import SystemMessage

from graph.llm import INTERNAL_LLM_TAG, llm_structured
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts.map_turn_analysis import build_map_turn_analysis_prompt
from graph.state import DepthMapState, LearningState, MapAspectProgress

logger = logging.getLogger(__name__)


async def analyze_map_dialogue_turn(
    state: LearningState,
    *,
    recent_messages: str,
    plan_fields: dict[str, str],
    depth_map: DepthMapState,
    map_covered: list[MapAspectProgress],
) -> MapDialogueTurnAnalysis | None:
    prompt = build_map_turn_analysis_prompt(
        topic=state["topic"],
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        depth_map=depth_map,
        map_covered=map_covered,
    )
    runnable = llm_structured.with_structured_output(MapDialogueTurnAnalysis).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke([SystemMessage(content=prompt)], config={"run_name": "map-turn-analysis"})
    except Exception:
        logger.warning("map turn analysis failed; falling back", exc_info=True)
        return None
    if not isinstance(result, MapDialogueTurnAnalysis):
        logger.warning("map turn analysis returned unexpected type %s", type(result).__name__)
        return None
    return _with_mode_from_misconception(result)


def _with_mode_from_misconception(analysis: MapDialogueTurnAnalysis) -> MapDialogueTurnAnalysis:
    if not analysis.has_misconception or analysis.response_mode == "reinforce":
        return analysis
    logger.warning("map turn analysis flagged a misconception but chose %s; forcing reinforce", analysis.response_mode)
    return analysis.model_copy(update={"response_mode": "reinforce"})
```

- [ ] **Step 5: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_map_turn_analysis.py -v && uv run mypy graph/prompts/map_turn_analysis.py graph/nodes/_map_turn_analysis.py`
Expected: PASS / `Success: no issues found`

- [ ] **Step 6: Commit**

```bash
cd server && git add graph/prompts/map_turn_analysis.py graph/nodes/_map_turn_analysis.py tests/unit/graph/test_map_turn_analysis.py
git commit -m "feat(graph): add map-driven turn analysis"
```

---

### Task 10: 地図駆動の応答生成プロンプト（`graph/prompts/map_question.py`）

**Files:**
- Create: `server/graph/prompts/map_question.py`
- Test: `server/tests/unit/graph/test_map_question_prompt.py`

**Interfaces:**
- Consumes: `build_mode_section` / `classify_user_intent` / `MODE_HINT` / `MODE_UNKNOWN_A` / `MODE_UNKNOWN_B` / `MODE_UNKNOWN_C` / `MODE_WRAP_UP` / `MODE_DIALOGUE` / `QUESTION_PROMPT_BASE` / `UserIntent`（`graph.prompts.question`）、`format_map_coverage` / `next_stage` / `question_for`（`graph.depth_map`）
- Produces: `build_map_question_prompt(*, topic: str, recent_messages: str, plan_fields: dict[str, str], messages: Sequence[Any], depth_map: DepthMapState, map_covered: Sequence[MapAspectProgress], turn_analysis: MapDialogueTurnAnalysis | None, wrap_up: bool = False) -> tuple[str, UserIntent]`

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_map_question_prompt.py`:

```python
from langchain_core.messages import HumanMessage

from graph.depth_map import build_depth_map
from graph.output_schemas import DepthMapAspectDraft, MapDialogueTurnAnalysis
from graph.prompts.map_question import build_map_question_prompt

_PLAN_FIELDS = {"learning_goal": "未指定", "focus_aspects": "未指定"}


def _depth_map():
    return build_depth_map(
        "システムコール",
        [
            DepthMapAspectDraft(
                name="システムコールの定義",
                is_core=True,
                defined_question="定義できるか",
                reasoned_question="なぜカーネル経由なのか",
                applied_question="strace でどう調べるか",
            )
        ],
    )


class TestBuildMapQuestionPrompt:
    def test_dialogue_intent_injects_the_aspect_core_question(self) -> None:
        depth_map = _depth_map()
        aspect_id = depth_map["aspects"][0]["id"]
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=aspect_id
        )
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="ユーザー: システムコールとは…",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="システムコールとはカーネルに処理を頼む方法です")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=analysis,
        )
        assert intent == "dialogue"
        assert "なぜカーネル経由なのか" in prompt
        assert "日常的な具体例だけで終わらせない" in prompt

    def test_wrap_up_overrides_the_mode_section(self) -> None:
        depth_map = _depth_map()
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="なるほど、分かりました")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=None,
            wrap_up=True,
        )
        assert intent == "dialogue"
        assert "区切りの提案" in prompt

    def test_missing_analysis_falls_back_to_self_judged_mode(self) -> None:
        depth_map = _depth_map()
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="なるほど")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=None,
        )
        assert intent == "dialogue"
        assert "応答モードの判定原則" in prompt

    def test_unknown_intent_uses_the_hint_mode(self) -> None:
        depth_map = _depth_map()
        prompt, intent = build_map_question_prompt(
            topic="システムコール",
            recent_messages="",
            plan_fields=_PLAN_FIELDS,
            messages=[HumanMessage(content="わかりません")],
            depth_map=depth_map,
            map_covered=[],
            turn_analysis=None,
        )
        assert intent == "unknown_a"
        assert "全般的な不知" in prompt
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_map_question_prompt.py -v`
Expected: FAIL

- [ ] **Step 3: `graph/prompts/map_question.py` を実装する**

```python
"""地図駆動の学習対話の応答生成プロンプト。question.py のモード構造を再利用する。"""

from collections.abc import Sequence
from typing import Any

from graph.depth_map import format_map_coverage, next_stage, question_for
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts.question import (
    MODE_DIALOGUE,
    MODE_HINT,
    MODE_UNKNOWN_A,
    MODE_UNKNOWN_B,
    MODE_UNKNOWN_C,
    MODE_WRAP_UP,
    QUESTION_PROMPT_BASE,
    UserIntent,
    build_mode_section,
    classify_user_intent,
)
from graph.state import DepthMapState, MapAspectProgress

_MODE_SECTIONS: dict[UserIntent, str] = {
    "exhausted": MODE_HINT,
    "unknown_a": MODE_UNKNOWN_A,
    "unknown_b": MODE_UNKNOWN_B,
    "unknown_c": MODE_UNKNOWN_C,
}


def _reached_stage(aspect_id: str, map_covered: Sequence[MapAspectProgress]) -> str | None:
    for c in map_covered:
        if c["aspect_id"] == aspect_id:
            return c["reached_stage"]
    return None


def _build_map_dialogue_section(
    analysis: MapDialogueTurnAnalysis, depth_map: DepthMapState, map_covered: Sequence[MapAspectProgress]
) -> str:
    aspect = next((a for a in depth_map["aspects"] if a["id"] == analysis.selected_aspect_id), None)
    if aspect is None:
        return build_mode_section(
            response_mode=analysis.response_mode,
            selected_aspect_label=analysis.selected_aspect_id,
            error_summary=analysis.error_summary,
        )
    target_stage = next_stage(_reached_stage(aspect["id"], map_covered))  # type: ignore[arg-type]
    hint = (
        "### この観点の核心（地図より）\n"
        f"{question_for(aspect, target_stage)}\n"
        "この核心に向かって問いを組み立てる。日常的な具体例だけで終わらせない。"
    )
    return build_mode_section(
        response_mode=analysis.response_mode,
        selected_aspect_label=aspect["name"],
        error_summary=analysis.error_summary,
        extra_hint=hint,
    )


def _build_coverage_section(map_covered: Sequence[MapAspectProgress], depth_map: DepthMapState) -> str:
    lines = format_map_coverage(map_covered, depth_map)
    if not lines:
        return ""
    return (
        "## カバー済み観点と到達度（過去ターン累積）\n"
        f"{lines}\n"
        "上記の観点は記載の段階まで説明済みとして扱い、同じ深さの質問を繰り返さない。\n\n"
    )


def build_map_question_prompt(
    *,
    topic: str,
    recent_messages: str,
    plan_fields: dict[str, str],
    messages: Sequence[Any],
    depth_map: DepthMapState,
    map_covered: Sequence[MapAspectProgress],
    turn_analysis: MapDialogueTurnAnalysis | None,
    wrap_up: bool = False,
) -> tuple[str, UserIntent]:
    intent = classify_user_intent(messages)
    if intent == "dialogue" and wrap_up:
        mode_section = MODE_WRAP_UP
    elif intent == "dialogue" and turn_analysis is not None:
        mode_section = _build_map_dialogue_section(turn_analysis, depth_map, map_covered)
    elif intent == "dialogue":
        mode_section = MODE_DIALOGUE
    else:
        mode_section = _MODE_SECTIONS[intent]
    template = QUESTION_PROMPT_BASE + "\n" + mode_section
    prompt = template.format(
        topic=topic,
        recent_messages=recent_messages,
        coverage_section=_build_coverage_section(map_covered, depth_map),
        **plan_fields,
    )
    return prompt, intent
```

- [ ] **Step 4: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_map_question_prompt.py -v && uv run mypy graph/prompts/map_question.py`
Expected: PASS（型エラーが出た場合は `_reached_stage` の戻り値注釈を `MapStage | None` に変更し `# type: ignore` を外す）

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/prompts/map_question.py tests/unit/graph/test_map_question_prompt.py
git commit -m "feat(graph): add map-driven question prompt composition"
```

---

### Task 11: 地図駆動の対話ノード（`graph/nodes/_map_dialogue.py`）

**Files:**
- Create: `server/graph/nodes/_map_dialogue.py`
- Test: `server/tests/unit/graph/test_map_dialogue.py`

**Interfaces:**
- Consumes: `analyze_map_dialogue_turn`（`graph.nodes._map_turn_analysis`）、`build_map_question_prompt`（`graph.prompts.map_question`）、`depth_map_progress` / `merge_map_coverage`（`graph.depth_map`）、`recent_messages_block`（`graph.nodes._shared`）
- Produces:
  - `@dataclass(frozen=True) class MapTurnPlan: depth_map: DepthMapState; map_covered: list[MapAspectProgress] = field(default_factory=list); analysis: MapDialogueTurnAnalysis | None = None; wrap_up: bool = False`
  - `async def prepare_map_turn(state: LearningState) -> MapTurnPlan`
  - `async def respond_map(state: LearningState, plan: MapTurnPlan) -> dict[str, Any]`

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_map_dialogue.py`（`test_learning_dialogue.py` と同じモック方式）:

```python
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.depth_map import build_depth_map
from graph.output_schemas import DepthMapAspectDraft, MapAspectObservation, MapDialogueTurnAnalysis
from graph.state import LearningState, MapAspectProgress

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")

_DEPTH_MAP = build_depth_map(
    "システムコール",
    [
        DepthMapAspectDraft(
            name="システムコールの定義",
            is_core=True,
            defined_question="定義できるか",
            reasoned_question="なぜ必要か",
            applied_question="どう活かすか",
        )
    ],
)
_ASPECT_ID = _DEPTH_MAP["aspects"][0]["id"]

_FAKE_PROMPT = MagicMock(return_value=("QUESTION_PROMPT", "dialogue"))
_NO_ANALYSIS = AsyncMock(return_value=None)


def _make_state(messages: list[Any], **overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": messages,
        "topic": "システムコール",
        "turn_count": 2,
        "should_generate_note": False,
        "session_type": "learning",
        "depth_map": _DEPTH_MAP,
    }
    base.update(overrides)
    return cast(LearningState, base)


class TestPrepareMapTurn:
    async def test_merges_observations_into_map_covered(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="defined")],
            has_misconception=False,
            response_mode="deepen",
            selected_aspect_id=_ASPECT_ID,
        )
        with patch(
            "graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)
        ):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="システムコールとは…")]))

        assert plan.map_covered == [{"aspect_id": _ASPECT_ID, "reached_stage": "defined"}]

    async def test_offers_wrap_up_when_core_aspects_reach_reasoned(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[MapAspectObservation(aspect_id=_ASPECT_ID, reached_stage="reasoned")],
            has_misconception=False,
            response_mode="expand",
            selected_aspect_id=_ASPECT_ID,
        )
        with patch(
            "graph.nodes._map_dialogue.analyze_map_dialogue_turn", AsyncMock(return_value=analysis)
        ):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="なぜカーネル経由か説明できます")]))

        assert plan.wrap_up is True

    async def test_analysis_failure_keeps_existing_coverage(self) -> None:
        existing: list[MapAspectProgress] = [{"aspect_id": _ASPECT_ID, "reached_stage": "defined"}]
        with patch("graph.nodes._map_dialogue.analyze_map_dialogue_turn", _NO_ANALYSIS):
            from graph.nodes._map_dialogue import prepare_map_turn

            plan = await prepare_map_turn(_make_state([HumanMessage(content="わかりません")], map_covered=existing))

        assert plan.map_covered == existing
        assert plan.wrap_up is False


class TestRespondMap:
    async def test_increments_turn_count_and_returns_depth_map(self) -> None:
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            result = await respond_map(
                _make_state([HumanMessage(content="hi")], turn_count=2),
                MapTurnPlan(depth_map=_DEPTH_MAP),
            )

        assert result["turn_count"] == 3
        assert result["depth_map"] == _DEPTH_MAP
        assert result["should_generate_note"] is False

    async def test_persists_the_resolved_aspect_name_in_turn_analysis(self) -> None:
        analysis = MapDialogueTurnAnalysis(
            observations=[], has_misconception=False, response_mode="deepen", selected_aspect_id=_ASPECT_ID
        )
        with (
            patch(
                "graph.nodes._map_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes._map_dialogue.build_map_question_prompt", _FAKE_PROMPT),
        ):
            from graph.nodes._map_dialogue import MapTurnPlan, respond_map

            result = await respond_map(
                _make_state([HumanMessage(content="hi")]),
                MapTurnPlan(depth_map=_DEPTH_MAP, analysis=analysis),
            )

        assert result["turn_analysis"]["selected_aspect"] == "システムコールの定義"
        assert result["turn_analysis"]["selected_aspect_id"] == _ASPECT_ID
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_map_dialogue.py -v`
Expected: FAIL

- [ ] **Step 3: `graph/nodes/_map_dialogue.py` を実装する**

```python
"""地図駆動の学習対話（聞き取り完了後）。learning_dialogue.py の legacy TurnPlan/prepare_turn/respond と対になる。"""

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from graph.depth_map import depth_map_progress, merge_map_coverage
from graph.llm import llm
from graph.multimodal import load_image_blocks
from graph.nodes._map_turn_analysis import analyze_map_dialogue_turn
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import MapDialogueTurnAnalysis
from graph.prompts import format_learning_plan_fields
from graph.prompts.map_question import build_map_question_prompt
from graph.prompts.question import classify_user_intent
from graph.state import DepthMapState, LearningState, MapAspectProgress, TurnAnalysisRecord
from storage import get_storage


@dataclass(frozen=True)
class MapTurnPlan:
    """事前分析が決めた、このターンのプロンプトへ注入する値。"""

    depth_map: DepthMapState
    map_covered: list[MapAspectProgress] = field(default_factory=list)
    analysis: MapDialogueTurnAnalysis | None = None
    wrap_up: bool = False


def _to_record(plan: MapTurnPlan) -> TurnAnalysisRecord | None:
    if plan.analysis is None:
        return None
    aspect = next((a for a in plan.depth_map["aspects"] if a["id"] == plan.analysis.selected_aspect_id), None)
    label = aspect["name"] if aspect else plan.analysis.selected_aspect_id
    return TurnAnalysisRecord(
        response_mode=plan.analysis.response_mode,
        selected_aspect=label,
        selected_aspect_id=plan.analysis.selected_aspect_id,
        has_misconception=plan.analysis.has_misconception,
        error_summary=plan.analysis.error_summary,
        wrap_up=plan.wrap_up,
    )


def _turn_context(state: LearningState) -> tuple[str, dict[str, str]]:
    recent_messages = recent_messages_block(state)
    plan_fields = format_learning_plan_fields(
        learning_goal=state.get("learning_goal"),
        focus_aspects=state.get("focus_aspects"),
    )
    return recent_messages, plan_fields


async def prepare_map_turn(state: LearningState) -> MapTurnPlan:
    depth_map = state["depth_map"]
    map_covered: list[MapAspectProgress] = list(state.get("map_covered") or [])
    recent_messages, plan_fields = _turn_context(state)
    analysis: MapDialogueTurnAnalysis | None = None
    if classify_user_intent(state["messages"]) == "dialogue":
        analysis = await analyze_map_dialogue_turn(
            state,
            recent_messages=recent_messages,
            plan_fields=plan_fields,
            depth_map=depth_map,
            map_covered=map_covered,
        )
        if analysis is not None:
            map_covered, depth_map = merge_map_coverage(map_covered, analysis.observations, depth_map)
    wrap_up = (
        analysis is not None
        and not analysis.has_misconception
        and not state.get("wrap_up_offered")
        and depth_map_progress(map_covered, depth_map).is_complete
    )
    return MapTurnPlan(depth_map=depth_map, map_covered=map_covered, analysis=analysis, wrap_up=wrap_up)


async def respond_map(state: LearningState, plan: MapTurnPlan) -> dict[str, Any]:
    recent_messages, plan_fields = _turn_context(state)
    question_prompt, intent = build_map_question_prompt(
        topic=state["topic"],
        recent_messages=recent_messages,
        plan_fields=plan_fields,
        messages=state["messages"],
        depth_map=plan.depth_map,
        map_covered=plan.map_covered,
        turn_analysis=plan.analysis,
        wrap_up=plan.wrap_up,
    )
    llm_messages: list[BaseMessage] = [SystemMessage(content=question_prompt)]
    if state["messages"]:
        image_blocks = await load_image_blocks(state["messages"][-1], get_storage())
        if image_blocks:
            llm_messages.append(HumanMessage(content=image_blocks))

    response = await llm.ainvoke(
        llm_messages,
        config={
            "metadata": {
                "intent": intent,
                "response_mode": plan.analysis.response_mode if plan.analysis else None,
                "selected_aspect_id": plan.analysis.selected_aspect_id if plan.analysis else None,
                "wrap_up": plan.wrap_up,
            }
        },
    )

    return {
        "messages": [response],
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
        "depth_map": plan.depth_map,
        "map_covered": plan.map_covered,
        "turn_analysis": _to_record(plan),
        "wrap_up_offered": bool(state.get("wrap_up_offered")) or plan.wrap_up,
    }
```

- [ ] **Step 4: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_map_dialogue.py -v && uv run mypy graph/nodes/_map_dialogue.py`
Expected: PASS / `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/nodes/_map_dialogue.py tests/unit/graph/test_map_dialogue.py
git commit -m "feat(graph): add map-driven dialogue prepare/respond"
```

---

### Task 12: 聞き取りフェーズのターン処理（`graph/nodes/_intake.py`）

**Files:**
- Create: `server/graph/nodes/_intake.py`
- Test: `server/tests/unit/graph/test_intake.py`

**Interfaces:**
- Consumes: `extract_intake`（`_intake_analysis`）、`prepare_map_turn` / `respond_map`（`_map_dialogue`）、`build_depth_map`（`graph.depth_map`）、`build_depth_map_prompt`（`graph.prompts.depth_map`）、`build_intake_prompt` / `INTAKE_MAX_TURNS`（`graph.prompts.intake`）
- Produces: `async def handle_intake_turn(state: LearningState) -> dict[str, Any]`
  - 契約: 戻り値に `"messages"` キーが**無い**場合、そのターンは地図生成に失敗しており、
    呼び出し元（`learning_dialogue` のルーター）が legacy 経路で応答を生成する責務を持つ
    （`_intake.py` から `learning_dialogue.py` を import すると循環 import になるため）

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_intake.py`:

```python
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from graph.output_schemas import DepthMapGeneration, IntakeExtraction, MapDialogueTurnAnalysis
from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_state(messages: list[Any], **overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": messages,
        "topic": "システムコール",
        "turn_count": 1,
        "should_generate_note": False,
        "session_type": "learning",
        "intake_complete": False,
        "intake_turns": 0,
    }
    base.update(overrides)
    return cast(LearningState, base)


class TestHandleIntakeTurnIncomplete:
    async def test_asks_the_next_question_when_fields_still_missing(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="", ready_to_start=False)
        response = AIMessage(content="出典はありますか？")
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch("graph.nodes._intake.llm", MagicMock(ainvoke=AsyncMock(return_value=response))),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="面接対策です")]))

        assert result["intake_complete"] is False
        assert result["intake_turns"] == 1
        assert result["learning_goal"] == "面接対策"
        assert result["messages"] == [response]

    async def test_extraction_failure_keeps_prior_values_and_does_not_crash(self) -> None:
        response = AIMessage(content="もう一度教えてください")
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=None)),
            patch("graph.nodes._intake.llm", MagicMock(ainvoke=AsyncMock(return_value=response))),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(
                _make_state([HumanMessage(content="わかりません")], learning_goal="面接対策")
            )

        assert result["learning_goal"] == "面接対策"
        assert result["intake_complete"] is False

    async def test_stops_after_reaching_the_turn_limit(self) -> None:
        extraction = IntakeExtraction(purpose="", source="", prior_knowledge="", ready_to_start=False)
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch(
                "graph.nodes._intake._generate_depth_map",
                AsyncMock(return_value={"topic": "システムコール", "aspects": [{"id": "a", "name": "A", "is_core": True, "defined_question": "d", "reasoned_question": "r", "applied_question": "ap"}]}),
            ),
            patch(
                "graph.nodes._intake.prepare_map_turn",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "graph.nodes._intake.respond_map",
                AsyncMock(return_value={"messages": [AIMessage(content="始めましょう")], "turn_count": 3}),
            ),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="特にありません")], intake_turns=2))

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 3


class TestHandleIntakeTurnCompletion:
    async def test_all_three_fields_in_one_reply_completes_in_one_turn(self) -> None:
        """目的・出典・前提知識を一度に全部話した場合、聞き取りが1ターンで完了し1メッセージで返る。"""
        extraction = IntakeExtraction(
            purpose="面接対策", source="Linuxのしくみ", prior_knowledge="OSの授業を受けた", ready_to_start=False
        )
        map_response = {
            "messages": [AIMessage(content="では始めましょう")],
            "turn_count": 2,
            "depth_map": {"topic": "t", "aspects": []},
            "map_covered": [],
        }
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch(
                "graph.nodes._intake._generate_depth_map",
                AsyncMock(
                    return_value={
                        "topic": "システムコール",
                        "aspects": [
                            {
                                "id": "a",
                                "name": "A",
                                "is_core": True,
                                "defined_question": "d",
                                "reasoned_question": "r",
                                "applied_question": "ap",
                            }
                        ],
                    }
                ),
            ),
            patch("graph.nodes._intake.prepare_map_turn", AsyncMock(return_value=MagicMock())),
            patch("graph.nodes._intake.respond_map", AsyncMock(return_value=map_response)),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(
                _make_state([HumanMessage(content="面接対策で、Linuxのしくみで学んでいて、OSの授業を受けたことがあります")])
            )

        assert result["intake_complete"] is True
        assert result["intake_turns"] == 1
        assert result["messages"] == map_response["messages"]

    async def test_ready_to_start_completes_in_one_turn_and_returns_a_single_message(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="", prior_knowledge="", ready_to_start=True)
        map_response = {"messages": [AIMessage(content="では始めましょう")], "turn_count": 2, "depth_map": {"topic": "t", "aspects": []}, "map_covered": []}
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch(
                "graph.nodes._intake._generate_depth_map",
                AsyncMock(return_value={"topic": "システムコール", "aspects": [{"id": "a", "name": "A", "is_core": True, "defined_question": "d", "reasoned_question": "r", "applied_question": "ap"}]}),
            ),
            patch("graph.nodes._intake.prepare_map_turn", AsyncMock(return_value=MagicMock())),
            patch("graph.nodes._intake.respond_map", AsyncMock(return_value=map_response)),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="特に無いので始めたいです")]))

        assert result["intake_complete"] is True
        assert result["messages"] == map_response["messages"]

    async def test_depth_map_generation_failure_returns_no_messages_key(self) -> None:
        extraction = IntakeExtraction(purpose="面接対策", source="本", prior_knowledge="なし", ready_to_start=False)
        with (
            patch("graph.nodes._intake.extract_intake", AsyncMock(return_value=extraction)),
            patch("graph.nodes._intake._generate_depth_map", AsyncMock(return_value=None)),
        ):
            from graph.nodes._intake import handle_intake_turn

            result = await handle_intake_turn(_make_state([HumanMessage(content="本で勉強してます")]))

        assert result["intake_complete"] is True
        assert "messages" not in result
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_intake.py -v`
Expected: FAIL

- [ ] **Step 3: `graph/nodes/_intake.py` を実装する**

```python
"""聞き取り（目的・出典・前提知識）フェーズの処理。intake_complete=False のターンで呼ばれる。

完了ターンで地図生成が失敗した場合、`messages` を含まない dict を返す。
その場合は呼び出し元（learning_dialogue のルーター）が legacy 経路で応答を生成する
（このモジュールから legacy の prepare_turn/respond を呼ぶと learning_dialogue.py との
circular import になるため、responsibility を呼び出し元へ返す）。
"""

import logging
from typing import Any

from langchain_core.messages import SystemMessage

from graph.depth_map import build_depth_map
from graph.llm import INTERNAL_LLM_TAG, llm, llm_structured
from graph.nodes._intake_analysis import extract_intake
from graph.nodes._map_dialogue import prepare_map_turn, respond_map
from graph.nodes._shared import recent_messages_block
from graph.output_schemas import DepthMapGeneration
from graph.prompts.depth_map import build_depth_map_prompt
from graph.prompts.intake import INTAKE_MAX_TURNS, build_intake_prompt
from graph.state import DepthMapState, LearningState

logger = logging.getLogger(__name__)


def _merge_field(existing: str | None, extracted: str) -> str:
    return extracted or (existing or "")


async def _generate_depth_map(*, topic: str, purpose: str, source: str, prior_knowledge: str) -> DepthMapState | None:
    prompt = build_depth_map_prompt(topic=topic, purpose=purpose, source=source, prior_knowledge=prior_knowledge)
    runnable = llm_structured.with_structured_output(DepthMapGeneration).with_config(tags=[INTERNAL_LLM_TAG])
    try:
        result = await runnable.ainvoke([SystemMessage(content=prompt)], config={"run_name": "generate-depth-map"})
    except Exception:
        logger.warning("depth map generation failed", exc_info=True)
        return None
    if not isinstance(result, DepthMapGeneration) or not result.aspects:
        logger.warning("depth map generation returned no aspects")
        return None
    return build_depth_map(topic, result.aspects)


async def handle_intake_turn(state: LearningState) -> dict[str, Any]:
    recent_messages = recent_messages_block(state)
    extraction = await extract_intake(state, recent_messages=recent_messages)

    purpose = _merge_field(state.get("learning_goal"), extraction.purpose if extraction else "")
    source = _merge_field(state.get("learning_source"), extraction.source if extraction else "")
    prior_knowledge = _merge_field(state.get("prior_knowledge"), extraction.prior_knowledge if extraction else "")
    turns = state.get("intake_turns", 0) + 1
    ready = bool(extraction and extraction.ready_to_start)
    complete = ready or turns >= INTAKE_MAX_TURNS or bool(purpose and source and prior_knowledge)

    base_updates: dict[str, Any] = {
        "intake_complete": complete,
        "intake_turns": turns,
        "learning_goal": purpose,
        "learning_source": source,
        "prior_knowledge": prior_knowledge,
        "turn_count": state["turn_count"] + 1,
        "should_generate_note": False,
    }

    if not complete:
        prompt = build_intake_prompt(
            topic=state["topic"],
            purpose=purpose,
            source=source,
            prior_knowledge=prior_knowledge,
            recent_messages=recent_messages,
        )
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        return {**base_updates, "messages": [response]}

    depth_map = await _generate_depth_map(topic=state["topic"], purpose=purpose, source=source, prior_knowledge=prior_knowledge)
    if depth_map is None:
        return base_updates

    first_turn_state: LearningState = {**state, **base_updates, "depth_map": depth_map, "map_covered": []}
    plan = await prepare_map_turn(first_turn_state)
    result = await respond_map(first_turn_state, plan)
    return {**base_updates, **result}
```

- [ ] **Step 4: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_intake.py -v && uv run mypy graph/nodes/_intake.py`
Expected: PASS / `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/nodes/_intake.py tests/unit/graph/test_intake.py
git commit -m "feat(graph): add intake turn handling"
```

---

### Task 13: `learning_start` を聞き取りの最初の問いに書き換える

**Files:**
- Modify: `server/graph/nodes/learning_start.py`
- Delete: `server/graph/prompts/learning_planner.py`
- Delete: `server/tests/unit/graph/test_learning_planner_prompt.py`
- Modify: `server/graph/prompts/__init__.py`
- Test: `server/tests/unit/graph/test_learning_start.py`（新規）

**Interfaces:**
- Consumes: `build_intake_prompt`（`graph.prompts.intake`）

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/graph/test_learning_start.py`:

```python
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from langchain_core.messages import AIMessage

from graph.state import LearningState

SESSION_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _state(**overrides: object) -> LearningState:
    base: dict[str, object] = {
        "user_id": "user-abc",
        "dialogue_session_id": SESSION_ID,
        "note_id": NOTE_ID,
        "messages": [],
        "topic": "システムコール",
        "turn_count": 0,
        "should_generate_note": False,
        "session_type": "learning",
    }
    base.update(overrides)
    return cast(LearningState, base)


class TestLearningStart:
    async def test_starts_intake_and_sets_turn_count(self) -> None:
        response = AIMessage(content="今回できるようになりたいことはありますか？")
        with patch("graph.nodes.learning_start.llm", MagicMock(ainvoke=AsyncMock(return_value=response))):
            from graph.nodes.learning_start import learning_start

            result = await learning_start(_state())

        assert result["turn_count"] == 1
        assert result["intake_complete"] is False
        assert result["intake_turns"] == 0
        assert result["should_generate_note"] is False
        assert result["messages"][0].content == "システムコール"
        assert result["messages"][1] is response

    async def test_preseeds_purpose_from_api_provided_learning_goal(self) -> None:
        response = AIMessage(content="出典はありますか？")
        mock_llm = MagicMock(ainvoke=AsyncMock(return_value=response))
        with patch("graph.nodes.learning_start.llm", mock_llm):
            from graph.nodes.learning_start import learning_start

            await learning_start(_state(learning_goal="面接対策"))

        prompt = mock_llm.ainvoke.call_args.args[0][0].content
        assert "面接対策" in prompt
        assert prompt.count("未回答") == 2
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_learning_start.py -v`
Expected: FAIL

- [ ] **Step 3: `learning_start.py` を書き換える**

`server/graph/nodes/learning_start.py` の全文を置き換える:

```python
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from graph.llm import llm
from graph.prompts.intake import build_intake_prompt
from graph.state import LearningState


async def learning_start(state: LearningState) -> dict[str, Any]:
    """学習フローの開始: topic のみで始め、聞き取り（目的・出典・前提知識）の最初の問いを返す。

    API から learning_goal（目的）が渡っていれば、聞き取りの対象からその項目を除外する。
    """
    topic = state["topic"]
    user_message = HumanMessage(content=topic)

    prompt = build_intake_prompt(
        topic=topic,
        purpose=state.get("learning_goal") or "",
        source="",
        prior_knowledge="",
        recent_messages="",
    )
    response = await llm.ainvoke([SystemMessage(content=prompt), user_message])

    return {
        "messages": [user_message, response],
        "turn_count": 1,
        "should_generate_note": False,
        "intake_complete": False,
        "intake_turns": 0,
    }


__all__ = ["learning_start"]
```

- [ ] **Step 4: `learning_planner.py` と、その専用テストを削除する**

```bash
cd server && git rm graph/prompts/learning_planner.py tests/unit/graph/test_learning_planner_prompt.py
```

- [ ] **Step 5: `graph/prompts/__init__.py` から `LEARNING_PLANNER_PROMPT` の import/export を取り除く**

`from graph.prompts.learning_planner import LEARNING_PLANNER_PROMPT` の行を削除し、`__all__` リストから `"LEARNING_PLANNER_PROMPT"` を削除する。

- [ ] **Step 6: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_learning_start.py tests/unit/graph -v && uv run mypy graph/nodes/learning_start.py graph/prompts/__init__.py`
Expected: PASS（`test_learning_planner_prompt.py` は削除済みなので収集されない）/ `Success: no issues found`

- [ ] **Step 7: Commit**

```bash
cd server && git add graph/nodes/learning_start.py graph/prompts/__init__.py tests/unit/graph/test_learning_start.py
git commit -m "feat(graph): start learning sessions with an intake question"
```

---

### Task 14: `learning_dialogue` をルーターにする

**Files:**
- Modify: `server/graph/nodes/learning_dialogue.py`
- Test: `server/tests/unit/graph/test_learning_dialogue.py`（追記のみ。既存テストは変更しない）

**Interfaces:**
- Consumes: `handle_intake_turn`（`_intake`）、`prepare_map_turn` / `respond_map`（`_map_dialogue`）
- 既存の `TurnPlan` / `prepare_turn` / `respond` は無変更のまま維持する（`evals/eval.py` の直接 import 対象）

- [ ] **Step 1: 失敗するテストを追記する**

`server/tests/unit/graph/test_learning_dialogue.py` の末尾に追記:

```python
class TestLearningDialogueRouting:
    async def test_missing_intake_complete_key_uses_the_legacy_path(self) -> None:
        """intake_complete キーが無い（デプロイ前に開始した）セッションは聞き取りに入らない。"""
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
            patch("graph.nodes.learning_dialogue.handle_intake_turn") as mock_intake,
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")]))

        mock_intake.assert_not_called()
        assert result["turn_count"] == 3

    async def test_intake_incomplete_delegates_to_handle_intake_turn(self) -> None:
        intake_result = {"messages": [AIMessage(content="次の質問です")], "intake_complete": False, "intake_turns": 1}
        with patch(
            "graph.nodes.learning_dialogue.handle_intake_turn", AsyncMock(return_value=intake_result)
        ) as mock_intake:
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")], intake_complete=False))

        mock_intake.assert_awaited_once()
        assert result is intake_result

    async def test_intake_turn_without_messages_falls_back_to_legacy_response(self) -> None:
        """地図生成が失敗したターン: ルーターが legacy 経路で応答を生成する。"""
        intake_result = {
            "intake_complete": True,
            "intake_turns": 3,
            "learning_goal": "面接対策",
            "learning_source": "",
            "prior_knowledge": "",
            "turn_count": 3,
            "should_generate_note": False,
        }
        with (
            patch("graph.nodes.learning_dialogue.handle_intake_turn", AsyncMock(return_value=intake_result)),
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="今知っていることを教えてください"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")], intake_complete=False))

        assert "messages" in result
        assert result["intake_complete"] is True

    async def test_intake_complete_with_depth_map_uses_map_dialogue(self) -> None:
        depth_map = {"topic": "t", "aspects": []}
        map_result = {"messages": [AIMessage(content="地図駆動の質問")], "turn_count": 4}
        with (
            patch("graph.nodes.learning_dialogue.prepare_map_turn", AsyncMock(return_value=MagicMock())) as mock_prepare,
            patch("graph.nodes.learning_dialogue.respond_map", AsyncMock(return_value=map_result)) as mock_respond,
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(
                _make_state([HumanMessage(content="hi")], intake_complete=True, depth_map=depth_map)
            )

        mock_prepare.assert_awaited_once()
        mock_respond.assert_awaited_once()
        assert result is map_result

    async def test_intake_complete_without_depth_map_uses_legacy_path(self) -> None:
        """地図なしフォールバックが継続しているセッション。"""
        with (
            patch(
                "graph.nodes.learning_dialogue.llm",
                MagicMock(ainvoke=AsyncMock(return_value=AIMessage(content="質問です"))),
            ),
            patch("graph.nodes.learning_dialogue.build_question_prompt", _FAKE_PROMPT),
            patch("graph.nodes.learning_dialogue.analyze_dialogue_turn", _NO_ANALYSIS),
        ):
            from graph.nodes.learning_dialogue import learning_dialogue

            result = await learning_dialogue(_make_state([HumanMessage(content="hi")], intake_complete=True))

        assert result["turn_count"] == 3
```

- [ ] **Step 2: テストを実行して新規分が失敗することを確認する**

Run: `cd server && uv run pytest tests/unit/graph/test_learning_dialogue.py -v`
Expected: FAIL（`TestLearningDialogueRouting` の5件。それ以外の既存テストは PASS のまま）

- [ ] **Step 3: `learning_dialogue.py` の末尾（`async def learning_dialogue` 定義）を書き換える**

import を追加（ファイル冒頭の import 群に追加）:

```python
from graph.nodes._intake import handle_intake_turn
from graph.nodes._map_dialogue import prepare_map_turn, respond_map
```

既存の `async def learning_dialogue(state: LearningState) -> dict[str, Any]:` を以下に置き換える:

```python
async def learning_dialogue(state: LearningState) -> dict[str, Any]:
    """対話継続のルーター。

    `intake_complete` が欠損なら旧セッション（このキーを一度も書かれたことがない）として legacy
    経路のみ実行する。値で判定すると、聞き取り中の新セッション（False）と区別できない。
    """
    intake_complete = state.get("intake_complete")
    if intake_complete is None:
        return await respond(state, await prepare_turn(state))
    if not intake_complete:
        intake_result = await handle_intake_turn(state)
        if "messages" in intake_result:
            return intake_result
        fallback_state: LearningState = {**state, **intake_result}
        legacy_result = await respond(fallback_state, await prepare_turn(fallback_state))
        return {**intake_result, **legacy_result}
    if not state.get("depth_map"):
        return await respond(state, await prepare_turn(state))
    return await respond_map(state, await prepare_map_turn(state))
```

- [ ] **Step 4: 全テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/graph/test_learning_dialogue.py -v && uv run mypy graph/nodes/learning_dialogue.py`
Expected: PASS（既存テスト・新規テストとも全件）/ `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
cd server && git add graph/nodes/learning_dialogue.py tests/unit/graph/test_learning_dialogue.py
git commit -m "feat(graph): route learning_dialogue across legacy/intake/map phases"
```

---

### Task 15: `_learning_progress` を地図の有無で分岐させる

**Files:**
- Modify: `server/api/websocket/chat.py`
- Create: `server/tests/unit/api/websocket/test_chat.py`（新規。`tests/unit/api/websocket/` ディレクトリも新規作成）

**Interfaces:**
- Consumes: `depth_map_progress`（`graph.depth_map`）

- [ ] **Step 1: 失敗するテストを書く**

`server/tests/unit/api/websocket/__init__.py`（空ファイル）を作成し、`server/tests/unit/api/websocket/test_chat.py`:

```python
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from api.websocket.chat import _learning_progress


class _FakeState:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values


class TestLearningProgress:
    async def test_uses_depth_map_progress_when_depth_map_present(self) -> None:
        depth_map = {
            "topic": "t",
            "aspects": [{"id": "a", "name": "観点A", "is_core": True, "defined_question": "d", "reasoned_question": "r", "applied_question": "ap"}],
        }
        graph = MagicMock(
            aget_state=AsyncMock(
                return_value=_FakeState(
                    {"depth_map": depth_map, "map_covered": [{"aspect_id": "a", "reached_stage": "reasoned"}]}
                )
            )
        )
        progress = await _learning_progress(graph, {})
        assert progress is not None
        assert progress.reached_aspects == ["観点A"]
        assert progress.is_complete is True

    async def test_falls_back_to_legacy_coverage_without_depth_map(self) -> None:
        graph = MagicMock(
            aget_state=AsyncMock(
                return_value=_FakeState({"covered_aspects": [{"aspect": "前提条件", "reached_depth": "exemplified"}]})
            )
        )
        progress = await _learning_progress(graph, {})
        assert progress is not None
        assert progress.reached_aspects == ["前提条件"]

    async def test_returns_none_on_failure(self) -> None:
        graph = MagicMock(aget_state=AsyncMock(side_effect=RuntimeError("down")))
        assert await _learning_progress(graph, {}) is None
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd server && uv run pytest tests/unit/api/websocket/test_chat.py -v`
Expected: FAIL（分岐前の実装ではまだ通る可能性があるが、確認のため実行しておく）

- [ ] **Step 3: `_learning_progress` を書き換える**

`server/api/websocket/chat.py` の import に `from graph.depth_map import depth_map_progress` を追加し、`_learning_progress` を以下に置き換える:

```python
async def _learning_progress(graph: Any, config: dict[str, Any]) -> LearningProgress | None:
    """進捗は表示専用の副次情報。取得に失敗してもターンの成否に影響させず `None` を返す。"""
    try:
        values = (await graph.aget_state(config)).values
    except Exception:
        logger.exception("Failed to read learning progress")
        return None
    depth_map = values.get("depth_map")
    if depth_map:
        progress = depth_map_progress(values.get("map_covered") or [], depth_map)
    else:
        progress = coverage_progress(values.get("covered_aspects") or [], values.get("focus_aspects"))
    return LearningProgress(
        reached_aspects=list(progress.reached_aspects),
        target_count=progress.target_count,
        is_complete=progress.is_complete,
    )
```

- [ ] **Step 4: テストと型チェックを実行する**

Run: `cd server && uv run pytest tests/unit/api/websocket/test_chat.py -v && uv run mypy api/websocket/chat.py`
Expected: PASS / `Success: no issues found`

- [ ] **Step 5: Commit**

```bash
cd server && git add api/websocket/chat.py tests/unit/api/websocket/__init__.py tests/unit/api/websocket/test_chat.py
git commit -m "feat(api): branch learning progress on depth map presence"
```

---

### Task 16: クライアント — 学習ゴール入力欄を削除する

**Files:**
- Modify: `client/app/(main)/learn/page.tsx`

聞き取りはチャットで行うため、開始フォームは topic 入力のみにする。

- [ ] **Step 1: `learningGoal` state と関連 UI を削除する**

`client/app/(main)/learn/page.tsx` から以下を削除する:
- `const [learningGoal, setLearningGoal] = useState("");`
- `const [isDetailsOpen, setIsDetailsOpen] = useState(false);`
- リセット用 `useEffect` 内の `setLearningGoal("");` と `setIsDetailsOpen(false);`
- `handleStartLearning` 内の `learning_goal: learningGoal.trim() || undefined,`（`startLearning(topic.trim())` に単純化）
- フォーム内の学習ゴール入力ブロック（`isDetailsOpen` を使った `<div>` 全体: `FlagIcon`/`XIcon`/`PlusIcon`/`Textarea`/「学習ゴールを追加」ボタンを含む）

`import` 文から未使用になった `FlagIcon`, `PlusIcon`, `XIcon`, `Textarea` を削除する（`ArrowRightIcon`, `HistoryIcon`, `Loader2Icon`, `PencilIcon` は他の箇所で使用中のため残す。実際に未使用か `npm run lint` で確認する）。

- [ ] **Step 2: 型チェックと lint を実行する**

Run: `cd client && npx tsc --noEmit && npm run lint`
Expected: エラー無し（未使用 import が残っていれば ESLint が指摘するので、指摘された import を削除する）

- [ ] **Step 3: 既存のフロントエンドテストを実行する**

Run: `cd client && npm run test`
Expected: PASS（`learn/page.tsx` を対象にした既存テストは無いため、無関係のテストが通ることを確認する）

- [ ] **Step 4: Commit**

```bash
cd client && git add "app/(main)/learn/page.tsx"
git commit -m "feat(client): collect learning goal via chat intake instead of the start form"
```

---

### Task 17: 最終検証

**Files:** なし（検証のみ）

- [ ] **Step 1: サーバー側の lint・型チェック・全テストを実行する**

Run: `cd server && uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: 全件 PASS。`ruff format` が差分を出した場合は `git add -u` してから次のコミットに含める

- [ ] **Step 2: legacy 経路（`evals/eval.py` が依存する関数）に diff が無いことを確認する**

Run: `cd server && git diff main -- graph/nodes/learning_dialogue.py | grep -E '^\-.*def (prepare_turn|respond|learning_dialogue)\(' || echo "OK: signatures unchanged"`
Expected: `OK: signatures unchanged`（`TurnPlan`/`prepare_turn`/`respond` の定義行に削除diffが無いこと）

- [ ] **Step 3: クライアント側の lint・型チェック・全テストを実行する**

Run: `cd client && npm run lint && npx tsc --noEmit && npm run test`
Expected: 全件 PASS

- [ ] **Step 4: pre-commit フックを最終確認として流す**

Run: `cd server && uv run pre-commit run --all-files`
Expected: 全件 PASS（差分が出た場合は差分を確認して commit に含める）

- [ ] **Step 5: Commit（最終調整があれば）**

```bash
git add -A
git commit -m "chore: final lint/format pass for intake + depth map feature"
```
