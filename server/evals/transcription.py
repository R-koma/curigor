"""文字起こしの精度を、読み上げて録音した音声セットで案ごとに比べる（#493）。

音声は保存しない方針（ADR-007）なので、録音はリポジトリの外（`--audio-dir`）に置き、
`evals.tools.record_audio` で `<id>.wav`（声で話すと同じ 16kHz の WAV）と `<id>.webm`
（入力欄のマイクと同じ形式）を作る。文字起こしの API に直接送るので VAD を通らない。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import statistics
import time
import unicodedata
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from evals.checkpoint import CheckpointStore, sha256_bytes, write_json
from evals.retry import QuotaExhausted, is_quota_exhausted, is_transient

logger = logging.getLogger(__name__)

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "transcription.json"
_REPORTS_DIR = Path(__file__).parent / "reports"
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0

# client の `transcriptionPrompt`（`hooks/use-voice-conversation.ts`）と一致させる。
# "topic" の prompt は `topicTranscriptionPrompt`（`lib/audio.ts`）と一致させる
VOICE_PROMPT_BASE = "話し終えたら「以上」と言って締めくくります。"
DEFAULT_PROMPT_LIMIT = 200
DEFAULT_TRANSCRIPTION_MODEL = "gpt-transcribe"
DEFAULT_CORRECTION_MODEL = "gpt-6-luna"
LANGUAGE = "ja"

# 2026-10 時点の公開価格（ドル / 分）。gpt-transcribe は ADR-007 の値
PRICE_PER_MINUTE = {"gpt-transcribe": 0.0045, "gpt-4o-transcribe": 0.006, "gpt-4o-mini-transcribe": 0.003}

_PUNCTUATION = re.compile(r"[\s。、．，.,!！?？「」『』・\-‐―()（）/:：]")
_FILLER = re.compile(r"(えっと|えーと|えー|あの|うーん|まあ|なんか|その|なんだろう)[、,，\s]")
_END_WORD = re.compile(r"[\s。、．，.,!！?？]*以上[\s。、．，.,!！?？]*$")
_WAV_HEADER_BYTES = 44
_WAV_BYTES_PER_SECOND = 16_000 * 2


@dataclass(frozen=True)
class Item:
    id: str
    category: str
    topic_id: str
    topic: str
    aspects: tuple[str, ...]
    keywords: tuple[str, ...]
    previous_assistant: str
    text: str
    terms: tuple[tuple[str, ...], ...]
    previous_item_id: str | None


@dataclass(frozen=True)
class Request:
    model: str
    audio_format: str
    prompt: str | None = None
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    model: str = DEFAULT_TRANSCRIPTION_MODEL
    audio_format: str = "wav"
    prompt: str = "voice"
    keywords: bool = False
    generated_keywords: bool = False
    correct: bool = False


VARIANTS: tuple[Variant, ...] = (
    Variant("current_voice", "今の声で話す（定型文 + トピック）"),
    Variant("current_mic", "今の入力欄のマイク（prompt なし・webm）", audio_format="webm", prompt="none"),
    Variant("prompt_context", "prompt に観点名と直前の質問を足す", prompt="context"),
    Variant("prev_segment", "prompt に直前の発言（前の文の current_voice の結果）を足す", prompt="previous"),
    Variant("keywords", "keywords にトピックの用語を渡す", keywords=True),
    Variant("keywords_context", "keywords + prompt_context", prompt="context", keywords=True),
    Variant("keywords_generated", "keywords に本番の生成（LLM）で作った用語を渡す", generated_keywords=True),
    Variant(
        "mic_keywords_generated",
        "入力欄のマイクに prompt（トピック）と生成した keywords を渡す",
        audio_format="webm",
        prompt="topic",
        generated_keywords=True,
    ),
    Variant("llm_correct", "current_voice の結果を LLM で補正する", correct=True),
    Variant("gpt-4o-transcribe", "モデルを gpt-4o-transcribe に替える", model="gpt-4o-transcribe"),
    Variant("gpt-4o-mini-transcribe", "モデルを gpt-4o-mini-transcribe に替える", model="gpt-4o-mini-transcribe"),
)
_VARIANTS_BY_NAME = {v.name: v for v in VARIANTS}


@dataclass
class Result:
    variant: str
    item_id: str
    category: str
    run: int
    text: str
    latency_ms: float
    audio_seconds: float
    cost_usd: float
    cer: float
    errors: int
    reference_chars: int
    terms_hit: int
    terms_total: int
    missed_terms: list[str] = field(default_factory=list)
    inserted_keywords: list[str] = field(default_factory=list)
    correction_input_tokens: int = 0
    correction_output_tokens: int = 0
    keywords: list[str] = field(default_factory=list)


def load_items(path: Path = DEFAULT_DATASET) -> list[Item]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[Item] = []
    for topic in data["topics"]:
        previous: str | None = None
        for raw in topic["items"]:
            items.append(
                Item(
                    id=raw["id"],
                    category=raw["category"],
                    topic_id=topic["id"],
                    topic=topic["topic"],
                    aspects=tuple(topic["aspects"]),
                    keywords=tuple(topic["keywords"]),
                    previous_assistant=raw["previous_assistant"],
                    text=raw["text"],
                    terms=tuple(tuple(forms) for forms in raw["terms"]),
                    previous_item_id=previous,
                )
            )
            previous = raw["id"]
    return items


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = _END_WORD.sub("", text)
    text = _FILLER.sub("", text)
    return _PUNCTUATION.sub("", text)


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def score(item: Item, hypothesis: str) -> dict[str, Any]:
    reference = normalize(item.text)
    hyp = normalize(hypothesis)
    errors = edit_distance(reference, hyp)
    missed = [forms[0] for forms in item.terms if not any(normalize(form) in hyp for form in forms)]
    inserted = [k for k in item.keywords if normalize(k) not in reference and normalize(k) in hyp]
    return {
        "cer": errors / len(reference),
        "errors": errors,
        "reference_chars": len(reference),
        "terms_hit": len(item.terms) - len(missed),
        "terms_total": len(item.terms),
        "missed_terms": missed,
        "inserted_keywords": inserted,
    }


def voice_prompt(item: Item, limit: int) -> str:
    return f"{VOICE_PROMPT_BASE}トピック: {item.topic}"[:limit]


def context_prompt(item: Item, limit: int) -> str:
    parts = [f"{VOICE_PROMPT_BASE}トピック: {item.topic}", f"観点: {'、'.join(item.aspects)}"]
    parts.append(f"直前の質問: {item.previous_assistant}")
    return "\n".join(parts)[:limit]


def previous_prompt(item: Item, previous_text: str | None, limit: int) -> str:
    base = voice_prompt(item, limit)
    if not previous_text:
        return base
    return f"{base}\n直前の発言: {previous_text}"[:limit]


def build_request(
    variant: Variant,
    item: Item,
    limit: int,
    previous_text: str | None = None,
    generated_keywords: tuple[str, ...] = (),
) -> Request:
    if variant.prompt == "none":
        prompt = None
    elif variant.prompt == "context":
        prompt = context_prompt(item, limit)
    elif variant.prompt == "previous":
        prompt = previous_prompt(item, previous_text, limit)
    elif variant.prompt == "topic":
        prompt = f"トピック: {item.topic}"[:limit]
    else:
        prompt = voice_prompt(item, limit)
    keywords = item.keywords if variant.keywords else generated_keywords if variant.generated_keywords else ()
    return Request(model=variant.model, audio_format=variant.audio_format, prompt=prompt, keywords=keywords)


CORRECTION_PROMPT = """あなたは音声認識の結果を校正する係です。
学習者が、学んでいる内容を声で説明した発言の文字起こしを渡します。

