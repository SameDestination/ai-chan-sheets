"""Local-only Windows-friendly lifecycle; never kill processes by name or PID."""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

APP = "character-sheets-local"
APP_ROOT = Path(__file__).resolve().parent.parent
RUNTIME = APP_ROOT / ".runtime" / "server.json"


def documents_directory() -> Path:
    if os.name == "nt":
        buffer = ctypes.create_unicode_buffer(32768)
        # CSIDL_PERSONAL honors a relocated Documents folder.
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            return Path(buffer.value)
    return Path.home() / "Documents"


def data_directory() -> Path:
    return documents_directory() / "CharacterSheets"


def read_runtime(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise RuntimeError("Unreadable runtime file; inspect it before starting: " + str(path)) from exc
    if not isinstance(value, dict):
        raise RuntimeError("Invalid runtime file: " + str(path))
    return value


def local_url(record: dict) -> str:
    url = str(record.get("url", "")).rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path not in ("", "/"):
        raise RuntimeError("Refusing a non-loopback or invalid runtime URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("Invalid runtime URL")
    if parsed.port != int(record.get("port", 0)) or not (1 <= parsed.port <= 65535):
        raise RuntimeError("Invalid runtime port")
    return url


def request(url: str, token: str | None = None) -> dict:
    # Disable environment proxies: localhost lifecycle must never leave the machine.
    headers = {"Accept": "application/json"}
    body = None
    if token is not None:
        body = b"{}"
        headers.update({"Content-Type": "application/json", "X-CSRF-Token": token,
                        "Origin": url.rsplit("/api/shutdown", 1)[0]})
    req = urllib.request.Request(url, data=body, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=2) as response:
        raw = response.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise RuntimeError("Unexpected lifecycle response size")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise RuntimeError("Unexpected lifecycle response")
        return value


def matching_health(record: dict) -> bool:
    url = local_url(record)
    try:
        health = request(url + "/health")
    except (OSError, ValueError, urllib.error.URLError):
        return False
    if health.get("app") != APP or str(health.get("pid")) != str(record.get("pid")):
        raise RuntimeError("The runtime port belongs to a different application; refusing to reuse or stop it")
    if not record.get("instance_id") or health.get("instance_id") != record.get("instance_id"):
        raise RuntimeError("Instance identity mismatch; refusing to reuse or stop this process")
    return True


def process_running(pid: object) -> bool:
    try:
        number = int(pid)
    except (TypeError, ValueError):
        return False
    if number <= 0:
        return False
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x00100000, False, number)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(ctypes.c_void_p(handle), 0) == 0x102
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(number, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@contextlib.contextmanager
def startup_lock(runtime: Path):
    runtime.parent.mkdir(parents=True, exist_ok=True)
    lock = open(runtime.parent / "launcher.lock", "a+b")
    lock.seek(0, 2)
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    deadline = time.monotonic() + 12
    locked = False
    try:
        while not locked:
            try:
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Another launcher is busy. Retry in a moment.")
                time.sleep(0.15)
        yield
    finally:
        if locked:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def start(runtime: Path, data_root: Path, open_browser: bool) -> dict:
    with startup_lock(runtime):
        old = read_runtime(runtime)
        if old and matching_health(old):
            result = {"status": "already_running", "url": local_url(old), "pid": old["pid"]}
        else:
            if old and process_running(old.get("pid")):
                raise RuntimeError("Recorded process is still alive but its health check failed. Do not start a duplicate; inspect diagnostics.")
            data_root.mkdir(parents=True, exist_ok=True)
            logfile = runtime.parent / "server.log"
            command = [sys.executable, "-m", "local_app.server", "--data-root", str(data_root.resolve()),
                       "--port", "0", "--runtime-file", str(runtime.resolve())]
            creationflags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
            with logfile.open("ab") as log:
                process = subprocess.Popen(command, cwd=str(APP_ROOT), stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=log, creationflags=creationflags,
                                           start_new_session=os.name != "nt")
            deadline = time.monotonic() + 15
            result = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Server exited during startup. Inspect: " + str(logfile))
                current = read_runtime(runtime)
                if current and int(current.get("pid", 0)) == process.pid and matching_health(current):
                    result = {"status": "started", "url": local_url(current), "pid": process.pid}
                    break
                time.sleep(0.15)
            if result is None:
                raise RuntimeError("Startup outcome unknown; do not launch again until diagnostics reconcile it. Log: " + str(logfile))
    if open_browser:
        webbrowser.open(result["url"])
    return result


def stop(runtime: Path) -> dict:
    with startup_lock(runtime):
        record = read_runtime(runtime)
        if not record:
            return {"status": "not_running"}
        if not matching_health(record):
            if process_running(record.get("pid")):
                raise RuntimeError("Server health is unavailable. No process was killed; inspect diagnostics.")
            return {"status": "not_running", "note": "Stale runtime file retained"}
        token = record.get("stop_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Missing local stop token; refusing unauthenticated shutdown")
        request(local_url(record) + "/api/shutdown", token)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not process_running(record.get("pid")):
                return {"status": "stopped"}
            try:
                if not matching_health(record):
                    return {"status": "shutdown_requested", "note": "HTTP listener closed"}
            except RuntimeError:
                return {"status": "shutdown_requested", "note": "Original instance no longer owns its listener"}
            time.sleep(0.2)
        raise RuntimeError("Shutdown requested, but exit is not confirmed. No process was force-killed.")


def diagnose(runtime: Path) -> dict:
    result = {"app": APP, "application_root": str(APP_ROOT), "python": sys.version.split()[0],
              "python_executable": sys.executable, "default_data_root": str(data_directory()),
              "runtime_file": str(runtime), "api_billing": "disabled", "generation_mode": "interactive_handoff"}
    try:
        from PIL import __version__
        result["pillow"] = __version__
    except ImportError:
        result["pillow"] = "missing; run Install-CharacterSheets.ps1"
    try:
        record = read_runtime(runtime)
        result["running"] = bool(record and matching_health(record))
        if record:
            result["url"] = local_url(record)
            result["pid"] = record.get("pid")
            result["data_root"] = record.get("data_root", "unreported")
    except RuntimeError as exc:
        result["running"] = "unknown"
        result["error"] = str(exc)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "diagnose"))
    parser.add_argument("--runtime-file", type=Path, default=RUNTIME)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            result = start(args.runtime_file.resolve(), (args.data_root or data_directory()).resolve(), not args.no_browser)
        elif args.command == "stop":
            result = stop(args.runtime_file.resolve())
        else:
            result = diagnose(args.runtime_file.resolve())
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, urllib.error.URLError) as exc:
        print("Character Sheets: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
