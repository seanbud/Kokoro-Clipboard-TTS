#!/usr/bin/env python3
"""Benchmark Kokoro model loading and warm first-chunk synthesis.

The command uses the repository's bundled model and versioned reader-quality
corpus. It records fixture identity and length, never the source text itself.

Examples:
    .sidecar-venv/bin/python scripts/benchmark_kokoro_backend.py --device cpu
    PYTORCH_ENABLE_MPS_FALLBACK=1 .sidecar-venv/bin/python \
      scripts/benchmark_kokoro_backend.py --device mps --repetitions 3 --pretty
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
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT_ROOT / "tests" / "fixtures" / "reader_quality_v1.json"
DEFAULT_MODEL_DIR = PROJECT_ROOT / "sidecar" / "model"
LATENCY_SUITE_FIXTURES = [
    "chat-ok-ellipsis",
    "technical-identifiers",
    "structure-paragraph-breaks",
    "long-form-single-sentence",
]


def load_fixture(corpus_path: Path, fixture_id: str) -> dict[str, Any]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    for fixture in corpus["cases"]:
        if fixture["id"] == fixture_id:
            return fixture
    available = ", ".join(item["id"] for item in corpus["cases"])
    raise ValueError(f"Unknown fixture {fixture_id!r}. Available fixtures: {available}")


def percentile(values: list[float], percentile_value: float) -> float:
    """Return a nearest-rank percentile suitable for small benchmark samples."""

    if not values:
        raise ValueError("values must not be empty")
    if percentile_value < 0 or percentile_value > 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile_value / 100) * len(ordered)))
    return ordered[rank - 1]


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        raise ValueError("runs must not be empty")

    successful = [run for run in runs if "firstChunkMs" in run]
    failed_count = len(runs) - len(successful)
    if not successful:
        return {
            "successfulRuns": 0,
            "failedRuns": failed_count,
            "firstChunkMedianMs": None,
            "firstChunkP95Ms": None,
            "realTimeFactorMedian": None,
        }

    first_chunk = [run["firstChunkMs"] for run in successful]
    real_time_factors = [run["realTimeFactor"] for run in successful]
    return {
        "successfulRuns": len(successful),
        "failedRuns": failed_count,
        "firstChunkMedianMs": round(statistics.median(first_chunk), 3),
        "firstChunkP95Ms": round(percentile(first_chunk, 95), 3),
        "realTimeFactorMedian": round(statistics.median(real_time_factors), 4),
    }


def summarize_by_fixture(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fixture_ids = dict.fromkeys(run["fixtureId"] for run in runs)
    return {
        fixture_id: summarize_runs(
            [run for run in runs if run["fixtureId"] == fixture_id]
        )
        for fixture_id in fixture_ids
    }


def synchronize_device(torch_module: Any, device: str) -> None:
    if device == "cuda":
        torch_module.cuda.synchronize()
    elif device == "mps":
        torch_module.mps.synchronize()


def measure_call(
    call: Callable[[], Any],
    synchronize: Callable[[], None],
) -> tuple[Any, float]:
    synchronize()
    start = time.perf_counter()
    value = call()
    synchronize()
    return value, (time.perf_counter() - start) * 1000


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from kokoro import KModel, KPipeline

    fixture_ids = LATENCY_SUITE_FIXTURES if args.suite == "latency" else [args.fixture]
    fixtures = [load_fixture(args.corpus, fixture_id) for fixture_id in fixture_ids]
    model_path = args.model_dir / "kokoro-v1_0.pth"
    config_path = args.model_dir / "config.json"
    voice_path = args.model_dir / "voices" / f"{args.voice}.pt"
    for required in (model_path, config_path, voice_path):
        if not required.is_file():
            raise FileNotFoundError(f"Required benchmark asset not found: {required}")

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was requested but is not available")

    synchronize = lambda: synchronize_device(torch, args.device)

    model, model_load_ms = measure_call(
        lambda: KModel(
            repo_id="hexgrad/Kokoro-82M",
            config=str(config_path),
            model=str(model_path),
        ).to(args.device).eval(),
        synchronize,
    )
    pipeline, pipeline_ready_ms = measure_call(
        lambda: KPipeline(
            lang_code="a",
            repo_id="hexgrad/Kokoro-82M",
            model=model,
        ),
        synchronize,
    )

    def synthesize_first_chunk(source_text: str):
        return next(
            pipeline(
                source_text,
                voice=str(voice_path),
                speed=args.speed,
            )
        )

    for _ in range(args.warmup_runs):
        measure_call(lambda: synthesize_first_chunk("Okay."), synchronize)

    runs = []
    for index in range(args.repetitions):
        for fixture in fixtures:
            text = fixture["input"]
            try:
                result, first_chunk_ms = measure_call(
                    lambda text=text: synthesize_first_chunk(text),
                    synchronize,
                )
            except Exception as error:
                runs.append(
                    {
                        "run": index + 1,
                        "fixtureId": fixture["id"],
                        "textLength": len(text),
                        "wordCount": len(text.split()),
                        "errorType": type(error).__name__,
                        "error": str(error),
                    }
                )
                continue
            sample_count = int(result.audio.shape[-1])
            audio_duration_ms = sample_count / 24_000 * 1000
            runs.append(
                {
                    "run": index + 1,
                    "fixtureId": fixture["id"],
                    "textLength": len(text),
                    "wordCount": len(text.split()),
                    "firstChunkMs": round(first_chunk_ms, 3),
                    "sampleCount": sample_count,
                    "audioDurationMs": round(audio_duration_ms, 3),
                    "realTimeFactor": round(first_chunk_ms / audio_duration_ms, 4),
                }
            )

    try:
        kokoro_version = importlib.metadata.version("kokoro")
    except importlib.metadata.PackageNotFoundError:
        kokoro_version = "unknown"

    return {
        "schemaVersion": 1,
        "benchmark": "kokoro-first-chunk",
        "recordedAtUnixMs": time.time_ns() // 1_000_000,
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "kokoro": kokoro_version,
            "device": args.device,
            "mpsAvailable": bool(torch.backends.mps.is_available()),
            "cudaAvailable": bool(torch.cuda.is_available()),
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
            "speed": args.speed,
            "warmupRuns": args.warmup_runs,
            "repetitions": args.repetitions,
        },
        "startup": {
            "modelLoadMs": round(model_load_ms, 3),
            "pipelineReadyMs": round(pipeline_ready_ms, 3),
            "totalReadyMs": round(model_load_ms + pipeline_ready_ms, 3),
        },
        "summary": summarize_runs(runs),
        "summaryByFixture": summarize_by_fixture(runs),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    parser.add_argument("--suite", choices=["single", "latency"], default="single")
    parser.add_argument("--fixture", default="chat-ok-ellipsis")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--voice", default="am_fenrir")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.warmup_runs < 0:
        parser.error("--warmup-runs must not be negative")
    if args.speed < 0.5 or args.speed > 2.0:
        parser.error("--speed must be between 0.5 and 2.0")

    try:
        result = benchmark(args)
    except Exception as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
