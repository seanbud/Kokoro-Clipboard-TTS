# Kokoro Clipboard TTS v0.8 Roadmap

Status: v0.8.0 release candidate
Baseline release: v0.7.1
Working release name: **Speech Intelligence**

## Release train

- **v0.7.x — Reader Engine:** shipped the session controller, exact pause/resume, live pitch-preserved speed, structural clipboard planning, startup prewarm, and first-audio feedback.
- **v0.8.x — Speech Intelligence:** ship deliberate handling for numbers and technical text, retained-line-break pauses, replay-current-sentence, voice preview, model consistency, startup diagnostics, and signed updater bootstrap.
- **v1.0 — Stable Reader:** next mainline target. Focus on accessibility, update verification, full supported-platform release evidence, crash recovery, and long-session soak testing.
- **Post-1.0 Engine Lab:** optional model/backend experiments remain evidence-gated and do not block v1.0. Kokoro stays the offline default unless another engine delivers a material listening-quality win without unacceptable package or platform costs.

## Progress ledger

- W0.1 request/session IDs: implemented locally; packaged-app verification pending.
- W0.2 structured lifecycle timing: implemented through the first successful audio write plus stream-acknowledged pause/resume sample offsets; benchmark result persistence pending.
- W0.3 reader-quality corpus: initial 24-case v1 corpus implemented.
- W0.4 benchmark tooling: lifecycle-log analyzer implemented; automated benchmark request runner pending.
- W0.5 fake audio integration harness: the production queue player runs against fake streams with exact offset, multi-chunk ordering, failed-write, cancellation, 50-thread replacement-race, and 500-chunk bounded-queue coverage; real-time 30-minute soak remains a release gate.
- W1.0 clipboard structure recovery: a native command reads both plain text and HTML where the source app provides them; matching HTML is converted to local structural hints, mismatches fall back to plain text, and high-confidence plain heading inference is fixture-locked. Cross-app manual verification remains.
- W1.1–W1.2 structural planner: headings, paragraphs, lists, quotes, code source mapping, bounded sentence/clause segmentation, and segment-specific pauses implemented locally.
- W1.3 normalization rules: conversational shorthand, common uppercase initialisms, informal ellipsis pauses, and word-collision counterexamples are fixture-locked.
- W1.4 number/technical normalization: currency, percentages, ISO dates, clock times, versions, speed multipliers, URLs, email addresses, paths, and inline code have approved spoken-form fixtures; locale selection, long digit policy, and user overrides remain.
- W1.5 code behavior: code blocks are always announced, read with identifier/operator normalization by default, and announced as skipped only when the stored setting is enabled; broader code fixtures remain pending.
- W2.1/W2.8 session controller: per-request cancellation, pause state, chunk/sample position, serialized inference, cancellation-aware queue backpressure, stale-control rejection, and deterministic replacement-race tests implemented locally; live overlap test pending.
- W2.2 persistent queue player: production playback state machine extracted behind a sounddevice-independent stream contract and covered by integration tests; packaged-device testing pending.
- W2.3 exact pause/resume: sample-offset retention implemented locally; live and packaged-app acceptance measurements pending.
- W2.4 sentence navigation: compact replay-current-sentence control and Option/Alt+Left shortcut implemented; forward skip is intentionally omitted.
- W2.6–W2.7 runtime speed: Apache-2.0 Sonic is vendored behind a small streaming C ABI, applies speed changes between 20 ms source blocks, and is wired through UI, Tauri, session state, playback, local build, and release packaging. Native and signed frozen macOS arm64 startup tests pass; Windows, macOS x64, command-to-audible measurement, and human listening gates remain.
- W3.1–W3.2 latency path: default engine prewarms before health/ready, the fixed 100 ms request delay is removed, and the 250 ms first-buffer silence is replaced by concurrent output-stream warmup; live clipping check pending.
- W3.4–W3.6 first-audio feedback: rolling local median keyed by backend, voice, and first-segment-size bucket; low-confidence indeterminate state; conservative 90%-capped bar; and half-second remaining-time label implemented. Playback-remaining estimate is pending.
- W3.7 compact packaging: unused ONNX/test modules were removed from the frozen build, producing an approximately 503 MB Apple Silicon candidate. A roughly 1 GB pre-extracted runtime improved repeat startup but was rejected as a poor product tradeoff; the compact offline build remains the release path.
- W6 update/recovery: signed updater metadata, download progress, install/restart controls, startup milestones, saved-shortcut restoration, and version display are implemented. v0.8.0 bootstraps the signing channel; v0.8.1 must prove an installed update from v0.8.0.
- W4.2 backend benchmark: corpus-driven PyTorch CPU/MPS runner and initial M2 reference suite implemented; Windows/CUDA and frozen-package measurements pending.
- W5.3 Pocket TTS benchmark: isolated v2.1.0 CPU streaming runner and initial M2 unquantized/quantized measurements implemented; blind quality and frozen-package work pending.
- W5.4 Chatterbox Nano benchmark: the official v0.1.7 implementation failed the Apple M2 size, first-audio, throughput, and memory gates. Keep it out of the app and revisit only after upstream provides a materially smaller streaming distribution; see `docs/investigations/chatterbox-nano-issue-27.md`.
- Remaining W1–W6 work: active, sequenced below; engine promotion remains evidence-gated.

