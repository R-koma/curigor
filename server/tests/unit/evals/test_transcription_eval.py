from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evals import transcription
from evals.checkpoint import CheckpointStore
from evals.tools.record_audio.app import create_app
from evals.transcription import VARIANTS, Item, Request, build_request, load_items, normalize, score

_BY_NAME = {v.name: v for v in VARIANTS}


def _item(**overrides: object) -> Item:
    values: dict[str, object] = {
        "id": "linux-homophone",
        "category": "homophone",
        "topic_id": "linux",
        "topic": "Linuxの仕組み",
        "aspects": ("プロセス", "システムコール"),
        "keywords": ("カーネル", "fork", "習得"),
        "previous_assistant": "何が身につく？",
        "text": "えっと、低レイヤーの技術を習得できます。",
        "terms": (("習得",), ("低レイヤー", "低レイヤ")),
        "previous_item_id": None,
    }
    values.update(overrides)
    return Item(**values)  # type: ignore[arg-type]


def _wav(seconds: float) -> bytes:
    return b"\0" * (44 + int(seconds * 32_000))


def test_dataset_has_thirty_items_with_terms_found_in_their_own_text() -> None:
    items = load_items()
    assert len(items) == 30
    assert len({i.id for i in items}) == 30
    for item in items:
        assert score(item, item.text)["missed_terms"] == [], item.id
        assert score(item, item.text)["errors"] == 0


def test_dataset_links_each_item_to_the_previous_one_in_its_topic() -> None:
    items = load_items()
    firsts = [i for i in items if i.previous_item_id is None]
    assert len(firsts) == 5
    by_id = {i.id: i for i in items}
    for item in items:
        if item.previous_item_id:
            assert by_id[item.previous_item_id].topic_id == item.topic_id


def test_normalize_ignores_punctuation_width_fillers_and_the_end_word() -> None:
    assert normalize("えっと、ＴＣＰは　速い。以上。") == normalize("TCPは速い")
    assert normalize("SYN-ACK") == normalize("SYN ACK")
    assert normalize("ルーター") != normalize("ルータ")


def test_score_counts_errors_missed_terms_and_inserted_keywords() -> None:
    result = score(_item(), "低レイヤーの技術を取得できます。fork")
    assert result["errors"] == 5
    assert result["missed_terms"] == ["習得"]
    assert result["terms_hit"] == 1
    assert result["inserted_keywords"] == ["fork"]


def test_score_accepts_any_listed_form_of_a_term() -> None:
    assert score(_item(), "低レイヤの技術を習得できます")["missed_terms"] == []


def test_voice_prompt_matches_the_client_and_respects_the_limit() -> None:
    request = build_request(_BY_NAME["current_voice"], _item(), limit=200)
    assert request == Request(
        model="gpt-transcribe",
        audio_format="wav",
        prompt="話し終えたら「以上」と言って締めくくります。トピック: Linuxの仕組み",
    )
    assert build_request(_BY_NAME["current_voice"], _item(), limit=10).prompt == "話し終えたら「以上」"


def test_mic_variant_sends_webm_without_a_prompt() -> None:
    request = build_request(_BY_NAME["current_mic"], _item(), limit=200)
    assert request.prompt is None
    assert request.audio_format == "webm"


def test_mic_keyword_variant_sends_the_topic_and_generated_keywords() -> None:
    request = build_request(_BY_NAME["mic_keywords_generated"], _item(), 200, generated_keywords=("習得",))
    assert request == Request(
        model="gpt-transcribe", audio_format="webm", prompt="トピック: Linuxの仕組み", keywords=("習得",)
    )


def test_context_and_keyword_variants_add_hints() -> None:
    context = build_request(_BY_NAME["keywords_context"], _item(), limit=200)
    assert context.prompt is not None
    assert "観点: プロセス、システムコール" in context.prompt
    assert "直前の質問: 何が身につく？" in context.prompt
    assert context.keywords == ("カーネル", "fork", "習得")
    assert build_request(_BY_NAME["current_voice"], _item(), limit=200).keywords == ()


def test_previous_variant_appends_the_previous_transcript() -> None:
    request = build_request(_BY_NAME["prev_segment"], _item(), limit=200, previous_text="前の発言")
    assert request.prompt is not None
    assert request.prompt.endswith("直前の発言: 前の発言")
    no_previous = build_request(_BY_NAME["prev_segment"], _item(), limit=200)
    assert no_previous.prompt == build_request(_BY_NAME["current_voice"], _item(), limit=200).prompt


def test_correction_prompt_carries_the_hints_and_transcript() -> None:
    prompt = transcription.correction_prompt(_item(), "技術を取得できます")
    assert "トピック: Linuxの仕組み" in prompt
    assert "用語: カーネル、fork、習得" in prompt
    assert prompt.endswith("技術を取得できます")


class _FakeApi:
    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list[Request] = []
        self.corrections = 0

    async def transcribe(self, audio: bytes, request: Request) -> str:
        self.requests.append(request)
        return self.text

    async def correct(self, prompt: str) -> tuple[str, dict[str, int]]:
        self.corrections += 1
        return "低レイヤーの技術を習得できます", {"input_tokens": 100, "output_tokens": 10}


def _runner(tmp_path: Path, api: _FakeApi, items: list[Item]) -> transcription.Runner:
    return transcription.Runner(
        items=items,
        audio_dir=tmp_path,
        checkpoint=CheckpointStore(tmp_path / "checkpoint"),
        transcribe=api.transcribe,
        correct=api.correct,
    )


