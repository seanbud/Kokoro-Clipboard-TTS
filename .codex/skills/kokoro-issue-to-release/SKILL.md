---
name: kokoro-issue-to-release
description: Take a Kokoro Clipboard TTS GitHub issue through triage, diagnosis, implementation, cross-platform verification, pull request review, merge, and signed updater release. Use for issue fixes, feature work, PR preparation, CI failures, version releases, and post-release verification in this repository.
---

# Kokoro Issue to Release

Ship one well-understood change without regressing the app's offline, responsive,
cross-platform reader experience. Read `references/repo-map.md` before editing.

## Establish scope

1. Read the issue body, all comments, linked PRs, and attached media. Prefer the
   GitHub connector; use `gh` when thread state, checks, or releases need it.
2. Restate the user-visible failure and turn it into explicit acceptance criteria.
   Separate facts, hypotheses, and product choices.
3. Inspect the relevant code and history. Reproduce or create the smallest failing
   test before changing behavior when practical.
4. Check the working tree. Preserve unrelated changes. Start from current `main`
   and create a focused `codex/<issue>-<slug>` branch.
5. State any manual or unavailable platform gate early. Do not pretend local macOS
   testing proves Windows behavior or the reverse.

## Implement the smallest complete fix

- Correct the root cause, not just its visible symptom.
- Keep platform behavior isolated with Tauri/Rust target conditions or narrowly
  scoped runtime checks. Preserve the other platform's established appearance.
- Keep clipboard text and generated speech local. Treat new model engines as
  removable, opt-in packs unless the issue explicitly changes that decision.
- Add regression coverage at the lowest useful layer: Vitest for UI/planning,
  Python unittest for the sidecar, and Rust tests for commands/window lifecycle.
- Update user-facing docs or changelog only when behavior or release instructions
  changed. Do not mix a version bump into a feature PR.
- Use `apply_patch` for intentional edits and review `git diff` before testing.

## Verify locally

Run:

```bash
python3 .codex/skills/kokoro-issue-to-release/scripts/verify.py
```

The command mirrors CI: native Sonic build/tests, Python suites, frontend tests and
build, Rust formatting and tests, and whitespace checks. Use `--quick` only during
iteration; the final PR requires the full command.

For visual, audio, updater, installation, or platform-specific work, also execute
the applicable manual cases in `RELEASE_TESTING.md`. Record exactly what was and
was not exercised in the PR.

## Publish and review

1. Inspect the final diff and `git status`; commit only files belonging to the issue.
2. Push the branch and open a draft PR whose body contains:
   - `Fixes #<number>` when merging should close the issue;
   - the root cause and solution;
   - automated test evidence;
   - manual/platform test evidence and remaining risk.
3. Monitor checks without noisy polling. If CI fails, read the failing logs, fix the
   cause, rerun the local gate, and update the same PR.
4. Keep visual or platform-specific PRs in draft until their manual gate is met.
5. Resolve review feedback and require all CI matrix jobs to pass. Merge only when
   the user has authorized shipping/merging and the acceptance criteria are met.

## Release separately

Functional changes merge before release plumbing. Unless the user explicitly asks
for a release, stop after the ready PR or merge.

1. Choose the smallest correct semantic version and create a release-only branch.
2. Update every version location listed in `references/repo-map.md` and add a dated
   `CHANGELOG.md` entry.
3. Run the pre-tag gate and full verification:

```bash
python3 .codex/skills/kokoro-issue-to-release/scripts/release_gate.py 0.0.0
python3 .codex/skills/kokoro-issue-to-release/scripts/verify.py
```

4. Publish, pass CI, and merge the release PR. Pull the resulting `main` commit.
5. Create and push the annotated tag `v0.0.0`. Do not manually create a competing
   GitHub release: `.github/workflows/release.yml` owns build and publication.
6. Wait for the Release workflow once, using event-driven or bounded waits. Fix the
   workflow and retag only with explicit care if it fails; never hide a failed run.
7. Confirm the release is public (not draft), then run:

```bash
python3 .codex/skills/kokoro-issue-to-release/scripts/release_gate.py 0.0.0 --published
```

8. Smoke-test the in-app updater from the previous public version when updater code
   or packaging changed. Only then report the release as shipped.

## Stop conditions

Stop and report evidence instead of widening scope when acceptance requires
hardware or a platform unavailable to you, a license/privacy decision, signing
secrets, destructive data changes, or a materially different product direction.
