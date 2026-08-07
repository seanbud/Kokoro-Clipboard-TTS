# Chatterbox Nano engine-pack spike (issue #27)

Recorded 2026-08-07. Recommendation: **do not build or offer a Chatterbox
Nano pack from the current official v0.1.7 implementation**. It misses the
size, responsiveness, throughput, and memory gates on the available Apple M2
reference machine. Kokoro remains the bundled default and no Chatterbox code,
weights, downloads, settings, or branding are added to the app.

## Tested implementation

- Official source: [`resemble-ai/chatterbox` at `5de7a54`](https://github.com/resemble-ai/chatterbox/commit/5de7a54aa4e5e2baadb0182dde554908b48b85c2), package 0.1.7
- Official model: [`ResembleAI/chatterbox-nano` at `71ccd1d`](https://huggingface.co/ResembleAI/chatterbox-nano/tree/71ccd1d0081b430592cea481f4307e764e07bc64)
- API: `ChatterboxTurboTTS.from_local(..., nano=True)` with the bundled default
  `conds.pt` voice and upstream generation defaults
- Machine: M2 MacBook Air, 8 CPU cores, 16 GB RAM, macOS 14.4, Python 3.10.16,
  Torch 2.6.0
- Corpus: the unchanged `tests/fixtures/reader_quality_v1.json` latency suite
- Each run used one short warmup. The four-fixture pass used one measurement per
  fixture; the short-fixture check used three repetitions to reduce warm-run noise.

The benchmark tool lives at `scripts/benchmark_chatterbox_nano.py`. It is not an
application dependency and imports Chatterbox only inside an isolated benchmark
environment. It records fixture IDs and text shape rather than clipboard text.

## Size gate

The Nano label describes its 110M text-to-speech backbone, not its total shipped
runtime. The current official loader selects every safetensors file, including a
1,056,484,620-byte `s3gen.safetensors` file that Nano does not load.

| Artifact | Bytes | Approximate size |
|---|---:|---:|
| Official loader's selected Nano snapshot | 2,998,584,368 | 2.79 GiB |
| Assets actually loaded by Nano | 1,942,099,748 | 1.81 GiB |
| Isolated installed Python environment used by this spike | 1,299,015,473 | 1.21 GiB |
| Current bundled Kokoro model directory | 355,486,216 | 339 MiB |
| Current v0.8.3 Apple Silicon DMG | 565,275,849 | 539 MiB |

Even a corrected minimal Nano download would contain about 5.5 times the current
Kokoro model bytes before packaging Nano's runtime. The measured benchmark
environment plus official snapshot occupied about 4.0 GiB. A production frozen
pack may compress differently, but this is already enough to fail the pack-size
gate without spending release effort on a PyInstaller prototype.

## Performance gate

The official `generate()` method returns one complete waveform tensor. It does
not expose an audio iterator or callback, so its generation time is also the
earliest possible first audio without maintaining a non-upstream streaming fork.

### Repeated warm short fixture

`chat-ok-ellipsis` (62 characters, 14 words), three repetitions:

| Engine/device | Ready time | Median first audio | Median RTF | Peak RSS |
|---|---:|---:|---:|---:|
| Nano CPU | 10.31 s | 13.02 s | 3.420 | 4.36 GB |
| Nano MPS | 10.82 s | 10.50 s | 2.915 | 3.68 GB |
| Kokoro CPU | 2.75 s | 1.46 s | 0.356 | not collected by baseline runner |
| Kokoro MPS | 2.84 s | 1.09 s | 0.265 | not collected by baseline runner |

On MPS, Nano's median audio became available about 9.7 times later than Kokoro's.
An RTF above 1 means synthesis is slower than the produced audio; Nano measured
about 2.9–3.4 times slower than real time after warmup. This machine therefore
did not reproduce the model card's general “3x faster than realtime on 8 cores”
CPU claim under the official macOS build and this narration fixture.

### Four-fixture latency suite

| Engine/device | Success | Median first audio | p95 | Median RTF | Long-form result |
|---|---:|---:|---:|---:|---|
| Nano CPU | 4/4 | 19.78 s | 37.30 s | 3.427 | 37.30 s for 12.08 s audio |
| Nano MPS | 3/4 | 14.81 s | 16.69 s | 3.567 | failed |
| Kokoro CPU | 4/4 | 3.76 s | 11.72 s | 0.791 | 11.72 s for 14.10 s audio |
| Kokoro MPS | 3/4 | 2.25 s | 2.29 s | 0.557 | failed |

The unbounded 229-character sentence failed on MPS for both engines with
`NotImplementedError: Output channels > 65536 not supported at the MPS device`.
That shared raw-input limitation is why the production planner bounds Kokoro
segments; it also means an MPS Nano pack cannot be advertised as compatible
without the same segmentation and frozen-app validation. CPU Nano completed the
sentence but did not expose any audio during its 37.30-second generation call.

## App-control compatibility

| Capability | Current official Nano behavior | Product implication |
|---|---|---|
| Streaming / early playback | No streaming output | Cannot preserve current overlap or first-audio behavior as-is |
| Cancel generation | Synchronous call has no cancellation hook | Would require killing a worker or maintaining upstream changes |
| Pause/resume | Possible only after audio has been returned to the app | Existing sample-accurate player can handle completed audio |
| Live speed | Compatible downstream through the existing Sonic player | Does not reduce Nano generation wait |
| Long-form structure | Upstream normalization collapses whitespace | The app planner must continue owning segments and external pauses |
| Acronyms/numbers/code | No deterministic product-specific normalization | Existing planner rules remain necessary regardless of engine |

Splitting every sentence or clause into separate calls is not equivalent to true
streaming: it can reduce the first request's length, but each call still has
multi-second latency and may lose cross-clause prosody. It does not rescue the
measured gate.

## Quality, privacy, and licensing

- Nano supports an included default voice and optional voice cloning. Upstream
  requires a reference clip longer than five seconds for cloning. A future pack
  would need explicit local storage/removal UX and must never upload reference
  audio; this spike used only the included voice.
- Once cached, the benchmark ran with `HF_HUB_OFFLINE=1`, confirming local
  inference. A real optional pack would still require an explicit network model
  download, checksums/signatures, progress, removal, and clean Kokoro fallback.
- The upstream code and model card declare MIT; the bundled Perth watermarker is
  also MIT. Distribution still requires a complete transitive dependency/license
  audit and retained notices.
- Upstream applies a Perth neural watermark to every generated file. Product UI
  and documentation would need to disclose that behavior.
- Paralinguistic tags such as `[laugh]` are a real expressive advantage, but they
  do not address deterministic shorthand, number, code, or structure planning.
- A blind, loudness-normalized listener comparison was not run. It remains a
  required gate, but there is no reason to ask users to do that work while the
  objective size and responsiveness gates already fail.

## Reproduction

Install upstream outside the app repository so the core dependency lock remains
unchanged:

```bash
python3.10 -m venv /tmp/chatterbox-nano-bench
/tmp/chatterbox-nano-bench/bin/pip install \
  'git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2'
HF_HUB_DISABLE_XET=1 /tmp/chatterbox-nano-bench/bin/python \
  scripts/benchmark_chatterbox_nano.py \
  --device cpu --suite latency --warmup-runs 1 --repetitions 1 --pretty
```

For MPS, add `PYTORCH_ENABLE_MPS_FALLBACK=1` and use `--device mps`. The script
pins the model revision, uses seed 27 by default, records the selected and loaded
asset sizes, and can write listening samples only when `--audio-dir` is supplied.

## Open gates and revisit trigger

Intel macOS, Windows, frozen-pack packaging, signed download/removal UX, and blind
preference tests were not run. They are intentionally not represented as passing.

Do not spend those gates on v0.1.7. Revisit Nano only when an official release:

1. provides real incremental streaming or a cancellable generator;
2. makes a first chunk available near Kokoro's latency on ordinary hardware;
3. distributes a materially smaller minimal runtime (target under 1 GB installed,
   with the exact product budget decided before implementation); and
4. passes the bounded long-form suite on supported CPU/accelerator paths.

If those triggers occur, rerun this script on Apple Silicon, Intel Mac, and
Windows, then perform the blind listener and frozen-package gates before adding
any in-app engine-download UX.
