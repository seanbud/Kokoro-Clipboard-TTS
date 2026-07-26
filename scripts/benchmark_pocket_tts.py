#!/usr/bin/env python3
"""Benchmark Pocket TTS streaming latency without adding it to app dependencies.

Install Pocket TTS in an isolated environment, then run for example:

    python scripts/benchmark_pocket_tts.py --suite latency --repetitions 3 --pretty

The output records fixture identity and shape, never the source text itself.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # Windows does not provide the Unix resource module.
    resource = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT_ROOT / "tests" / "fixtures" / "reader_quality_v1.json"
LATENCY_SUITE_FIXTURES = [
    "chat-ok-ellipsis",
    "technical-identifiers",
    "structure-paragraph-breaks",
    "long-form-single-sentence",
]


def peak_rss_bytes() -> int | None:
    if resource is None:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux and the other supported Unix runners report KiB.
    return peak if sys.platform == "darwin" else peak * 1024


def load_fixture(corpus_path: Path, fixture_id: str) -> dict[str, Any]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    for fixture in corpus["cases"]:
        if fixture["id"] == fixture_id:
            return fixture
    raise ValueError(f"Unknown fixture {fixture_id!r}")


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile_value / 100) * len(ordered)))
    return ordered[rank - 1]


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [run for run in runs if "firstChunkMs" in run]
    if not successful:
        return {
            "successfulRuns": 0,
            "failedRuns": len(runs),
            "firstChunkMedianMs": None,
            "firstChunkP95Ms": None,
            "realTimeFactorMedian": None,
        }
    first_chunks = [run["firstChunkMs"] for run in successful]
    factors = [run["realTimeFactor"] for run in successful]
    return {
        "successfulRuns": len(successful),
        "failedRuns": len(runs) - len(successful),
        "firstChunkMedianMs": round(statistics.median(first_chunks), 3),
        "firstChunkP95Ms": round(percentile(first_chunks, 95), 3),
        "realTimeFactorMedian": round(statistics.median(factors), 4),
    }


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    from pocket_tts import TTSModel

    fixture_ids = LATENCY_SUITE_FIXTURES if args.suite == "latency" else [args.fixture]
    fixtures = [load_fixture(args.corpus, fixture_id) for fixture_id in fixture_ids]

    load_started = time.perf_counter()
    model = TTSModel.load_model(quantize=args.quantize)
    model_load_ms = (time.perf_counter() - load_started) * 1000

    voice_started = time.perf_counter()
    voice_state = model.get_state_for_audio_prompt(args.voice)
    voice_ready_ms = (time.perf_counter() - voice_started) * 1000

    def stream_once(text: str) -> dict[str, float | int]:
        started = time.perf_counter()
        first_chunk_ms = None
        sample_count = 0
        chunk_count = 0
        for audio in model.generate_audio_stream(
            voice_state,
            text,
            max_tokens=args.max_tokens,
            copy_state=True,
        ):
            if first_chunk_ms is None:
                first_chunk_ms = (time.perf_counter() - started) * 1000
            sample_count += int(audio.shape[-1])
            chunk_count += 1
        generation_ms = (time.perf_counter() - started) * 1000
        if first_chunk_ms is None or sample_count == 0:
            raise RuntimeError("Pocket TTS produced no audio")
        duration_ms = sample_count / model.sample_rate * 1000
        return {
            "firstChunkMs": round(first_chunk_ms, 3),
            "generationMs": round(generation_ms, 3),
            "sampleCount": sample_count,
            "chunkCount": chunk_count,
            "audioDurationMs": round(duration_ms, 3),
            "realTimeFactor": round(generation_ms / duration_ms, 4),
        }

    for _ in range(args.warmup_runs):
        stream_once("Okay.")

    runs = []
    for repetition in range(args.repetitions):
        for fixture in fixtures:
            base = {
                "run": repetition + 1,
                "fixtureId": fixture["id"],
                "textLength": len(fixture["input"]),
                "wordCount": len(fixture["input"].split()),
            }
            try:
                runs.append({**base, **stream_once(fixture["input"])})
            except Exception as error:
                runs.append({
                    **base,
                    "errorType": type(error).__name__,
                    "error": str(error),
                })

    try:
        version = importlib.metadata.version("pocket-tts")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"

    return {
        "schemaVersion": 1,
        "benchmark": "pocket-tts-streaming",
        "recordedAtUnixMs": time.time_ns() // 1_000_000,
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "pocketTts": version,
            "device": "cpu",
        },
        "fixtureSet": {
            "corpusSchemaVersion": 1,
            "suite": args.suite,
            "fixtures": [
                {
                    "id": fixture["id"],
                    "category": fixture["category"],
                    "textLength": len(fixture["input"]),
                    "wordCount": len(fixture["input"].split()),
                }
                for fixture in fixtures
            ],
        },
        "settings": {
            "voice": args.voice,
            "quantize": args.quantize,
            "maxTokens": args.max_tokens,
            "warmupRuns": args.warmup_runs,
            "repetitions": args.repetitions,
        },
        "startup": {
            "modelLoadMs": round(model_load_ms, 3),
            "voiceReadyMs": round(voice_ready_ms, 3),
            "totalReadyMs": round(model_load_ms + voice_ready_ms, 3),
        },
        "summary": summarize_runs(runs),
        "peakRssBytes": peak_rss_bytes(),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["single", "latency"], default="single")
    parser.add_argument("--fixture", default="chat-ok-ellipsis")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--voice", default="alba")
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--quantize", action="store_true")
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.repetitions < 1 or args.warmup_runs < 0 or args.max_tokens < 1:
        parser.error("repetitions/max-tokens must be positive; warmup-runs cannot be negative")

    try:
        result = benchmark(args)
    except Exception as error:
        print(f"Benchmark failed: {error}")
        return 1
    rendered = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