## Release outcome

v0.8 should make reading feel deliberate and dependable without increasing the installed footprint or replacing the proven Kokoro default.

The release is successful when it:

1. preserves useful document structure and handles common shorthand, numbers, links, paths, and code intentionally;
2. adds a compact replay-current-sentence action without a forward-skip button;
3. previews voices before saving and restores customized shortcuts on restart;
4. reports honest cold-start and first-audio progress while retaining the compact offline package;
5. eliminates training-mode variability in Kokoro inference; and
6. bootstraps signed cross-platform updates for verification in the first v0.8 patch release.

This roadmap separates model inference, speech planning, and audio playback. That separation is required: changing models alone cannot recover formatting that the app discarded or fix playback state that the app never tracked.

## Product principles

- **Local by default:** clipboard content must remain on the device. No cloud inference or telemetry is part of v0.7.
- **Stable default, explicit experiments:** experimental engines and compute backends must be opt-in and must fall back safely.
- **Measure audible latency:** generation completion and first audible sample are different events. Acceptance tests use the latter.
- **Preserve meaning, not markup:** formatting should become pauses and reading cues rather than being read literally or collapsed indiscriminately.
- **User correction beats hidden heuristics:** pronunciation and shorthand behavior must be inspectable and overrideable.
- **Cross-platform packaging is part of the feature:** a backend is not supported until it works in the frozen Windows and macOS applications.

## Aligned product decisions

Confirmed with the product owner on 2026-07-25. Primary-content weighting and final engine promotion still require listening evidence, but implementation semantics are no longer open.

| Decision | Default assumption | Consequence if changed |
|---|---|---|
| Primary content | Articles, documentation, AI/chat responses, and email; code is secondary | Changes the weighting of the speech-quality corpus |
| Clipboard structure | Prefer matching rich clipboard HTML; otherwise preserve plain-text boundaries and infer only high-confidence short headings. Never alter the selected words to invent structure | Requires native HTML clipboard reads plus source-app compatibility tests |
| Runtime speed semantics | Pitch-preserved changes affect already-playing speech mid-sentence, targeting 150 ms p95; optimize and recommend 0.75x–1.5x, with 0.5x–2.0x treated as an advanced range | Requires a real-time time-stretch DSP path; regeneration at sentence boundaries is insufficient |
| Code blocks | Always announce code blocks; read them intelligently by default; skip only when the user enables the setting | Requires a stored setting plus concise identifier/operator normalization |
| Informal shorthand | `idk`, `lol`, `TBH`, and `imo` are pronounced as initialisms for now; later user dictionary rules override built-ins | Changes default lexicon fixtures only |
| Experimental models | Pocket TTS may be offered as an opt-in on-device engine; Kokoro remains the installed fallback until quality and packaging gates pass | Requires in-app lifecycle/download UX and engine-specific voices/settings |
| Release numbering | Ship Speech Intelligence as v0.8.0, then target v1.0 hardening directly | A mandatory v0.9 engine release would delay stability work without a demonstrated user benefit |

