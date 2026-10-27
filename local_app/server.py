"""Loopback-only local server. No image-provider credentials, SDK or outbound requests."""
import argparse
import base64
import binascii
import io
import json
import mimetypes
import os
from pathlib import Path
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image

from .core import Store, capability
from .safety import MAX_UPLOAD, managed, read_json, require, white_rgb, write_json


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, root, port=0, runtime_file=None, instance_id=None):
        super().__init__(("127.0.0.1", port), Handler)
        self.store = Store(root)
        self.store.recover()
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.stop_token = secrets.token_urlsafe(32)
        self.instance_id = instance_id or secrets.token_hex(16)
        self.runtime_file = Path(runtime_file) if runtime_file else None
        self.web = Path(__file__).parent / "web"

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"

    def runtime(self):
        return {"app": "character-sheets-local", "pid": os.getpid(), "port": self.server_port, "url": self.url,
                "instance_id": self.instance_id, "data_root": str(self.store.root), "stop_token": self.stop_token}


class Handler(BaseHTTPRequestHandler):
    server_version = "CharacterSheets/1.0"

    def log_message(self, fmt, *args):
        pass

    def guard(self, mutation=False, shutdown=False):
        valid = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        require(self.headers.get("Host") in valid, "Host必须是当前本地地址")
        origin = self.headers.get("Origin")
        require(not origin or origin in {"http://" + h for h in valid}, "拒绝不可信浏览器来源")
        require(self.headers.get("Sec-Fetch-Site", "none") in ("none", "same-origin", "same-site"), "禁止跨站访问")
        if mutation:
            expected = self.server.stop_token if shutdown else self.server.token
            require(secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), expected), "缺少本会话CSRF校验")
            require(self.headers.get("Content-Type", "").split(";", 1)[0] == "application/json", "需要application/json")

    def reply(self, value, code=200, content_type="application/json; charset=utf-8", filename=None):
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if filename:
            self.send_header("Content-Disposition", "attachment; filename=export.json")
        self.end_headers()
        self.wfile.write(data)

    def error(self, e):
        if isinstance(e, (ValueError, KeyError, TypeError, FileNotFoundError, binascii.Error, Image.DecompressionBombError, Image.UnidentifiedImageError)):
            self.reply({"error": str(e)}, 400)
        else:
            self.reply({"error": f"操作失败：{type(e).__name__}: {e}"}, 500)

    def do_GET(self):
        try:
            self.guard()
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            one = lambda k: query.get(k, [""])[0]
            path = parsed.path
            with self.server.lock:
                if path == "/health":
                    self.reply({"app": "character-sheets-local", "pid": os.getpid(), "instance_id": self.server.instance_id})
                elif path == "/api/status":
                    self.reply({"capability": capability(), "csrf_token": self.server.token,
                                "projects": self.server.store.list(), "data_root": str(self.server.store.root)})
                elif path == "/api/project":
                    self.reply(self.server.store.get(one("id")))
                elif path == "/api/prompt":
                    m = self.server.store.get(one("project"))
                    self.reply(self.server.store.prompt(m, one("task")))
                elif path == "/file":
                    p = managed(self.server.store.path(one("project")), one("path"))
                    require(p.is_file(), "文件不存在")
                    if one("preview") == "true" and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        with Image.open(p) as im:
                            im.thumbnail((1400, 1400))
                            rgb = white_rgb(im)
                            buf = io.BytesIO()
                            rgb.save(buf, "PNG")
                            self.reply(buf.getvalue(), content_type="image/png")
                    else:
                        require(p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".json", ".md", ".zip"), "文件类型不可下载")
                        self.reply(p.read_bytes(), content_type=mimetypes.guess_type(p.name)[0] or "application/octet-stream")
                elif path == "/" or path in ("/static/app.js", "/static/style.css"):
                    file = "index.html" if path == "/" else path.rsplit("/", 1)[1]
                    p = self.server.web / file
                    self.reply(p.read_bytes(), content_type={"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8"}[p.suffix[1:]])
                else:
                    self.reply({"error": "路径不存在"}, 404)
        except Exception as e:
            self.error(e)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            self.guard(mutation=True, shutdown=path == "/api/shutdown")
            length = int(self.headers.get("Content-Length", "0"))
            require(0 < length <= 36 * 1024 * 1024, "请求为空或超出36MiB")
            data = json.loads(self.rfile.read(length))
            require(isinstance(data, dict), "请求须为JSON对象")
            with self.server.lock:
                if path == "/api/create":
                    result = self.server.store.create(data.get("name"), data.get("preset", "upstream22"))
                elif path == "/api/action":
                    result = self.action(data)
                elif path == "/api/shutdown":
                    result = {"stopping": True}
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    self.reply({"error": "路径不存在"}, 404)
                    return
            self.reply(result)
        except Exception as e:
            self.error(e)

    def action(self, d):
        store = self.server.store
        pid, action = d.get("project"), d.get("action")
        def uploaded():
            encoded = d.get("data", "")
            require(isinstance(encoded, str) and len(encoded) <= (MAX_UPLOAD * 4 // 3 + 4), "上传超出25MiB")
            return base64.b64decode(encoded, validate=True)
        if action == "example":
            from .example import create_example
            return create_example(store)
        if action == "plan":
            return store.plan(pid, d["profile"], d["tasks"], d.get("preset"), d.get("custom_reason", ""))
        if action == "approve_plan":
            return store.approve_plan(pid)
        if action == "reference":
            return store.add_reference(pid, uploaded(), d.get("filename"), d.get("notes", ""))
        if action == "crop":
            return store.crop(pid, d["reference"], d["box"], d.get("notes", ""))
        if action == "reject_reference":
            return store.reject_reference(pid, d["reference"])
        if action == "prompt":
            return store.edit_prompt(pid, d["task"], d["prompt"])
        if action == "import_prompts":
            return store.import_prompts(pid, d["prompts"], d.get("directory", "提示词"))
        if action == "enqueue":
            return store.enqueue(pid, d["tasks"])
        if action == "handoff":
            return store.handoff(pid, d["task"], d.get("billing_evidence", ""), d.get("included_allowance_verified", False), d.get("authorize_requests", 1), d.get("correction", ""))
        if action == "queue":
            return store.queue_control(pid, d["operation"])
        if action == "import":
            return store.import_image(pid, d["task"], uploaded(), d.get("execution_mode"), d.get("billing_evidence", ""), d.get("source_path", ""), d.get("model", "unreported"))
        if action == "review":
            return store.review(pid, d["task"], d["version"], d["decision"], d.get("notes", ""), d.get("accept_settings_gap", False))
        if action == "select":
            return store.select(pid, d["task"], d["version"])
        if action == "failure":
            return store.report_failure(pid, d["task"], d["kind"], d.get("retry_after"))
        if action == "resolve_unknown":
            return store.resolve_unknown(pid, d["task"], d["decision"])
        if action == "compose":
            return store.compose(pid, d.get("options"))
        if action == "verify":
            return store.verify(pid)
        if action == "export_upstream":
            return store.export_upstream(pid)
        raise ValueError("未知操作")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path.home() / "Documents" / "CharacterSheets")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--runtime-file", type=Path)
    parser.add_argument("--instance-id")
    args = parser.parse_args()
    if args.instance_id:
        require(len(args.instance_id) == 32 and all(v in "0123456789abcdef" for v in args.instance_id), "实例ID无效")
    server = Server(args.data_root, args.port, args.runtime_file, args.instance_id)
    if args.runtime_file:
        write_json(args.runtime_file, server.runtime())
    try:
        print(server.url, flush=True)
        server.serve_forever()
    finally:
        server.server_close()
        if args.runtime_file and args.runtime_file.is_file():
            if read_json(args.runtime_file).get("instance_id") == server.instance_id:
                args.runtime_file.unlink()


if __name__ == "__main__":
    main()
