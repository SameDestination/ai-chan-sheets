"""Managed-path, atomic IO and bounded image primitives. No network providers."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import warnings

from PIL import Image

MAX_UPLOAD = 25 * 1024 * 1024
MAX_ASSET_PIXELS = 24_000_000
MAX_EDGE = 8192
ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value), "标识符不合法")
    return value


def managed(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative and ":" not in relative,
            "只允许工程内相对路径")
    p = PurePosixPath(relative)
    require(not p.is_absolute() and all(x not in ("..", ".", "") for x in relative.split("/")), "路径越界")
    base = Path(root).resolve()
    result = (base / relative).resolve()
    require(result.is_relative_to(base) and result != base, "路径越界或符号链接越界")
    return result


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic(path, data, *, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not immutable or not path.exists(), "历史文件不可覆盖")
    fd, temp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if immutable:
            # The server serializes writes; never overwrite an existing attempt.
            require(not path.exists(), "历史文件不可覆盖")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, value, **kw):
    atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), **kw)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def image_info(data):
    require(0 < len(data) <= MAX_UPLOAD, "图像文件为空或超过25MiB")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as im:
            require(im.format in ("PNG", "JPEG", "WEBP"), "仅接受PNG/JPEG/WebP图像")
            w, h = im.size
            require(0 < w <= MAX_EDGE and 0 < h <= MAX_EDGE and w * h <= MAX_ASSET_PIXELS, "图像尺寸超过安全上限")
            require(not getattr(im, "is_animated", False), "请先选择单帧静态图像")
            fmt = im.format
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            return {"width": w, "height": h, "format": fmt, "mode": im.mode}


def white_rgb(im):
    rgba = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, "white")
    bg.alpha_composite(rgba)
    return bg.convert("RGB")