## v0.6.3 baseline evidence

- `src/utils/textCleaner.ts` collapses all whitespace, including paragraph and list boundaries, with `\s+`.
- `sidecar/kokoro_server.py` tracks pause and stop globally rather than by playback session.
- Pausing during a chunk restarts that chunk on resume because no sample offset is retained.
- Changing speed in `FloatingWidget.tsx` updates persisted UI state but sends no command to active playback.
- The sidecar waits 100 ms before starting a request, prepends 250 ms of silence to the first chunk, and adds 200 ms after every generated chunk.
- The UI infers playback from sidecar log text rather than receiving structured synthesis/playback events.
- The official general-purpose Kokoro model remains v1.0. Alternative runtimes use the same weights and therefore do not inherently improve prosody.
- Local M2 measurements showed that PyTorch MPS and quantized ONNX CPU were slower than the existing PyTorch CPU path. Hardware acceleration cannot be assumed from provider availability.
- The v0.6.3 baseline had 21 text-cleaner tests and no Rust unit tests. Existing release testing verifies startup and a beep rather than the full reader behavior in this roadmap.

### Initial backend reference measurement

Measured locally on 2026-07-25 using an Apple M2, macOS 14.4, PyTorch 2.11.0, Kokoro 0.9.4, one short warmup, and one pass over four differently sized corpus fixtures. These are diagnostic results, not release acceptance evidence.

| Backend | Ready time | Successful fixtures | First-chunk median | First-chunk p95 | Critical observation |
|---|---:|---:|---:|---:|---|
| PyTorch CPU | 2.75 s | 4/4 | 1.36 s | 4.84 s | Reliable, but the 37-word single sentence took 4.84 s |
| PyTorch MPS | 3.03 s | 3/4 | 0.78 s | 0.86 s among successes | Faster for bounded inputs, but the 37-word sentence failed with the MPS 65,536-output-channel limit |

MPS is therefore not eligible for automatic selection with the unbounded v0.6.3 sentence path. The local structural planner splits the failing 229-character fixture into 136- and 92-character semantic segments, both of which synthesized successfully on MPS. The full suite and frozen package must still pass before MPS is reconsidered for automatic selection.

A second three-repetition CPU diagnostic after adding startup prewarm measured 3.15 s to load the engine and a 2.97 s median across 12 raw-fixture runs (fixture medians 1.60–9.28 s). This is intentionally not presented as an improvement: the runner still sends each raw fixture directly, while the application now sends bounded planned segments. It confirms that startup prewarm moves roughly 3–4 seconds out of the first user request, but end-to-end first-audio acceptance must be measured through the real planned request path and remains open.

## Target architecture

```text
Clipboard text
    |
    v
Clipboard structure recovery
  - plain text is the content authority
  - matching HTML restores headings, paragraphs, lists, and explicit breaks
  - conservative fallback when formatting is absent or disagrees
    |
    v
Speech planner
  - preserves source structure
  - normalizes spoken forms
  - emits semantic segments and pause intent
    |
    v
Engine adapter
  - Kokoro stable adapter
  - experimental Pocket TTS adapter
  - structured synthesis events and timing
    |
    v
Session audio controller
  - session ID and cancellation
  - generated-chunk lookahead/cache
  - sentence index and sample offset
  - pitch-preserved playback speed
    |
    v
Tauri event contract -> reader widget
```

### Planned segment contract

The speech planner should return data rather than one flattened string:

```ts
type SpeechSegment = {
  id: string;
  sourceText: string;
  spokenText: string;
  kind: "heading" | "paragraph" | "sentence" | "list-item" | "quote" | "code";
  pauseAfterMs: number;
  sourceStart: number;
  sourceEnd: number;
};
```

