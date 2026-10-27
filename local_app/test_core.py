"""Offline lifecycle, approval, provenance and browser-origin regression tests."""
import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .core import Store, classify_failure
from .example import fixture, prepared_project
from .safety import image_info, managed, read_json
from .server import Server


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="角色 Sheets 空间 ")
        self.store = Store(Path(self.tmp.name) / "项目 数据")
        self.m = prepared_project(self.store)
        self.pid = self.m["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def dispatch(self, tid="A01"):
        self.store.enqueue(self.pid, [tid])
        self.store.queue_control(self.pid, "resume")
        return self.store.handoff(self.pid, tid, "OFFLINE TEST: mocked included allowance evidence", True)

    def import_fixture(self, tid="A01", index=1):
        self.dispatch(tid)
        # Explicitly mocked input; this test is not live capability evidence.
        return self.store.import_image(self.pid, tid, fixture(index, (120, 200), True), "codex_builtin",
                                       "OFFLINE MOCK only; no subscription claim", "mocked-tool-output.png")

    def test_manifest_gate_and_character_specific_validation(self):
        raw = self.store.create("角色 新工程")
        with self.assertRaises(ValueError):
            self.store.approve_plan(raw["id"])
        tasks = copy.deepcopy(self.m["tasks"])
        tasks[0]["filename"] = "../escape.png"
        with self.assertRaises(ValueError):
            self.store.plan(self.pid, self.m["profile"], tasks)
        tasks = copy.deepcopy(self.m["tasks"])
        tasks[0]["id"] = tasks[1]["id"]
        with self.assertRaises(ValueError):
            self.store.plan(self.pid, self.m["profile"], tasks)
        tasks = copy.deepcopy(self.m["tasks"])
        tasks[0]["depends_on"] = ["A02"]
        tasks[1]["refs"] = ["@A01"]
        with self.assertRaisesRegex(ValueError, "循环"):
            self.store.plan(self.pid, self.m["profile"], tasks)

    def test_prompt_is_character_specific_and_complete(self):
        prompt = self.store.prompt(self.m, "A02")
        self.assertEqual(set(("id", "group", "model", "quality", "size", "refs", "prompt")) - set(prompt), set())
        self.assertIn("画面左方", prompt["prompt"])
        self.assertNotIn("猫耳", prompt["prompt"])
        self.assertIn("纯白背景", prompt["prompt"])
        self.assertIn("unknown", prompt["prompt"])

    def test_billing_pause_serial_and_request_limit_gates(self):
        self.store.enqueue(self.pid, ["A01", "A02"])
        with self.assertRaisesRegex(ValueError, "暂停"):
            self.store.handoff(self.pid, "A01", "enough mock evidence", True)
        self.store.queue_control(self.pid, "resume")
        with self.assertRaisesRegex(ValueError, "额度"):
            self.store.handoff(self.pid, "A01")
        with self.assertRaisesRegex(ValueError, "顺序"):
            self.store.handoff(self.pid, "A02", "enough mock evidence", True)
        result = self.store.handoff(self.pid, "A01", "enough mock evidence", True)
        self.assertIn("真实图像", result["instruction"])
        with self.assertRaisesRegex(ValueError, "一次"):
            self.store.handoff(self.pid, "A02", "enough mock evidence", True)
        self.assertEqual(self.store.get(self.pid)["requests_dispatched"], 1)

    def test_invalid_image_is_not_success_and_import_is_immutable(self):
        self.dispatch()
        with self.assertRaises(Exception):
            self.store.import_image(self.pid, "A01", b"not an image", "codex_builtin", "mock evidence", "fake.png")
        self.assertEqual(self.store.get(self.pid)["attempts"], {})
        m = self.store.import_image(self.pid, "A01", fixture(1, (120, 200)), "manual_chatgpt_import", "mock evidence", "fake.png")
        record = m["attempts"]["A01"][0]
        original = (self.store.path(self.pid) / record["record_file"]).read_bytes()
        self.store.review(self.pid, "A01", 1, "approved", "offline fixture review")
        self.assertEqual((self.store.path(self.pid) / record["record_file"]).read_bytes(), original)
        with self.assertRaises(ValueError):
            self.store.import_image(self.pid, "A01", fixture(2), "codex_builtin", "mock evidence", "fake.png")

    def test_version_selection_staleness_and_settings_gap(self):
        self.import_fixture()
        self.store.review(self.pid, "A01", 1, "approved", "mock")
        self.import_fixture(index=2)
        self.store.review(self.pid, "A01", 2, "approved", "mock")
        m = self.store.select(self.pid, "A01", 1)
        self.assertEqual(self.store.selected_record(m, "A01")["version"], 1)
        self.store.edit_prompt(self.pid, "A01", "fix one detail")
        m = self.store.get(self.pid)
        self.assertIsNone(m["approved_revision"])
        self.assertEqual(m["selections"], {})
        self.assertEqual(len(m["attempts"]["A01"]), 2)
        self.assertTrue((self.store.path(self.pid) / "prompt_history/A01_v01.json").is_file())

    def test_reference_crop_parent_rejection_invalidates(self):
        reference = self.m["references"][0]
        m = self.store.crop(self.pid, reference["id"], [0, 0, 20, 30], "single view crop")
        crop = m["references"][-1]
        self.assertEqual(crop["parent_sha256"], reference["sha256"])
        self.assertEqual(crop["crop_box"], [0, 0, 20, 30])
        m = self.store.reject_reference(self.pid, reference["id"])
        self.assertTrue(all(r["rejected"] for r in m["references"]))
        with self.assertRaises(ValueError):
            self.store.approve_plan(self.pid)

    def test_dependency_requires_selected_current_source(self):
        tasks = copy.deepcopy(self.m["tasks"])
        tasks[1]["refs"] = ["@A01"]
        m = self.store.plan(self.pid, self.m["profile"], tasks)
        self.store.approve_plan(self.pid)
        with self.assertRaises(ValueError):
            self.store.resolve_refs(m, "A02")
        self.import_fixture()
        self.store.review(self.pid, "A01", 1, "approved", "mock")
        self.import_fixture("A02", index=2)
        self.store.review(self.pid, "A02", 1, "approved", "mock")
        m = self.store.review(self.pid, "A01", 1, "rejected", "changed choice")
        self.assertNotIn("A02", m["selections"])
        self.assertEqual(m["task_status"]["A02"], "stale")

    def test_actual_dimensions_require_explicit_gap_acceptance(self):
        self.dispatch()
        self.store.import_image(self.pid, "A01", fixture(7, (80, 80)), "codex_builtin", "offline mock evidence", "mock.png")
        with self.assertRaisesRegex(ValueError, "差异"):
            self.store.review(self.pid, "A01", 1, "approved")
        m = self.store.review(self.pid, "A01", 1, "approved", accept_settings_gap=True)
        self.assertEqual(m["attempts"]["A01"][0]["dimensions"], [80, 80])

    def test_restart_timeout_cancel_and_explicit_reconciliation(self):
        self.dispatch()
        self.store.recover()
        m = self.store.get(self.pid)
        self.assertEqual(m["task_status"]["A01"], "outcome_unknown")
        with self.assertRaises(ValueError):
            self.store.enqueue(self.pid, ["A01"])
        self.store.enqueue(self.pid, ["A02"])
        self.store.queue_control(self.pid, "resume")
        with self.assertRaisesRegex(ValueError, "未知结果"):
            self.store.handoff(self.pid, "A02", "offline mock evidence", True)
        self.store.resolve_unknown(self.pid, "A01", "retry_explicitly")
        self.store.queue_control(self.pid, "resume")
        result = self.store.handoff(self.pid, "A01", "offline mock evidence", True)
        self.assertEqual(result["version"], 2)
        m = self.store.queue_control(self.pid, "cancel")
        self.assertEqual(m["task_status"]["A01"], "outcome_unknown")
        self.assertEqual(m["requests_dispatched"], 2)

    def test_wrong_task_failure_cannot_release_serial_slot(self):
        self.dispatch()
        self.store.enqueue(self.pid, ["A02"])
        with self.assertRaises(ValueError):
            self.store.report_failure(self.pid, "A02", "503")
        self.assertEqual(self.store.get(self.pid)["queue"]["active"], "A01")

    def test_correction_preserves_all_prompt_revisions(self):
        before = self.store.path(self.pid) / f"prompt_revisions/r{self.m['revision']:04}/A01.json"
        original = before.read_bytes()
        self.store.edit_prompt(self.pid, "A01", "an explicit local correction")
        self.assertEqual(before.read_bytes(), original)
        self.assertNotEqual(before.read_bytes(), (self.store.path(self.pid) / "00_提示词/A01.json").read_bytes())

    def test_interrupted_import_reconciles_without_overwriting(self):
        from unittest.mock import patch
        self.dispatch()
        data = fixture(18, (120, 200))
        with patch.object(self.store, "save", side_effect=OSError("simulated crash after atomic files")):
            with self.assertRaises(OSError):
                self.store.import_image(self.pid, "A01", data, "codex_builtin", "offline mock evidence", "mock.png")
        self.store.recover()
        m = self.store.import_image(self.pid, "A01", data, "codex_builtin", "offline mock evidence", "mock.png")
        self.assertEqual(len(m["attempts"]["A01"]), 1)
        self.assertEqual(m["task_status"]["A01"], "awaiting_review")

    def test_crash_during_handoff_never_undercounts_or_reuses_version(self):
        from unittest.mock import patch
        from . import core
        real_write = core.write_json
        def fail_event(path, *args, **kwargs):
            if Path(path).parent.name == "handoffs":
                raise OSError("simulated crash before instruction delivery")
            return real_write(path, *args, **kwargs)
        self.store.enqueue(self.pid, ["A01"])
        self.store.queue_control(self.pid, "resume")
        with patch.object(core, "write_json", side_effect=fail_event):
            with self.assertRaises(OSError):
                self.store.handoff(self.pid, "A01", "offline mock evidence", True)
        self.store.recover()
        m = self.store.get(self.pid)
        self.assertEqual(m["requests_dispatched"], 1)
        self.assertEqual(m["task_status"]["A01"], "outcome_unknown")
        self.store.resolve_unknown(self.pid, "A01", "retry_explicitly")
        self.store.queue_control(self.pid, "resume")
        result = self.store.handoff(self.pid, "A01", "offline mock evidence", True)
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["manifest"]["requests_dispatched"], 2)

    def test_upstream_prompt_import_normalizes_registered_refs_only(self):
        p = self.store.prompt(self.m, "A01")
        p["refs"] = ["archive\\reference\\fixture.png"]
        p["model"] = "upstream-model-name-not-executed"
        m = self.store.import_prompts(self.pid, [p], "提示词")
        self.assertEqual(m["tasks"][0]["refs"], [m["references"][0]["id"]])
        self.assertEqual(m["tasks"][0]["model"], "unreported")
        self.assertIsNone(m["approved_revision"])
        p["refs"] = ["../fixture.png"]
        with self.assertRaises(ValueError):
            self.store.import_prompts(self.pid, [p])

    def test_full_controller_to_verifier_and_self_contained_upstream_export(self):
        import zipfile
        from .example import create_example
        m = create_example(self.store)
        result = self.store.compose(m["id"])
        self.assertTrue(result["export"]["verified"])
        report = self.store.verify(m["id"])["report"]
        self.assertEqual(report["byte_match"], 22)
        self.assertEqual(report["native_slices_verified"], 4)
        exported = self.store.export_upstream(m["id"])
        with zipfile.ZipFile(self.store.path(m["id"]) / exported["file"]) as bundle:
            archive_manifest = json.loads(bundle.read("制作清单.json"))
            self.assertEqual(len(archive_manifest["tasks"]), 22)
            for tid in archive_manifest["tasks"]:
                stem = archive_manifest["selections"][tid]
                rec = json.loads(bundle.read(f"00_生成记录/{stem}.json"))
                self.assertIn(rec["output"], bundle.namelist())
                self.assertIn(f"00_提示词/{stem}.json", bundle.namelist())
            self.assertNotIn(".env", bundle.namelist())
            self.assertFalse(any(".runtime" in p for p in bundle.namelist()))

    def test_failures_and_bounded_retry_policy(self):
        for kind in ("401", "403", "missing_credentials", "quota_exhausted", "invalid_image", "incompatible_request"):
            self.assertFalse(classify_failure(kind)["retryable"])
            self.assertTrue(classify_failure(kind)["pause"])
        self.assertTrue(classify_failure("429", 1, 17)["retryable"])
        self.assertEqual(classify_failure("429", 1, 17)["delay"], 17)
        self.assertFalse(classify_failure("503", 3)["retryable"])
        self.assertEqual(classify_failure("timeout")["state"], "outcome_unknown")
        self.dispatch()
        self.store.report_failure(self.pid, "A01", "503")
        m = self.store.get(self.pid)
        self.assertTrue(m["queue"]["paused"])
        self.assertEqual(m["task_status"]["A01"], "failed")

    def test_path_restrictions_and_missing_project(self):
        for path in ("../a", "C:/secret", "/etc/x", "a\\..\\secret", "references/../x", "a//x"):
            with self.assertRaises(ValueError, msg=path):
                managed(self.store.path(self.pid), path)
        with self.assertRaises(Exception):
            self.store.get("p-does-not-exist")


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = Server(self.tmp.name)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.url = self.server.url

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        self.tmp.cleanup()

    def request(self, path, data=None, headers=None):
        hdr = headers or {}
        if data is not None:
            hdr = {"Content-Type": "application/json", **hdr}
        request = Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, headers=hdr)
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
            return json.loads(response.read())

    def test_localhost_origin_csrf_and_file_traversal(self):
        status = self.request("/api/status")
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for headers in ({}, {"Origin": "https://evil.example", "X-CSRF-Token": status["csrf_token"]},
                        {"Host": "evil.example", "X-CSRF-Token": status["csrf_token"]}):
            with self.assertRaises(HTTPError):
                self.request("/api/create", {"name": "test"}, headers)
        m = self.request("/api/create", {"name": "角色 空格"}, {"X-CSRF-Token": status["csrf_token"]})
        self.assertEqual(m["name"], "角色 空格")
        with self.assertRaises(HTTPError):
            self.request(f"/file?project={m['id']}&path=../secret")
        health = self.request("/health")
        self.assertNotIn("stop_token", health)
        self.assertEqual(health["instance_id"], self.server.instance_id)


if __name__ == "__main__":
    unittest.main()