async def test_runner_scores_variants_and_estimates_cost(tmp_path: Path) -> None:
    (tmp_path / "linux-homophone.wav").write_bytes(_wav(6))
    api = _FakeApi("低レイヤーの技術を取得できます")
    runner = _runner(tmp_path, api, [_item()])

    results = await runner.run([_BY_NAME["current_voice"], _BY_NAME["llm_correct"]], runs=1)

    by_variant = {r.variant: r for r in results}
    assert by_variant["current_voice"].missed_terms == ["習得"]
    assert by_variant["current_voice"].cost_usd == pytest.approx(0.0045 * 6 / 60)
    assert by_variant["llm_correct"].missed_terms == []
    assert by_variant["llm_correct"].correction_input_tokens == 100
    assert runner.errors == []


async def test_runner_reuses_saved_calls_when_the_request_is_unchanged(tmp_path: Path) -> None:
    (tmp_path / "linux-homophone.wav").write_bytes(_wav(1))
    api = _FakeApi("低レイヤーの技術を取得できます")
    variants = [_BY_NAME["current_voice"], _BY_NAME["llm_correct"]]

    await _runner(tmp_path, api, [_item()]).run(variants, runs=1)
    await _runner(tmp_path, api, [_item()]).run(variants, runs=1)

    assert len(api.requests) == 1
    assert api.corrections == 1


async def test_runner_feeds_the_previous_items_baseline_transcript(tmp_path: Path) -> None:
    first = _item(id="a")
    second = _item(id="b", previous_item_id="a")
    for item in (first, second):
        (tmp_path / f"{item.id}.wav").write_bytes(_wav(1))
    api = _FakeApi("前の文の文字起こし")

    await _runner(tmp_path, api, [first, second]).run([_BY_NAME["prev_segment"]], runs=1)

    prompts = [r.prompt for r in api.requests if r.prompt and "直前の発言" in r.prompt]
    assert prompts == [f"{transcription.voice_prompt(second, 200)}\n直前の発言: 前の文の文字起こし"]


async def test_runner_reports_missing_audio(tmp_path: Path) -> None:
    runner = _runner(tmp_path, _FakeApi("x"), [_item()])
    results = await runner.run([_BY_NAME["current_mic"]], runs=1)
    assert results == []
    assert runner.errors == ["current_mic linux-homophone: linux-homophone.webm が無い"]


async def test_run_writes_a_report(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for item in load_items():
        (audio_dir / f"{item.id}.wav").write_bytes(_wav(2))
    api = _FakeApi("技術")
    out = tmp_path / "report.json"
    args = argparse.Namespace(
        audio_dir=audio_dir,
        dataset=transcription.DEFAULT_DATASET,
        variant=["current_voice"],
        item=None,
        runs=1,
        prompt_limit=200,
        correction_model="m",
        concurrency=4,
        checkpoint_dir=tmp_path / "checkpoint",
        out=out,
    )

    assert await transcription.run(args, transcribe=api.transcribe, correct=api.correct) == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    summary = report["variants"]["current_voice"]
    assert summary["n"] == 30
    assert 0 < summary["cer"] <= 1
    assert set(report["by_category"]) == {"technical", "homophone", "proper", "english", "numbers", "disfluency"}


def test_record_app_saves_and_serves_audio_for_known_items_only(tmp_path: Path) -> None:
    client = TestClient(create_app(transcription.DEFAULT_DATASET, tmp_path))

    items = client.get("/api/items").json()
    assert len(items) == 30
    assert not any(i["recorded"] for i in items)

    assert client.put("/api/items/linux-technical/audio/wav", content=_wav(1)).status_code == 204
    assert client.put("/api/items/linux-technical/audio/webm", content=b"webm").status_code == 204
    assert (tmp_path / "linux-technical.wav").exists()
    assert client.get("/api/items").json()[0]["recorded"] is True
    assert client.get("/api/items/linux-technical/audio/webm").content == b"webm"

    assert client.put("/api/items/..%2Fx/audio/wav", content=b"x").status_code == 404
    assert client.put("/api/items/unknown/audio/wav", content=b"x").status_code == 404
    assert client.put("/api/items/linux-technical/audio/mp3", content=b"x").status_code == 422
    assert client.put("/api/items/linux-technical/audio/wav", content=b"").status_code == 413


async def test_generated_keywords_are_made_once_per_topic_and_reused(tmp_path: Path) -> None:
    first = _item(id="a")
    second = _item(id="b", previous_item_id="a")
    for item in (first, second):
        (tmp_path / f"{item.id}.wav").write_bytes(_wav(1))
    api = _FakeApi("技術を習得できます")
    generated: list[str] = []

    async def generate(item: Item) -> list[str]:
        generated.append(item.id)
        return [item.topic, "習得"]

    generator = transcription.KeywordGenerator(fingerprint="v1", generate=generate)
    runner = _runner(tmp_path, api, [first, second])
    runner.keyword_generator = generator

    results = await runner.run([_BY_NAME["keywords_generated"]], runs=2)

    assert generated == ["a"]
    assert {r.keywords == ["Linuxの仕組み", "習得"] for r in results} == {True}
    assert {r.keywords for r in api.requests} == {("Linuxの仕組み", "習得")}