Exact transport types may change, but source mapping, segment kind, and pause intent are required.

## Workstreams

### W0 — Instrumentation and regression corpus

This work lands first so later performance and quality claims are supported by evidence.

Tasks:

- W0.1 Add request/session IDs to all sidecar events.
- W0.2 Emit structured timestamps for request received, planning complete, inference start, first chunk ready, first sample written, pause acknowledged, resume acknowledged, and playback finished.
- W0.3 Create a versioned reader-quality corpus containing prose, chat, formatting, acronyms, numbers, URLs, filenames, and code.
- W0.4 Add a benchmark runner that records cold start, warm time-to-first-audio, real-time factor, peak memory, and generated duration as JSON.
- W0.5 Add an audio/control integration harness using a fake output sink so pause position and chunk ordering can be tested without speakers.

Acceptance criteria:

- Every request has one unique ID propagated through UI, Rust, and sidecar events.
- Old or cancelled requests cannot emit state changes for the active session.
- Benchmark results record OS, architecture, backend, model, voice, text fixture, and cold/warm state.
- Timing events are generated from the actual audio write path, not inferred from log strings.

### W1 — Structured speech planner

Tasks:

- W1.0 Read plain and HTML clipboard representations, accept rich structure only when visible words match, and retain a deterministic plain-text fallback.
- W1.1 Replace destructive whitespace flattening with block-aware parsing.
- W1.2 Convert headings, paragraphs, lists, quotes, and blank lines into semantic segments and configurable pauses.
- W1.3 Add deterministic English normalization for common chat shorthand and acronyms.
- W1.4 Add locale-aware normalization for numbers, currency, time, dates, percentages, units, versions, and long digit strings.
- W1.5 Always announce code blocks. Read identifiers and operators intelligently by default; when the user enables **Skip code blocks**, announce that the block was skipped instead of reading its contents.
- W1.6 Add a user pronunciation/replacement dictionary with whole-word and case-sensitive options.
- W1.7 Preserve source offsets so the UI can show the current sentence later.

Initial pause policy to validate by listening tests:

| Boundary | Initial pause |
|---|---:|
| Comma/clause | model-controlled |
| Sentence | 120 ms external minimum |
| List item | 220 ms |
| Paragraph | 420 ms |
| Heading | 550 ms |
| Major section/blank-line run | 700 ms maximum |

Acceptance criteria:

- Paragraphs and list items remain distinguishable after planning.
- HTML-derived structure never changes the selected visible words and falls back to plain text on any mismatch.
- Copy fixtures from at least one browser, document editor, chat app, and plain-text editor pass on Windows and macOS; the test record identifies which structural formats each source actually supplies.
- When formatting is absent, inferred headings require conservative evidence and hard-wrapped prose remains unsplit in regression fixtures.
- Every normalization rule has input/output fixtures, including punctuation and word-boundary counterexamples.
- User dictionary rules override built-in shorthand rules.
- Planning is deterministic, offline, and does not log clipboard text in release builds.
- A blind listening pass rates the planned version equal or better than the v0.6.3 baseline on at least 80% of corpus items, with no critical regressions.

### W2 — Session audio controller and runtime controls

Tasks:

- W2.1 Replace global playback events with a session object containing cancellation, chunk index, and sample offset.
- W2.2 Use a persistent output stream with bounded block writes and exact offset accounting.
- W2.3 Implement pause/resume without replay or skip.
- W2.4 Add sentence back/forward commands and cache recently generated sentence audio.
- W2.5 Add bounded lookahead generation with backpressure.
- W2.6 Prototype pitch-preserved time stretching suitable for frozen Windows and macOS builds.
- W2.7 Apply active speed changes at the agreed boundary and invalidate only stale future audio.
- W2.8 Make stop/new-request cancellation race-safe.

Acceptance criteria:

