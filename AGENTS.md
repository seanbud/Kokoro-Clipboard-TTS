# Repository agent guide

Use the repo-local `kokoro-issue-to-release` skill for any request that starts
from a GitHub issue or is expected to end in a pull request or release:

`.codex/skills/kokoro-issue-to-release/SKILL.md`

## Non-negotiable project rules

- Keep Kokoro Clipboard TTS private and offline by default. Do not add telemetry,
  cloud APIs, or network speech processing without an explicit product decision.
- Preserve unrelated working-tree changes. Never discard user work.
- Create focused branches with the `codex/` prefix and focused commits.
- Diagnose before editing. Turn the issue into observable acceptance criteria and
  add a regression test whenever the behavior can be automated.
- Scope platform-specific UI and window changes explicitly. A Windows fix must
  not alter macOS behavior unless the issue requires it, and vice versa.
- Keep the bundled core installer and default Kokoro experience working when
  experimenting with optional engines.
- Run the repo verification script before publishing a pull request:
  `python3 .codex/skills/kokoro-issue-to-release/scripts/verify.py`.
- Never claim a release is shipped until the public GitHub release and signed
  updater metadata have passed the post-release gate.

Human setup and release documentation lives in `.agent/CONTRIBUTING.md`.
