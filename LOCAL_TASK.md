# Local character-sheet controller

- Owner: Codex; implementation worktree: feature branch `feat/subscription-local-workflow`.
- Scope: standalone Python/Pillow local application, Windows installation, Chinese browser UI, persistent per-asset subscription-only handoff, human review, native-pixel composition and independent verification.
- Baseline: lmy414/ai-chan-sheets `51c15559ac7ebc6bbfb22e1769ba46716f976d5d`, rechecked 2026-10-27. Preserve upstream license and attribution.
- Isolation: no Gwen source/runtime/configuration changes. Separate worktrees for delegated implementation. No generation API, OAuth extraction, purchased credits, upstream push, force push, or personal artwork in commits.
- Tests: deterministic complete 22-task RGB/RGBA fixtures; validation/dependencies/approval/staleness/restart/error states; negative integrity mutations; localhost/security; launcher/restart and rendered UI inspection.
- Authorized publication: selected source/docs/tests only to SameDestination/ai-chan-sheets feature branch and PR against that fork's main. User's explicit request supersedes attachment's no-push text.
- Unresolved: no authoritative remaining included allowance available; live calls blocked. Built-in tool is exposed in this interactive session. Elevated read-only `codex login status` reports ChatGPT login; no credentials read.

Implementation and test evidence will be recorded in LOCAL_VALIDATION.md and the handoff.

## Per-attempt correction fix — 2026-10-28

- Owner: Codex controller-review agent; branch `fix/per-attempt-correction`, isolated worktree based on integration commit `4fa55a8`.
- Scope: optional bounded correction on a single handoff, exact immutable attempt/base prompts, selective target/dependency invalidation, HTTP/UI input, documentation and offline regression tests.
- Constraints: preserve approved character design and unrelated asset approvals; no installed-app/user-data writes, production changes or image-generation calls. Canonical plan edits retain full invalidation and all subscription/serial limits remain enforced.
- Tests: controller regression suite including v01/v02 preservation, dependencies, unrelated selections, invalid inputs, approval/quota gates and HTTP correction forwarding; JavaScript syntax check.
- Validation: `python -m unittest local_app.test_core -v` passed all 22 tests (27.665s); `node --check local_app/web/app.js` and `git diff --check` passed. No live generation calls or installed/user-data changes. Root agent integration review requested separately.

Review complete: the read-only reviewer approved source publication after the serial-slot, prompt-history,
crash-reservation, interrupted-import and self-contained compatibility-export fixes. No remaining high/medium
findings or staged credential/private-asset findings. Separate UI and native-pixel branches were integrated
without sharing implementation writers. Real image/vision calls remain zero; live capability remains blocked.