- Pause reaches silence within 100 ms at p95.
- Resume starts within 150 ms at p95 when current audio is cached.
- Resume position differs by no more than 100 ms and never restarts the sentence.
- A new request cannot leak audio or completion events from the previous session.
- Previous/next sentence responds within 150 ms when target audio is cached.
- Speed changes preserve pitch perceptually and do not create a gap over 250 ms at the agreed transition boundary.
- Thirty minutes of continuous playback produces no unbounded queue or memory growth.

Decision gate W2-D1:

- Mid-sentence behavior is required. Use Sonic as the production candidate: it is an Apache-2.0 ANSI C streaming library built specifically for pitch-preserving speech-rate control, with no Python-wheel or C++ runtime dependency.
- A native Apple M2 spike at 24 kHz preserved a 220 Hz test tone within 1 Hz at 0.5x, 0.75x, 1x, 1.5x, and 2x; processed two seconds of input in roughly 0.8–3.6 ms; and reflected a 1x-to-2x change no later than the second 20 ms input block. Synthetic tests validate duration and pitch but do not replace human speech listening.
- Use approximately 20 ms source buffers so the slowest 0.5x output write remains about 40 ms. The speed endpoint updates session state; the playback DSP reads it between buffers without regeneration, replay, or pitch change.
- Treat 0.75x–1.5x as the recommended, quality-first range and apply the strictest listening gate there. Keep 0.5x–2.0x available as an advanced range, clearly allowing more artifacts at its extremes.
- The existing `python-stretch` wrapper is rejected for this path because each `process()` call pads, flushes, and resets the processor; using it buffer-by-buffer is not continuous real-time streaming. Signalsmith's MIT-licensed C++ core remains a fallback only if the project owns a true streaming binding. Reject Rubber Band for the default implementation unless a commercial license is purchased because its open-source distribution is GPL; SoundTouch remains the LGPL fallback.

### W3 — Faster first audio and honest progress

Tasks:

- W3.1 Load and warm the selected default engine during sidecar startup.
- W3.2 Remove the fixed pre-request delay and replace first-chunk silence with output-stream warmup or a measured minimum.
- W3.3 Prioritize a short first semantic segment, then generate larger lookahead segments.
- W3.4 Add rolling device-local estimates keyed by backend, voice, and first-segment size.
- W3.5 Show preparation, first-audio generation, playback progress, and estimated remaining time in the widget.
- W3.6 Ensure estimates degrade to indeterminate state when confidence is low rather than displaying false precision.
- W3.7 Reduce cold app readiness time by auditing broad PyInstaller `collect-all` rules, excluding development/tests and unused backends, and comparing one-file extraction with a signed pre-extracted sidecar layout.

Acceptance criteria on supported reference hardware:

- Warm first-audio median is at most 750 ms and p95 is at most 1.5 seconds for the short-text fixture set, or the release documents an approved hardware-specific exception.
- Cold-start and warm-start latency are reported separately.
- Cold installed-app launch reaches a synthesis-ready health state within 10 seconds p95 on the supported reference machines.
- The progress indicator never reaches zero or 100% before audio is ready.
- Once at least five comparable local samples exist, first-audio estimates are within the greater of 500 ms or 35% for at least 80% of requests.
- Playback remaining time updates from generated audio duration and clearly marks estimated pending duration.

### W4 — Experimental compute backends

The feature is backend selection, not a promise that a GPU is faster.

Tasks:

- W4.1 Define `Auto`, `CPU`, and platform-supported experimental providers behind one capability API.
- W4.2 Benchmark PyTorch CPU/CUDA/MPS and viable ONNX providers on supported packaging targets.
- W4.3 Make `Auto` choose only from providers that pass a startup, synthesis, and output-equivalence smoke test.
- W4.4 Fall back to CPU after initialization or inference failure and surface the reason in diagnostics.
- W4.5 Record package-size, startup-time, memory, and driver/runtime requirements for each provider.

Acceptance criteria:

