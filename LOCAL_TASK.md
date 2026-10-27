# Local character-sheet controller

- Owner: Codex; implementation worktree: feature branch `feat/subscription-local-workflow`.
- Scope: standalone Python/Pillow local application, Windows installation, Chinese browser UI, persistent per-asset subscription-only handoff, human review, native-pixel composition and independent verification.
- Baseline: lmy414/ai-chan-sheets `51c15559ac7ebc6bbfb22e1769ba46716f976d5d`, rechecked 2026-10-27. Preserve upstream license and attribution.
- Isolation: no Gwen source/runtime/configuration changes. Separate worktrees for delegated implementation. No generation API, OAuth extraction, purchased credits, upstream push, force push, or personal artwork in commits.
- Tests: deterministic complete 22-task RGB/RGBA fixtures; validation/dependencies/approval/staleness/restart/error states; negative integrity mutations; localhost/security; launcher/restart and rendered UI inspection.
- Authorized publication: selected source/docs/tests only to SameDestination/ai-chan-sheets feature branch and PR against that fork's main. User's explicit request supersedes attachment's no-push text.
- Unresolved: no authoritative remaining included allowance available; live calls blocked. Built-in tool is exposed in this interactive session. Elevated read-only `codex login status` reports ChatGPT login; no credentials read.

Implementation and test evidence will be recorded in LOCAL_VALIDATION.md and the handoff.
