# Local validation evidence

Date: 2026-10-27 (Asia/Shanghai). Windows, Python 3.12.0, isolated Pillow 12.2.0. Upstream revision `51c15559ac7ebc6bbfb22e1769ba46716f976d5d`.

## Offline automated checks

Command: `.venv\Scripts\python.exe -m unittest discover -s local_app -t . -p "test_*.py" -v`.

- 18 controller/HTTP/integration regressions: manifest/character-specific prompt validation, dependency cycles and selected reference resolution, actual-dimension approval gate, immutable original/prompt/review records, v01/v02 selection, stale dependencies, crops and rejected parents, serial billing preflight, request limits, restart/unknown outcome, explicit retries/cancellation, failure classes, interrupted import reconciliation, crash-safe handoff reservation, upstream prompt import, self-contained compatibility archive, managed paths and localhost Host/Origin/CSRF protections.
- 40 native-pixel regressions: complete 22-task RGB/RGBA fixtures in Chinese/space paths; original pixels and alpha-over-white; four native slices; preview bounds/no upscaling; selected v02; missing/empty/omitted/extra/duplicate/stale/substituted records and placements; wrong group/hash/dimensions/master/index; scaling, overlaps, bounds; modified master/slice pixels; missing font and memory-budget failure. Fixture assets cannot impersonate production artwork.
- 4 lifecycle regressions: stop-token URL restrictions, server identity mismatch, Windows venv redirector/server PID differences, exact local Documents default.
- JavaScript syntax, Python compilation, PowerShell parser/ASCII checks and `git diff --check` pass.

The 58 controller/pixel tests passed from the installed application. Four lifecycle tests subsequently passed after the Windows launch fix. The final combined run passed **62/62** tests in 32.811 seconds, with zero failures or skips. There are no live network/generation tests in this suite. Mocked 401/403/429/503/timeouts validate local failure policy, not a network connector; Mode B has no automatic network generator.

## Installation and launch validation

- Installed at `%USERPROFILE%\ai-chan-sheets-local`; project root `%USERPROFILE%\Documents\CharacterSheets`. Existing files are preserved and replaced source files are backed up by the installer. No production Gwen files, services or configuration were changed.
- Start invoked from an unrelated current directory: successful. A second start returns `already_running` with the same server instance and URL.
- Safe stop uses verified loopback instance identity and the local shutdown token. HTTP listener closure confirmed; restart uses a new instance. No process-name kill is used.
- First startup exposed the Windows venv launcher/worker PID split. Corrected to authenticate the per-launch instance ID; dedicated regression added. Restart and saved-project verification pass.
- A separate installation/data path containing Chinese characters and spaces was used for start/stop validation. No user data was copied into that test installation.

## Rendered UI and board

No browser was connected to the computer-use tool, so rendering used installed Chrome in headless test mode with fresh isolated profiles and only the loopback URL. All seven routes rendered: overview, references/analysis, manifest, queue/handoff, review/contact sheet, composition/exports and capability diagnostics. Every page reported connected; no broken image marker appeared. Screenshots were visually inspected for overview, side-by-side review, export controls and diagnostics. Chinese headings and text were readable without clipping. The export defaults match the compositor's supported option names.

Screenshots/DOM snapshots are local under `%TEMP%\character-sheets-ui-qa`, not committed. UI assets use no remote libraries, fonts, analytics or provider calls.

An explicitly labeled local example contains 22 deterministic geometric RGB/RGBA images (`offline_fixture`), not AI-generated art. Its saved master is 3175×1984 (ratio approximately 1.6003), source scale 1.0. Independent reopen verified **22/22** asset pixel regions and **4/4** native slices. Example exports live beneath the example project's `exports/v001/`: `master.png`, `browse.jpg`, `overview.jpg`, four `section-NN-native.png`, four `section-NN-preview.jpg`, `layout.json`, `report.json`. The example title and UI banner explicitly deny artwork approval. Small fixtures are never upscaled to meet a preview target.

## Live capability and status

| Status | Evidence |
| --- | --- |
| INSTALLED | Isolated dependency installed, local service healthy, launch/stop/restart verified |
| OFFLINE-TESTED | Automated deterministic suites and rendered local application/sample board |
| SUBSCRIPTION-IMAGEGEN-VERIFIED | **NOT VERIFIED / BLOCKED**: current remaining included allowance and per-image funding unavailable |
| STANDALONE-AUTOMATION-VERIFIED | **NOT VERIFIED**: Mode B has no automatic subscription invocation adapter |
| ARTWORK-APPROVED | **No**: no user character assets generated or visually approved |

Actual live image requests: **0**. Actual subscription vision/planning requests: **0**. Paid Image/Responses API calls, API-key runners, purchased-credit consumption and provider substitutions: **0**. Image model observed from an execution: `unreported`.

ChatGPT sign-in was confirmed by the official CLI's read-only login status. Tool presence/reference/edit schema was observed in the installing session; neither proves funding, returned output or reference conditioning. See [CAPABILITY_AUDIT.md](CAPABILITY_AUDIT.md). The unresolved live prerequisites are explicit and do not prevent using project management, review, composition or exports after this Codex session.

## Software follow-up checks — 2026-10-28

Per-attempt correction support now preserves the approved canonical design and unrelated selections while retaining the exact immutable corrected prompt. Target and dependent selections require review again. The combined offline suite passed **66/66** tests in 38.148 seconds, including HTTP forwarding and unchanged billing/approval gates. This supersedes the earlier 62-test software count without rewriting the historical installation audit.

Diagnostics can display an explicit, timestamped project `execution_summary` separately from that installation audit. JavaScript syntax and render smoke checks passed: an ordinary imported file does not imply billing, reference conditioning, automation or artwork approval, while explicit project evidence displays its own timestamp, provenance and call counts. Session artwork and account usage evidence remain local project data and are not committed with application code.
