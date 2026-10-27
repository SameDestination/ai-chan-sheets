# Local controller handoff

Owner: Codex. Date: 2026-10-27 (Asia/Shanghai). Dedicated integration branch: `feat/subscription-local-workflow`.

Implemented and installed the standalone controller described in [LOCAL_README.zh-CN.md](LOCAL_README.zh-CN.md). The upstream scripts, license and attribution remain identifiable and preserved. Stage-by-stage mapping and reproduced upstream bugs are documented in [UPSTREAM_COMPATIBILITY.md](UPSTREAM_COMPATIBILITY.md). Only selected application source, tests, launchers and documentation are authorized for the user's fork; no user project, generated asset, credential, configuration, venv or local runtime record is part of the publication.

Application: `%USERPROFILE%\ai-chan-sheets-local`. Data: `%USERPROFILE%\Documents\CharacterSheets`. Start: `Start-CharacterSheets.cmd`; stop: `Stop-CharacterSheets.cmd`; diagnosis: `Diagnose-CharacterSheets.cmd`. The launcher reports the current loopback URL. It does not create services or startup tasks. Installation preserves existing files and keeps replacement backups. A temporary test installation in a Chinese/space path is stopped; its data contains no user assets.

The example is clearly labeled `offline_fixture`, with a verified 22-item native master and four native slices. Local screenshots and sample exports are deliberately excluded from Git. Pixel verification is not artistic approval.

Review: a second agent read the controller/security diff and identified serial-slot, prompt-history, interrupted-import and compatibility-export issues. Each was fixed and regression-tested. Final independent read-only review approved source publication with no remaining high/medium findings or privacy findings. Parallel implementations used separate branches/worktrees; integration and installation had one writer. Final combined suite: **62/62 passed**, zero failures/skips; seven UI screens rendered, Chinese/space-path install/start/stop passed. See [LOCAL_VALIDATION.md](LOCAL_VALIDATION.md) for evidence.

Deployment status: **standalone application installed locally; Gwen production unchanged**. This repository does not transfer or restart Gwen services. Publishing is limited to `SameDestination/ai-chan-sheets` and a PR targeting that fork's `main`; no upstream push, tags, force push or merge is authorized.

Publication verified: implementation commit `d02d84f96e5261d2bfe1a9180c8e0ea8dc2551fd` reached the authorized fork branch. [PR #1](https://github.com/SameDestination/ai-chan-sheets/pull/1) is open, with both head and base repositories verified as the user's fork and base branch `main`. The GitHub connector denied PR creation; the already authenticated official GitHub CLI completed it. No upstream remote was configured or pushed. The final chat reports the branch's final head SHA, including this handoff record.

Unresolved prerequisites: current included subscription allowance/funding and actual reference-conditioned generation remain unverified. The exposed interactive tool and ChatGPT login do not establish standalone automation. Live image and vision requests performed: zero. No paid fallback exists. Mode B exports one exact task and real reference assignments for the already authenticated interactive Codex/ChatGPT operator, then imports the genuine file with honest provenance.

User decisions still required for real artwork: choose/import licensed references; complete character facts and supported clothing/detail counts; approve the versioned manifest; verify included allowance/funding before each single request; inspect and approve each actual image/settings gap; explicitly select accepted versions. Do not start a full 22-image run without separate authorization.
