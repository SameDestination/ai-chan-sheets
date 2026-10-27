"""Offline launcher guards, including Windows venv parent/child PID behavior."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import lifecycle


class LifecycleTests(unittest.TestCase):
    def test_runtime_url_cannot_send_stop_token_elsewhere(self):
        for url in ("https://127.0.0.1:1000", "http://evil.example:1000", "http://127.0.0.1:1000/path", "http://user:secret@127.0.0.1:1000", "http://127.0.0.1:1000/?token=x"):
            with self.assertRaises(RuntimeError):
                lifecycle.local_url({"url": url, "port": 1000})

    def test_identity_mismatch_never_reuses_or_stops_process(self):
        record = {"url": "http://127.0.0.1:12345", "port": 12345, "pid": 42, "instance_id": "a"}
        with patch.object(lifecycle, "request", return_value={"app": lifecycle.APP, "pid": 42, "instance_id": "other"}):
            with self.assertRaises(RuntimeError):
                lifecycle.matching_health(record)

    def test_new_server_pid_may_differ_from_venv_redirector(self):
        with tempfile.TemporaryDirectory(prefix="角色 launcher ") as temp:
            runtime = Path(temp) / "runtime.json"
            expected = "e" * 32
            actual = {"url": "http://127.0.0.1:12345", "port": 12345, "pid": 222, "instance_id": expected}
            class Process:
                pid = 111
                def poll(self):
                    return None
            class UID:
                hex = expected
            with patch.object(lifecycle, "read_runtime", side_effect=[None, actual]), \
                 patch.object(lifecycle, "matching_health", return_value=True), \
                 patch.object(lifecycle.subprocess, "Popen", return_value=Process()) as popen, \
                 patch.object(lifecycle.uuid, "uuid4", return_value=UID()):
                result = lifecycle.start(runtime, Path(temp) / "数据 空间", False)
            self.assertEqual(result["status"], "started")
            self.assertEqual(result["pid"], 222)
            self.assertIn(expected, popen.call_args[0][0])

    def test_default_does_not_redirect_to_cloud_documents(self):
        self.assertEqual(lifecycle.data_directory(), Path.home() / "Documents" / "CharacterSheets")


if __name__ == "__main__":
    unittest.main()