## 直すもの
- 同音異義語の漢字の誤り（例: 取得 → 習得）
- 専門用語・固有名詞・英字の略語の誤った表記

## 守ること
- 言い回し・語順・言いよどみ・文の区切りは変えない
- 学習者の説明が内容として間違っていても直さない（誤変換だけを直す）
- 確信が持てない箇所はそのまま残す
- 直す箇所が無ければ、渡された文字起こしをそのまま返す
- 出力は直した本文だけにし、説明や引用符を付けない

## 手がかり
トピック: {topic}
観点: {aspects}
用語: {keywords}
直前の質問: {previous_assistant}

## 文字起こし
{transcript}"""


def correction_prompt(item: Item, transcript: str) -> str:
    return CORRECTION_PROMPT.format(
        topic=item.topic,
        aspects="、".join(item.aspects),
        keywords="、".join(item.keywords),
        previous_assistant=item.previous_assistant,
        transcript=transcript,
    )


@dataclass(frozen=True)
class KeywordGenerator:
    fingerprint: str
    generate: Callable[[Item], Awaitable[list[str]]]


Transcribe = Callable[[bytes, Request], Awaitable[str]]
Correct = Callable[[str], Awaitable[tuple[str, dict[str, int]]]]

_MIME_TYPES = {"wav": "audio/wav", "webm": "audio/webm"}


def openai_transcribe() -> Transcribe:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(timeout=120, max_retries=0)

    async def transcribe(audio: bytes, request: Request) -> str:
        options: dict[str, Any] = {}
        if request.prompt:
            options["prompt"] = request.prompt
        extra: dict[str, Any] = {}
        if request.model == "gpt-transcribe":
            extra["languages"] = [LANGUAGE]
            if request.keywords:
                extra["keywords"] = list(request.keywords)
        else:
            options["language"] = LANGUAGE
        result = await client.audio.transcriptions.create(
            model=request.model,
            file=(f"audio.{request.audio_format}", audio, _MIME_TYPES[request.audio_format]),
            response_format="json",
            extra_body=extra or None,
            **options,
        )
        return str(result.text).strip()

    return transcribe


def production_keywords() -> KeywordGenerator:
    from services.transcription_keywords import KeywordSource, generate_terms, merge_keywords

    def source(item: Item) -> KeywordSource:
        return KeywordSource(item.topic, item.aspects, "")

    async def generate(item: Item) -> list[str]:
        return merge_keywords(source(item), await generate_terms(source(item)))

    probe = KeywordSource("", (), "")
    return KeywordGenerator(fingerprint=probe.fingerprint, generate=generate)


def llm_correct(model: str) -> Correct:
    from langchain_core.messages import AIMessage

    from graph.llm import ModelSpec, build_chat_model

    chat = build_chat_model(ModelSpec(provider="openai", model=model, reasoning_effort="none", temperature=0))

    async def correct(prompt: str) -> tuple[str, dict[str, int]]:
        response = await chat.ainvoke(prompt)
        assert isinstance(response, AIMessage)
        usage = response.usage_metadata
        tokens = {
            "input_tokens": usage["input_tokens"] if usage else 0,
            "output_tokens": usage["output_tokens"] if usage else 0,
        }
        return str(response.content).strip(), tokens

    return correct


async def with_retry[T](call: Callable[[], Awaitable[T]]) -> T:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return await call()
        except Exception as exc:
            if is_quota_exhausted(exc):
                raise QuotaExhausted(str(exc)) from exc
            if not is_transient(exc) or attempt == _MAX_ATTEMPTS:
                raise
            logger.warning("attempt %d/%d raised: %s", attempt, _MAX_ATTEMPTS, exc)
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")


def audio_seconds(audio_dir: Path, item_id: str) -> float:
    wav = audio_dir / f"{item_id}.wav"
    if not wav.exists():
        return 0.0
    return max(wav.stat().st_size - _WAV_HEADER_BYTES, 0) / _WAV_BYTES_PER_SECOND


def transcription_cost(model: str, seconds: float) -> float:
    return PRICE_PER_MINUTE.get(model, 0.0) * seconds / 60


@dataclass
class Runner:
    items: list[Item]
    audio_dir: Path
    checkpoint: CheckpointStore
    transcribe: Transcribe
    correct: Correct | None
    keyword_generator: KeywordGenerator | None = None
    prompt_limit: int = DEFAULT_PROMPT_LIMIT
    correction_model: str = DEFAULT_CORRECTION_MODEL
    concurrency: int = 4
    errors: list[str] = field(default_factory=list)

    def _audio(self, item: Item, audio_format: str) -> bytes | None:
        path = self.audio_dir / f"{item.id}.{audio_format}"
        return path.read_bytes() if path.exists() else None

    async def _cached(
        self, key: str, item: Item, run: int, request_hash: str, call: Callable[[], Awaitable[Any]]
    ) -> Any:
        saved = self.checkpoint.load_generation(key, item.id, run)
        if saved is not None and saved.get("request_hash") == request_hash:
            return saved["output"]
        output = await with_retry(call)
        self.checkpoint.save_generation(key, item.id, run, {"request_hash": request_hash, "output": output})
        return output

    async def _transcribe(self, item: Item, run: int, request: Request, audio: bytes) -> dict[str, Any]:
        request_hash = sha256_bytes(audio) + sha256_bytes(json.dumps(asdict(request), ensure_ascii=False).encode())

        async def call() -> dict[str, Any]:
            started = time.perf_counter()
            text = await self.transcribe(audio, request)
            return {"text": text, "latency_ms": (time.perf_counter() - started) * 1000}

        key = f"transcribe-{request.model}-{request.audio_format}"
        output: dict[str, Any] = await self._cached(key, item, run, request_hash, call)
        return output

    async def _correct(self, item: Item, run: int, transcript: str) -> dict[str, Any]:
        assert self.correct is not None
        correct = self.correct
        prompt = correction_prompt(item, transcript)
        request_hash = sha256_bytes(f"{self.correction_model}\n{prompt}".encode())

        async def call() -> dict[str, Any]:
            started = time.perf_counter()
            text, tokens = await correct(prompt)
            return {"text": text, "latency_ms": (time.perf_counter() - started) * 1000, **tokens}

        output: dict[str, Any] = await self._cached("correct", item, run, request_hash, call)
        return output

    async def _generated_keywords(self) -> dict[str, tuple[str, ...]]:
        assert self.keyword_generator is not None
        generator = self.keyword_generator
        by_topic: dict[str, tuple[str, ...]] = {}
        for item in self.items:
            if item.topic_id in by_topic:
                continue
            request_hash = sha256_bytes(f"{generator.fingerprint}\n{item.topic}\n{'、'.join(item.aspects)}".encode())
            saved = self.checkpoint.load_generation("keywords", item.topic_id, 0)
            if saved is not None and saved.get("request_hash") == request_hash:
                keywords = saved["output"]
            else:
                keywords = await with_retry(partial(generator.generate, item))
                self.checkpoint.save_generation(
                    "keywords", item.topic_id, 0, {"request_hash": request_hash, "output": keywords}
                )
            by_topic[item.topic_id] = tuple(keywords)
        return by_topic

    async def run_variant(
        self, variant: Variant, run: int, previous_texts: dict[str, str] | None = None
    ) -> dict[str, Result]:
        semaphore = asyncio.Semaphore(self.concurrency)
        results: dict[str, Result] = {}
        generated = await self._generated_keywords() if variant.generated_keywords else {}

        async def one(item: Item) -> None:
            audio = self._audio(item, variant.audio_format)
            if audio is None:
                self.errors.append(f"{variant.name} {item.id}: {item.id}.{variant.audio_format} が無い")
                return
            previous = (previous_texts or {}).get(item.previous_item_id or "")
            request = build_request(variant, item, self.prompt_limit, previous, generated.get(item.topic_id, ()))
            async with semaphore:
                try:
                    output = await self._transcribe(item, run, request, audio)
                    text, latency = output["text"], output["latency_ms"]
                    seconds = audio_seconds(self.audio_dir, item.id)
                    cost = transcription_cost(variant.model, seconds)
                    tokens: dict[str, Any] = {"correction_input_tokens": 0, "correction_output_tokens": 0}
                    if variant.correct:
                        corrected = await self._correct(item, run, text)
                        text, latency = corrected["text"], latency + corrected["latency_ms"]
                        tokens = {
                            "correction_input_tokens": corrected["input_tokens"],
                            "correction_output_tokens": corrected["output_tokens"],
                        }
                except QuotaExhausted:
                    raise
                except Exception as exc:
                    logger.exception("%s %s run%d failed", variant.name, item.id, run)
                    self.errors.append(f"{variant.name} {item.id} run{run}: {type(exc).__name__}: {exc}")
                    return
            results[item.id] = Result(
                variant=variant.name,
                item_id=item.id,
                category=item.category,
                run=run,
                text=text,
                latency_ms=latency,
                audio_seconds=seconds,
                cost_usd=cost,
                keywords=list(request.keywords),
                **tokens,
                **score(item, text),
            )

        await asyncio.gather(*(one(item) for item in self.items))
        return results

    async def run(self, variants: list[Variant], runs: int) -> list[Result]:
        ordered = sorted(variants, key=lambda v: v.prompt == "previous")
        all_results: list[Result] = []
        for run in range(runs):
            baseline: dict[str, str] | None = None
            for variant in ordered:
                previous_texts = None
                if variant.prompt == "previous":
                    if baseline is None:
                        baseline_results = await self.run_variant(_VARIANTS_BY_NAME["current_voice"], run)
                        baseline = {item_id: r.text for item_id, r in baseline_results.items()}
                    previous_texts = baseline
                results = await self.run_variant(variant, run, previous_texts)
                if variant.name == "current_voice":
                    baseline = {item_id: r.text for item_id, r in results.items()}
                print(f"run{run} {variant.name}: {len(results)}/{len(self.items)}")
                all_results.extend(results.values())
        return all_results


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(q) - 1]


def summarize(results: Iterable[Result]) -> dict[str, Any]:
    # evals.metrics は graph.llm を読み込み、API キーが無いと import で失敗する（録音の画面はキー無しで動かす）
    from evals.metrics import wilson_interval

    rows = list(results)
    if not rows:
        return {"n": 0}
    errors = sum(r.errors for r in rows)
    chars = sum(r.reference_chars for r in rows)
    hit = sum(r.terms_hit for r in rows)
    total = sum(r.terms_total for r in rows)
    seconds = sum(r.audio_seconds for r in rows)
    cost = sum(r.cost_usd for r in rows)
    latencies = [r.latency_ms for r in rows]
    interval = wilson_interval(hit, total)
    return {
        "n": len(rows),
        "cer": errors / chars if chars else None,
        "exact_sentences": sum(1 for r in rows if r.errors == 0) / len(rows),
        "term_accuracy": hit / total if total else None,
        "term_accuracy_ci95": list(interval) if interval else None,
        "inserted_keywords": sum(len(r.inserted_keywords) for r in rows),
        "latency_ms_p50": _percentile(latencies, 50),
        "latency_ms_p95": _percentile(latencies, 95),
        "transcription_usd_per_audio_minute": cost / seconds * 60 if seconds else None,
        "correction_input_tokens": sum(r.correction_input_tokens for r in rows),
        "correction_output_tokens": sum(r.correction_output_tokens for r in rows),
    }


def build_report(
    results: list[Result], variants: list[Variant], meta: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    by_variant = {v.name: [r for r in results if r.variant == v.name] for v in variants}
    categories = sorted({r.category for r in results})
    return {
        "meta": meta,
        "variants": {v.name: {"description": v.description, **summarize(by_variant[v.name])} for v in variants},
        "by_category": {
            category: {name: summarize(r for r in rows if r.category == category) for name, rows in by_variant.items()}
            for category in categories
        },
        "results": [asdict(r) for r in results],
        "errors": errors,
    }


def _fmt(value: float | None, pattern: str) -> str:
    return "-" if value is None else format(value, pattern)


def print_summary(report: dict[str, Any]) -> None:
    print("\n| 案 | CER | 全文一致 | 用語 | 余計な用語 | 遅延 p50 / p95 (ms) | $/分 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for name, s in report["variants"].items():
        if not s["n"]:
            print(f"| {name} | - | - | - | - | - | - |")
            continue
        print(
            f"| {name} | {_fmt(s['cer'], '.1%')} | {_fmt(s['exact_sentences'], '.0%')} "
            f"| {_fmt(s['term_accuracy'], '.0%')} | {s['inserted_keywords']} "
            f"| {_fmt(s['latency_ms_p50'], '.0f')} / {_fmt(s['latency_ms_p95'], '.0f')} "
            f"| {_fmt(s['transcription_usd_per_audio_minute'], '.4f')} |"
        )
    names = list(report["variants"])
    print("\nCER（種類ごと）")
    print("| 種類 | " + " | ".join(names) + " |")
    print("| --- |" + " --- |" * len(names))
    for category, by_name in report["by_category"].items():
        cells = " | ".join(_fmt(by_name[n].get("cer"), ".1%") for n in names)
        print(f"| {category} | {cells} |")
    for name, s in report["variants"].items():
        if s.get("correction_input_tokens"):
            print(
                f"\n{name} の補正のトークン: 入力 {s['correction_input_tokens']}"
                f" / 出力 {s['correction_output_tokens']}"
                f"（{s['n']} 文の合計。費用は {report['meta']['correction_model']} の単価で換算する）"
            )
    for error in report["errors"]:
        print(f"error: {error}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals.transcription", description="文字起こしの精度を案ごとに比べる")
    parser.add_argument("--audio-dir", type=Path, required=True, help="<id>.wav / <id>.webm を置いたディレクトリ")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--variant", action="append", choices=list(_VARIANTS_BY_NAME), help="比べる案（既定は全部）")
    parser.add_argument("--item", action="append", default=None, help="対象の文の id（複数指定可）")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--prompt-limit", type=int, default=DEFAULT_PROMPT_LIMIT)
    parser.add_argument("--correction-model", default=DEFAULT_CORRECTION_MODEL)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="レポートの保存先")
    return parser.parse_args(argv)


async def run(
    args: argparse.Namespace,
    transcribe: Transcribe | None = None,
    correct: Correct | None = None,
    keyword_generator: KeywordGenerator | None = None,
) -> int:
    items = load_items(args.dataset)
    if args.item:
        unknown = set(args.item) - {i.id for i in items}
        if unknown:
            print(f"error: unknown item id: {', '.join(sorted(unknown))}")
            return 1
        items = [i for i in items if i.id in set(args.item)]
    if not args.audio_dir.is_dir():
        print(f"error: 音声のディレクトリが無い: {args.audio_dir}")
        return 1
    variants = [_VARIANTS_BY_NAME[name] for name in args.variant] if args.variant else list(VARIANTS)
    if correct is None and any(v.correct for v in variants):
        correct = llm_correct(args.correction_model)
    if keyword_generator is None and any(v.generated_keywords for v in variants):
        keyword_generator = production_keywords()

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    checkpoint = CheckpointStore(args.checkpoint_dir or _REPORTS_DIR / f"{timestamp}-transcription-checkpoint")
    print(f"checkpoint: {checkpoint.root}\n")
    runner = Runner(
        items=items,
        audio_dir=args.audio_dir,
        checkpoint=checkpoint,
        transcribe=transcribe or openai_transcribe(),
        correct=correct,
        keyword_generator=keyword_generator,
        prompt_limit=args.prompt_limit,
        correction_model=args.correction_model,
        concurrency=args.concurrency,
    )
    try:
        results = await runner.run(variants, args.runs)
    except QuotaExhausted as exc:
        print(f"error: quota exhausted。保存済みの分は同じ --checkpoint-dir で再開できる: {exc}")
        return 1

    meta = {
        "kind": "transcription",
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": args.runs,
        "items": len(items),
        "prompt_limit": args.prompt_limit,
        "correction_model": args.correction_model,
        "dataset_hash": sha256_bytes(args.dataset.read_bytes()),
    }
    report = build_report(results, variants, meta, runner.errors)
    print_summary(report)
    out = args.out or _REPORTS_DIR / f"{timestamp}-transcription.json"
    write_json(out, report)
    print(f"\nreport: {out}")
    return 1 if runner.errors else 0


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(asyncio.run(run(parse_args())))


if __name__ == "__main__":
    main()
