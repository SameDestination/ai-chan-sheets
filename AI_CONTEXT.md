# AI context — standalone local controller

Reviewed 2026-10-28. Scope: the added `local_app/` controller and local lifecycle scripts; original upstream scripts are retained unchanged.

- `local_app/core.py`: persisted manifests, character-specific prompts, reference/dependency validation, explicit subscription handoffs, immutable versions/review records and stale approval gates.
- `local_app/safety.py`: managed paths, bounded image decoding, atomic files and hashes.
- `local_app/server.py` / `web/`: loopback HTTP, origin/CSRF protections, Chinese workflow UI.
- `local_app/pixels.py`: native-pixel composition plus separate disk verifier. Selected versions are authoritative; no skip counts as success.
- `local_app/lifecycle.py`, root `*-CharacterSheets.*`: app-only install/start/stop/diagnostics. No services, global environment changes or production integration.
- `local_app/example.py` / `test_*.py`: deterministic synthetic fixtures, never evidence of live generation or artistic approval.

Read [LOCAL_README.zh-CN.md](LOCAL_README.zh-CN.md), [CAPABILITY_AUDIT.md](CAPABILITY_AUDIT.md), [UPSTREAM_COMPATIBILITY.md](UPSTREAM_COMPATIBILITY.md), [NOTICE.local.md](NOTICE.local.md) and [LOCAL_VALIDATION.md](LOCAL_VALIDATION.md) as relevant.

Deliberate decisions (2026-10-27): Mode B has no outbound generation adapter because exposed interactive tools do not prove supported standalone subscription invocation or remaining included allowance. Request state is reserved before handoff instructions can escape; a crash therefore conservatively pauses with unknown outcome. Original generation records and subsequent review records are separate immutable files. All plan edits conservatively invalidate the whole plan; fine-grained invalidation can be added without relaxing current gates. These decisions prevent duplicate consumption, fabricated provenance and stale assets entering final output.

Per-attempt corrections (2026-10-28): a handoff may append an immutable correction to that attempt's exact tool prompt while retaining its canonical base prompt and plan fingerprint. This repairs one execution result without redefining the approved design or invalidating unrelated approvals. Only the corrected task selection, its transitive dependents and current export are invalidated; reference/profile/canonical-prompt edits still invalidate the whole plan. Regression tests in `test_core.py` cover immutable v01/v02 prompts, unrelated selections, dependency invalidation, HTTP forwarding and unchanged approval/quota gates. Human review is still required for the corrected result.