- Provider selection never prevents the app from starting.
- `Auto` does not choose a provider slower than CPU by more than 10% on the calibration fixture.
- An experimental provider must improve either warm first-audio or long-text throughput by at least 20% on a supported hardware class before it is recommended in UI.
- Frozen Windows and macOS packages pass the same synthesis fixtures as development mode.
- UI language says “compute backend,” not “GPU boost,” and marks non-default providers experimental.

Decision gate W4-D1:

- Drop a provider from v0.7 if its packaged runtime cost or failure rate outweighs measured benefit. Provider availability alone is not sufficient.

### W5 — Experimental speech-engine bake-off

Candidates:

1. Kokoro v1.0 PyTorch — stable baseline.
2. Pocket TTS — primary experimental candidate due to CPU streaming and low reported first-audio latency.
3. Chatterbox Nano — evaluate if packaging and first-audio latency are competitive.
4. Kitten TTS — evaluate normalization and package size, but treat developer-preview status as a risk.

Qwen3-TTS is excluded from the v0.7 desktop default because its 0.6B/1.7B models and GPU-oriented deployment conflict with the lightweight zero-config target. It can be reconsidered as an optional power-user engine later.

Tasks:

- W5.1 Implement a narrow engine-adapter protocol and keep playback outside model-specific code.
- W5.2 Produce anonymized, loudness-normalized blind samples for the regression corpus.
- W5.3 Measure latency, throughput, peak memory, model size, frozen binary size, and supported platforms.
- W5.4 Score pronunciation, stress, pausing, stability, voice preference, and normalization interaction.
- W5.5 Ship at most one non-Kokoro experimental engine in v0.7.

Scorecard:

| Dimension | Weight |
|---|---:|
| Blind speech preference | 30% |
| Warm time-to-first-audio | 20% |
| Pronunciation/prosody corpus pass rate | 15% |
| Cross-platform frozen-build reliability | 15% |
| Installer/model download size | 10% |
| Long-text throughput and memory | 10% |

Promotion requirements:

- An engine must beat Kokoro's weighted score by at least 10% to become the recommended default.
- A result within 10% remains experimental; Kokoro stays default.
- Any licensing, offline-operation, or frozen-build failure disqualifies an engine regardless of audio score.

#### Pocket TTS reference measurement

Measured locally on 2026-07-25 using Pocket TTS 2.1.0, Python 3.12.13, and an Apple M2. The unquantized run used one warmup and three passes over the four-fixture latency suite (12 successful runs):

| Variant | Cached engine + voice ready | Successful runs | First streamed frame median | First streamed frame p95 | Median full-generation RTF | Peak process RSS |
|---|---:|---:|---:|---:|---:|---:|
| Pocket TTS CPU | 0.80 s | 12/12 | 87 ms | 171 ms | 0.265 | 1.05 GB |
| Pocket TTS CPU quantized | 0.97 s | 4/4 | 160 ms | 403 ms | 0.568 | 1.12 GB |

The first uncached run took 22.3 seconds to download/load the model and prepare its voice; bundling or explicitly downloading weights removes network time. The cached Hugging Face weight snapshot occupies about 215 MB, and the isolated Python environment occupies about 719 MB before packaging/deduplication. Quantization is not recommended on this M2 because it regressed both latency and throughput without reducing observed peak RSS.

Pocket TTS passes the performance threshold for an experimental adapter by a wide margin, but not the overall promotion gate: blind speech-quality preference, pause/segment continuity, Windows and frozen-macOS packaging, and installer delta are still unmeasured. Its official API streams roughly 80 ms frames; its documented inability to encode requested silence in text means the app's existing structural segment and silence mixer remains necessary. Keep Kokoro as default until those gates pass.

A signed local macOS arm64 Kokoro/Sonic PyInstaller smoke build passed startup and health, but the current broad `collect-all` recipe produced a 525 MB one-file sidecar before the outer app installer. That is a base-runtime packaging problem to address in W3.7, and it strengthens the decision not to merge Pocket's roughly 719 MB isolated environment into every user's base install without a measured, compressed-delta gate.

#### Pocket TTS product and distribution decision

