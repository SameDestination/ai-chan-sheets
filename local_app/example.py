"""Deterministic non-sensitive mechanical fixtures, never AI/artwork evidence."""
import io

from PIL import Image, ImageDraw

from .core import PROFILE_FIELDS, now
from .safety import atomic, digest, write_json


def fixture(index, size=(80, 80), rgba=False):
    mode = "RGBA" if rgba else "RGB"
    color = ((index * 37 + 20) % 256, (index * 71 + 40) % 256, (index * 19 + 80) % 256)
    im = Image.new(mode, size, color + (90,) if rgba else color)
    draw = ImageDraw.Draw(im)
    draw.rectangle((index % 12, 10, size[0] - 8, size[1] - 9), outline="black", width=2)
    draw.text((8, 18), f"FIXTURE {index:02}", fill="black")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def prepared_project(store):
    m = store.create("离线机械样例（非生成、非美术审批）")
    m = store.add_reference(m["id"], fixture(99, (200, 220)), "fixture.png", "程序生成的非敏感测试几何图；不是角色原画。")
    profile = {k: [{"kind": "unknown", "text": "离线测试，无角色设定"}] for k in PROFILE_FIELDS}
    profile["identity_anchors"] = [{"kind": "user_specified", "text": "标有FIXTURE的不同彩色测试块"}]
    profile["source_art_style"] = [{"kind": "observed", "text": "机械测试图形，非角色绘画"}]
    tasks = m["tasks"]
    for i, t in enumerate(tasks):
        if "待确认" in t["title"]:
            t["title"] = f"机械样例 {i + 1}"
        t["instruction"] = "只供离线像素、排版与版本机制验证，不构成角色资产。"
        t["size"] = "120x200" if t["id"].startswith("A") else "80x80"
    m = store.plan(m["id"], profile, tasks)
    return store.approve_plan(m["id"])


def create_example(store):
    m = prepared_project(store)
    m["example"] = True
    m["artwork_approved"] = False
    m["example_notice"] = "离线机械测试图；未调用图像模型；fixture_approved仅代表测试数据可参与机械核验，不是人工美术批准。"
    project = store.path(m["id"])
    for i, t in enumerate(m["tasks"]):
        w, h = (120, 200) if t["id"].startswith("A") else (80, 80)
        file = f"{t['group']}/{t['id']}_v01.png"
        atomic(project / file, fixture(i + 1, (w, h), i % 2 == 0), immutable=True)
        sha = digest(project / file)
        record_file = f"00_生成记录/{t['id']}_v01_fixture.json"
        rec = {"id": t["id"], "task_id": t["id"], "version": 1, "group": t["group"], "label": t["title"],
               "status": "success", "review_status": "approved", "review_basis": "offline_fixture_only_not_artwork_approval",
               "execution_mode": "offline_fixture", "file": file, "output": file, "sha256": sha, "output_sha256": sha,
               "width": w, "height": h, "dimensions": [w, h], "actual_dimensions": [w, h], "record_file": record_file,
               "revision": m["revision"], "fingerprint": store.signature(m, t["id"]), "model": "unreported",
               "returned_model": "none_offline_fixture", "size": t["size"], "quality": "none", "settings_gap": False,
               "prompt": store.prompt(m, t["id"]), "refs": store.resolve_refs(m, t["id"]), "created_at": now(), "review_notes": m["example_notice"]}
        write_json(project / record_file, rec, immutable=True)
        m["attempts"][t["id"]] = [rec]
        m["selections"][t["id"]] = 1
        m["task_status"][t["id"]] = "approved"
    store.save(m)
    return m
