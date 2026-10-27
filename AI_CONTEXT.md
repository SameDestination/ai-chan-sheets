# AI context — standalone local controller

Reviewed 2026-10-27. Scope: the added `local_app/` controller and local lifecycle scripts; original upstream scripts are retained unchanged.

- `local_app/core.py`: persisted manifests, character-specific prompts, reference/dependency validation, explicit subscription handoffs, immutable versions/review records and stale approval gates.
- `local_app/safety.py`: managed paths, bounded image decoding, atomic files and hashes.
- `local_app/server.py` / `web/`: loopback HTTP, origin/CSRF protections, Chinese workflow UI.
- `local_app/pixels.py`: native-pixel composition plus separate disk verifier. Selected versions are authoritative; no skip counts as success.
- `local_app/lifecycle.py`, root `*-CharacterSheets.*`: app-only install/start/stop/diagnostics. No services, global environment changes or production integration.
- `local_app/example.py` / `test_*.py`: deterministic synthetic fixtures, never evidence of live generation or artistic approval.

Read [LOCAL_README.zh-CN.md](LOCAL_README.zh-CN.md), [CAPABILITY_AUDIT.md](CAPABILITY_AUDIT.md), [UPSTREAM_COMPATIBILITY.md](UPSTREAM_COMPATIBILITY.md), [NOTICE.local.md](NOTICE.local.md) and [LOCAL_VALIDATION.md](LOCAL_VALIDATION.md) as relevant.

Deliberate decisions (2026-10-27): Mode B has no outbound generation adapter because exposed interactive tools do not prove supported standalone subscription invocation or remaining included allowance. Request state is reserved before handoff instructions can escape; a crash therefore conservatively pauses with unknown outcome. Original generation records and subsequent review records are separate immutable files. All plan edits conservatively invalidate the whole plan; fine-grained invalidation can be added without relaxing current gates. These decisions prevent duplicate consumption, fabricated provenance and stale assets entering final output.