Pocket TTS is a separate 100M-parameter speech model, not “faster Kokoro.” It has different voices and may sound better on some text and worse on other text. It has no per-use monetary cost because inference remains local; “cheaper” means lower waiting/compute time, offset by additional disk and maintenance cost.

For v0.7, use one normal app installer and an in-app optional engine flow rather than separate “Kokoro” and “Pocket” installers or a manual GitHub setup:

1. Settings shows **Kokoro — Stable, Installed** and **Pocket TTS — Experimental, Faster start, ~215 MB model download**.
2. Pocket is never downloaded automatically. The user explicitly selects Download, sees progress/disk requirements and license/privacy text, and can cancel or remove it.
3. Pin engine-pack versions and SHA-256 hashes in a signed manifest. Download to a temporary app-data file, verify it, then atomically activate it; resume interrupted downloads when the host permits.
4. Keep engine-specific voice choices. Switching engines stops the current session, warms the target engine, and falls back to Kokoro with a visible diagnostic if loading or synthesis fails.
5. Clipboard text never leaves the machine. Network access is only for the user-requested engine asset.
6. Bundle Pocket's adapter code with the main sidecar only if the compressed installer delta stays below 75 MB. Otherwise ship a signed per-platform engine pack so non-users do not pay the dependency cost.
7. Publish engine assets for Windows x64, macOS arm64, and macOS x64 through the normal release pipeline. Do not label a platform supported until a frozen binary synthesizes the corpus there.
8. Do not expose voice cloning in v0.7; it adds consent, impersonation, storage, and support risks unrelated to the reader goal.

GitHub release assets may host the signed model/engine artifacts, but users should install and manage them inside the app. Requiring manual GitHub downloads creates path, version, checksum, and support failures; separate installers fragment updates and confuse which app owns settings.

### W6 — Reader UX and accessibility

Tasks:

- W6.1 Add previous/next sentence controls without making the compact widget materially larger by default.
- W6.2 Show current sentence position and estimated remaining time in an expandable detail state.
- W6.3 Add Article, Chat, and Code reading profiles.
- W6.4 Add settings for code behavior, shorthand defaults, pause strength, and pronunciation replacements.
- W6.5 Add local “report bad reading” export containing source, planned segments, non-sensitive runtime metadata, and settings only after explicit user action.
- W6.6 Ensure controls have keyboard access, accessible names, visible focus, and non-color status cues.

Acceptance criteria:

- All playback actions are usable without a mouse.
- The compact widget retains its current primary play/pause, stop, speed, and close actions.
- The UI distinguishes preparing, generating, speaking, paused, finished, and error states from structured events.
- Diagnostic export previews exactly what will be saved and never transmits it.

## Execution order

```text
Milestone A: Evidence foundation
  W0 instrumentation + corpus

Milestone B: Reader correctness
  W1 speech planner
  W2 session controller, exact pause/resume, sentence navigation

Milestone C: Perceived performance
  W3 warmup, first-segment priority, progress/ETA

Milestone D: Experiments
  W4 backend matrix
  W5 Pocket TTS bake-off

Milestone E: Product integration
  W6 settings, profiles, accessibility, diagnostics

Milestone F: Release hardening
  cross-platform frozen builds, soak tests, migration, documentation
```

W4 and W5 begin only after W0 produces trustworthy measurements. W6 visual work can begin after the W1/W2 event and state contracts stabilize.

## Proposed implementation slices

Each slice should be independently reviewable and releasable behind flags where appropriate.

1. **Session event contract:** typed event schema, request IDs, cancellation tests.
2. **Speech planner foundation:** semantic blocks and preserved offsets with fixtures.
3. **Normalization pack:** shorthand, numbers, and code policies with fixtures.
4. **Playback state machine:** exact offset pause/resume using a fake audio sink.
5. **Sentence queue:** lookahead, back/forward, bounded cache, race tests.
6. **Speed DSP spike:** compare embedded candidates and choose/package one.
7. **Latency pass:** warmup, remove fixed waits, short first segment, measurement.
8. **Progress UI:** structured states, first-audio estimate, remaining time.
9. **Backend lab:** benchmark and package viable CPU/GPU providers.
10. **Pocket adapter and bake-off:** samples, scorecard, promotion decision.
11. **Reader UX:** navigation, profiles, dictionary, accessibility.
12. **Release hardening:** installers, soak tests, upgrade path, docs.

