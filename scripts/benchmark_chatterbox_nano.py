#!/usr/bin/env python3
"""Benchmark official Chatterbox Nano without adding it to app dependencies.

Install the pinned upstream checkout in an isolated Python environment, then run:

    python scripts/benchmark_chatterbox_nano.py --suite latency --device cpu \
      --repetitions 1 --pretty

The benchmark downloads the model revision used by this investigation and calls
the official ``ChatterboxTurboTTS`` implementation with ``nano=True`` semantics
through ``from_local(..., nano=True)``. Output records fixture identity and text
shape, never source text. Audio files are only written when ``--audio-dir`` is
provided, so routine benchmark evidence remains small and reviewable.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

try:
    import resource
except ImportError:  # Windows does not provide the Unix resource module.
    resource = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT_ROOT / "tests" / "fixtures" / "reader_quality_v1.json"
IMPLEMENTATION_REVISION = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
MODEL_REPOSITORY = "ResembleAI/chatterbox-nano"
MODEL_REVISION = "71ccd1d0081b430592cea481f4307e764e07bc64"
OFFICIAL_DOWNLOAD_PATTERNS = ["*.safetensors", "*.json", "*.txt", "*.pt", "*.model"]
NANO_RUNTIME_FILES = {
    "added_tokens.json",
    "conds.pt",
    "merges.txt",
    "s3gen_meanflow.safetensors",
    "special_tokens_map.json",
    "t3_nano_v1.safetensors",
    "tokenizer_config.json",
    "ve.safetensors",
    "vocab.json",
}
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
    return peak if sys.platform == "darwin" else peak * 1024


def load_fixtures(corpus_path: Path, suite: str, fixture_id: str) -> list[dict[str, Any]]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    by_id = {fixture["id"]: fixture for fixture in corpus["cases"]}
    fixture_ids = (
        LATENCY_SUITE_FIXTURES
        if suite == "latency"
        else list(by_id)
        if suite == "quality"
        else [fixture_id]
    )
    missing = [item for item in fixture_ids if item not in by_id]
    if missing:
        raise ValueError(f"Unknown fixture(s): {', '.join(missing)}")
    return [by_id[item] for item in fixture_ids]


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if not 0 <= percentile_value <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile_value / 100) * len(ordered)))
    return ordered[rank - 1]


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [run for run in runs if "generationMs" in run]
    if not successful:
        return {
            "successfulRuns": 0,
            "failedRuns": len(runs),
            "firstAudioMedianMs": None,
            "firstAudioP95Ms": None,
            "realTimeFactorMedian": None,
            "averageCpuCoresMedian": None,
        }
    first_audio = [run["firstAudioMs"] for run in successful]
    factors = [run["realTimeFactor"] for run in successful]
    cpu_cores = [run["averageCpuCores"] for run in successful]
    return {
        "successfulRuns": len(successful),
        "failedRuns": len(runs) - len(successful),
        "firstAudioMedianMs": round(statistics.median(first_audio), 3),
        "firstAudioP95Ms": round(percentile(first_audio, 95), 3),
        "realTimeFactorMedian": round(statistics.median(factors), 4),
        "averageCpuCoresMedian": round(statistics.median(cpu_cores), 3),
    }


def directory_size_bytes(directory: Path, names: set[str] | None = None) -> int:
    total = 0
    for path in directory.rglob("*"):
        if path.is_file() and (names is None or path.name in names):
            total += path.stat().st_size
    return total


def measure_call(
    call: Callable[[], Any],
    synchronize: Callable[[], None],
) -> tuple[Any, float, float]:
    synchronize()
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    value = call()
    synchronize()
    wall_ms = (time.perf_counter() - wall_started) * 1000
    cpu_ms = (time.process_time() - cpu_started) * 1000
    return value, wall_ms, cpu_ms


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import torch
    import torchaudio
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    from huggingface_hub import snapshot_download

    fixtures = load_fixtures(args.corpus, args.suite, args.fixture)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was requested but is not available")

    if args.model_dir:
        model_dir = args.model_dir.resolve()
    else:
        model_dir = Path(
            snapshot_download(
                repo_id=MODEL_REPOSITORY,
                revision=args.model_revision,
                allow_patterns=OFFICIAL_DOWNLOAD_PATTERNS,
                token=os.getenv("HF_TOKEN") or None,
            )
        )

    missing_assets = sorted(name for name in NANO_RUNTIME_FILES if not (model_dir / name).is_file())
    if missing_assets:
        raise FileNotFoundError(f"Missing Nano runtime assets: {', '.join(missing_assets)}")

    def synchronize() -> None:
        if args.device == "cuda":
            torch.cuda.synchronize()
        elif args.device == "mps":
            torch.mps.synchronize()

    model, model_load_ms, model_load_cpu_ms = measure_call(
        lambda: ChatterboxTurboTTS.from_local(model_dir, args.device, nano=True),
        synchronize,
    )
    resident_device_bytes = None
    if args.device == "mps":
        resident_device_bytes = int(torch.mps.driver_allocated_memory())
    elif args.device == "cuda":
        resident_device_bytes = int(torch.cuda.memory_allocated())

    def generate(text: str):
        return model.generate(text)

    def seed_generation(seed: int) -> None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    for _ in range(args.warmup_runs):
        seed_generation(args.seed)
        measure_call(lambda: generate("Okay."), synchronize)

    if args.audio_dir:
        args.audio_dir.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    for repetition in range(args.repetitions):
        for fixture in fixtures:
            base = {
                "run": repetition + 1,
                "fixtureId": fixture["id"],
                "textLength": len(fixture["input"]),
                "wordCount": len(fixture["input"].split()),
            }
            try:
                seed_generation(args.seed + repetition)
                wav, generation_ms, cpu_ms = measure_call(
                    lambda text=fixture["input"]: generate(text),
                    synchronize,
                )
                sample_count = int(wav.shape[-1])
                audio_duration_ms = sample_count / model.sr * 1000
                result = {
                    **base,
                    # Official Nano returns one complete tensor, not a stream. The
                    # full generation latency is therefore its earliest audio.
                    "firstAudioMs": round(generation_ms, 3),
                    "generationMs": round(generation_ms, 3),
                    "cpuTimeMs": round(cpu_ms, 3),
                    "averageCpuCores": round(cpu_ms / generation_ms, 3),
                    "sampleCount": sample_count,
                    "audioDurationMs": round(audio_duration_ms, 3),
                    "realTimeFactor": round(generation_ms / audio_duration_ms, 4),
                }
                if args.audio_dir:
                    filename = f"nano-{args.device}-{fixture['id']}-r{repetition + 1}.wav"
                    torchaudio.save(str(args.audio_dir / filename), wav.cpu(), model.sr)
                    result["audioFile"] = filename
                runs.append(result)
            except Exception as error:
                runs.append({
                    **base,
                    "errorType": type(error).__name__,
                    "error": str(error),
                })

    try:
        chatterbox_version = importlib.metadata.version("chatterbox-tts")
    except importlib.metadata.PackageNotFoundError:
        chatterbox_version = "unknown"

    return {
        "schemaVersion": 1,
        "benchmark": "chatterbox-nano-whole-utterance",
        "recordedAtUnixMs": time.time_ns() // 1_000_000,
        "implementation": {
            "repository": "https://github.com/resemble-ai/chatterbox",
            "revision": args.implementation_revision,
            "packageVersion": chatterbox_version,
            "class": "ChatterboxTurboTTS",
            "nano": True,
        },
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": args.model_revision,
            "officialSnapshotBytes": directory_size_bytes(model_dir),
            "loadedRuntimeAssetBytes": directory_size_bytes(model_dir, NANO_RUNTIME_FILES),
            "officialDownloadPatterns": OFFICIAL_DOWNLOAD_PATTERNS,
        },
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": args.device,
            "logicalCpuCount": os.cpu_count(),
            "mpsAvailable": bool(torch.backends.mps.is_available()),
            "cudaAvailable": bool(torch.cuda.is_available()),
        },
        "delivery": {
            "apiMode": "whole-utterance",
            "streamingChunks": False,
            "firstAudioDefinition": "model.generate return; no earlier audio is exposed",
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
            "seed": args.seed,
            "warmupRuns": args.warmup_runs,
            "repetitions": args.repetitions,
        },
        "startup": {
            "modelLoadMs": round(model_load_ms, 3),
            "modelLoadCpuMs": round(model_load_cpu_ms, 3),
            "residentDeviceBytesAfterLoad": resident_device_bytes,
        },
        "summary": summarize_runs(runs),
        "peakRssBytes": peak_rss_bytes(),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    parser.add_argument("--suite", choices=["single", "latency", "quality"], default="single")
    parser.add_argument("--fixture", default="chat-ok-ellipsis")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--model-revision", default=MODEL_REVISION)
    parser.add_argument("--implementation-revision", default=IMPLEMENTATION_REVISION)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--audio-dir", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.repetitions < 1 or args.warmup_runs < 0:
        parser.error("repetitions must be positive; warmup-runs cannot be negative")

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