## Test strategy

### Unit tests

- Speech-plan parsing and source offsets.
- Normalization word boundaries, punctuation, casing, locales, and overrides.
- Playback state-machine transitions.
- ETA estimator confidence and fallback behavior.
- Backend capability and fallback selection.

### Integration tests

- UI -> Tauri -> sidecar event ordering with a fake synthesis engine.
- Sidecar -> fake audio sink exact sample accounting.
- New-request cancellation during planning, inference, queued playback, and pause.
- Speed/voice change invalidation of current versus future buffers.
- Speed-command acknowledgement and first changed audio block within 150 ms p95, tested throughout 0.75x–1.5x and at the 0.5x/2.0x advanced endpoints.
- Frozen sidecar starts and synthesizes actual speech, not only a test beep.

### Manual listening tests

- Blind A/B files use equal loudness and anonymous engine labels.
- Testers score naturalness, intelligibility, stress, pauses, and overall preference.
- Runtime-speed listening is weighted to the recommended 0.75x–1.5x range, with separate artifact notes for the 0.5x and 2.0x advanced endpoints.
- Failures are retained as regression fixtures with the planned spoken form.
- At least one Windows and one Apple Silicon tester complete the release corpus.

### Performance tests

- Cold launch -> ready.
- Warm request -> first audible sample.
- Warm request -> complete generation.
- Pause/resume and navigation response.
- 1, 5, and 30-minute texts.
- CPU, memory, queue depth, and package size.

## v0.7.0 release gates

v0.7.0 cannot ship until:

- frontend, Rust, Python, and native Sonic automated suites pass;
- the signed frozen Apple Silicon sidecar starts, prewarms Kokoro and Sonic, and reports healthy;
- release CI produces healthy frozen Windows x64, macOS arm64, and macOS x64 packages before a release is published;
- manual Apple Silicon testing confirms live speed, pause/resume, immediate widget close, and acceptable 0.75x–1.5x audio;
- experimental Pocket/GPU work is absent or disabled by default;
- installer upgrade from v0.6.3 preserves voice, volume, speed, and shortcut settings;
- privacy review confirms no clipboard content is logged or transmitted by default;
- README and release-testing documentation match the actual v1.0 model/runtime bundle; and
- release checks are recorded in the candidate notes.

The broader acceptance, corpus, accessibility, 30-minute soak, and engine-promotion gates below remain the path to v1.0 rather than blocking this focused v0.7.0 release.

## Explicit non-goals for v0.7

- Cloud TTS providers.
- Automatic LLM rewriting of clipboard content.
- Default voice cloning.
- Shipping multiple large experimental engines in the installer.
- Claiming universal GPU acceleration.
- Full screen-reader or operating-system accessibility API replacement.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Rules improve some phrases but alter technical meaning | Profiles, source mapping, previewable overrides, regression corpus |
| Time-stretch dependency breaks frozen builds | Select through a packaging spike before committing; retain next-sentence fallback |
| Experimental model inflates downloads | Optional versioned model packs with checksum and removal controls |
| GPU provider is slower or unstable | Calibration, explicit experiment flag, automatic CPU fallback |
| More segmentation creates robotic gaps | Listening-tested pause policy and model/external pause separation |
| Multiple worker threads leak stale events | Session IDs, cancellation tokens, bounded queues, state-machine tests |
| ETA becomes misleading | Local rolling estimates, confidence threshold, indeterminate fallback |

## Definition of done

The release is done only when the packaged applications—not only development mode—demonstrate the control, speech-planning, latency, progress, privacy, and fallback behavior in this roadmap, with recorded evidence from the test corpus and supported platform matrix.
