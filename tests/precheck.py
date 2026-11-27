"""Pre-deploy gate checks: syntax, static HTML/JS integrity, catalog, audio logic, and live HTTP smoke."""

import json
import os
import py_compile
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE, "backend")
SITE_DIR = os.path.join(BASE, "product_site")

sys.path.insert(0, BASE)
sys.path.insert(0, BACKEND_DIR)


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_python_syntax():
    print("[1/5] Checking Python syntax...")
    targets = [
        os.path.join(BASE, "server.py"),
        os.path.join(BASE, "check_install.py"),
    ]
    for fn in sorted(os.listdir(BACKEND_DIR)):
        if fn.endswith(".py"):
            targets.append(os.path.join(BACKEND_DIR, fn))
    for path in targets:
        py_compile.compile(path, doraise=True)
    print(f"  -> PASS: compiled {len(targets)} Python files")


def check_frontend_static():
    print("[2/5] Checking JS syntax and HTML local references...")
    node = shutil.which("node")
    js_files = sorted(fn for fn in os.listdir(SITE_DIR) if fn.endswith(".js"))
    if node:
        for fn in js_files:
            res = subprocess.run(
                [node, "--check", os.path.join(SITE_DIR, fn)],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                raise AssertionError(f"node --check failed for {fn}: {res.stderr or res.stdout}")
    else:
        print("  [warn] node not found; skipping JS syntax check")

    html_files = sorted(
        fn for fn in os.listdir(SITE_DIR) if fn.endswith(".html") and not fn.startswith("_")
    )
    ref_re = re.compile(r'''(?:<script[^>]+src|<link[^>]+href)=["']([^"']+)["']''', re.I)
    checked_refs = 0
    for fn in html_files:
        with open(os.path.join(SITE_DIR, fn), "r", encoding="utf-8") as f:
            html = f.read()
        for raw_ref in ref_re.findall(html):
            ref = raw_ref.strip()
            if not ref or ref.startswith(("http://", "https://", "//", "data:", "#")):
                continue
            rel = ref.split("?", 1)[0].split("#", 1)[0].lstrip("/")
            if not rel:
                continue
            target = os.path.normpath(os.path.join(SITE_DIR, rel))
            if not os.path.isfile(target):
                raise AssertionError(f"{fn} references missing local file: {raw_ref}")
            checked_refs += 1
    print(f"  -> PASS: {len(js_files)} JS files, {len(html_files)} HTML files ({checked_refs} local refs)")


def check_catalog_and_assets():
    print("[3/5] Checking sound_catalog, disk assets, and yexi_catalog.js...")
    import sound_catalog
    import server

    assert len(sound_catalog.ALL_SOUNDS) == 41, f"expected 41 sounds, got {len(sound_catalog.ALL_SOUNDS)}"

    layers = {}
    for item in sound_catalog.ALL_SOUNDS:
        layers[item["layer"]] = layers.get(item["layer"], 0) + 1
    assert layers == {"bed": 18, "texture": 12, "accent": 11}, f"unexpected layers: {layers}"

    disk_rels = set()
    for folder in ("product_assets", "scene_assets"):
        for fn in os.listdir(os.path.join(BASE, folder)):
            disk_rels.add(f"{folder}/{fn}")
    cat_rels = {it["rel_path"] for it in sound_catalog.ALL_SOUNDS}
    assert disk_rels == cat_rels, f"disk/catalog mismatch: {disk_rels ^ cat_rels}"

    for fn in sound_catalog.ALLOWED_TRACK_FILES:
        assert server.find_relpath(fn) != "", f"server.find_relpath missing {fn}"

    js_path = os.path.join(SITE_DIR, "yexi_catalog.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js_txt = f.read()
    m = re.search(r"var\s+YEXI_SOUNDS\s*=\s*\[(.*?)\];", js_txt, re.S)
    assert m, "YEXI_SOUNDS array not found in yexi_catalog.js"
    arr_txt = m.group(1)
    js_paths = re.findall(r'path:\s*"([^"]+)"', arr_txt)
    js_imgs = re.findall(r'img:\s*"([^"]+)"', arr_txt)
    assert len(js_paths) == 41, f"expected 41 YEXI_SOUNDS entries, got {len(js_paths)}"
    assert set(js_paths) == set(sound_catalog.ALLOWED_TRACK_FILES), "frontend/backend track mismatch"
    for rel_img in js_imgs:
        clean_img = rel_img.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        full_img = os.path.join(SITE_DIR, clean_img)
        assert os.path.isfile(full_img), f"missing frontend cover image: {rel_img}"
    print("  -> PASS: 41 sounds, layers(18/12/11), disk assets, and frontend catalog match")


def check_core_logic_and_render():
    print("[4/5] Checking rules engine, feedback translation, and audio render...")
    import numpy as np
    import feedback_translate as ft
    import understanding_brain as brain
    import server

    res = brain.design_soundscape_rules("睡不着，想要窗外暖一点的雨声，不要雷", force_compose=True)
    assert res["action"] == "compose" and len(res["tracks"]) >= 1
    assert res["intent"]["scene"] == "rain"
    assert all("远雷" not in t["path"] for t in res["tracks"])

    new_fire, _ = ft.apply_feedback("太吵了", [("scene_assets/炉火_营地篝火_62487.hq.mp3", 1.0)])
    assert any("766127" in p or "836535" in p for p, w in new_fire if w > 0)

    tw = brain._apply_incremental_tweak(
        "不要鸟了",
        [
            {"path": "溪流_柔和河水_707576.hq.mp3", "weight": 0.7, "pan": 0.0, "mode": "loop", "density": 0.4},
            {"path": "鸟鸣_夜莺鸣叫_853566.hq.mp3", "weight": 0.3, "pan": 0.4, "mode": "intermittent", "density": 0.3},
        ],
    )
    assert tw and all("鸟鸣" not in t["path"] for t in tw["tracks"])

    mix, sr = server.render(
        [
            {"rel": "scene_assets/炉火_夜营氛围_766127.hq.mp3", "weight": 0.70, "pan": 0.0, "mode": "loop", "density": 0.4},
            {"rel": "scene_assets/ASMR_羽毛轻拂_708086.hq.mp3", "weight": 0.35, "pan": 0.3, "mode": "intermittent", "density": 0.45},
        ],
        seconds=2,
    )
    assert sr == 44100 and mix.shape == (44100 * 2, 2), f"unexpected render shape: {mix.shape}"
    assert not np.isnan(mix).any() and not np.isinf(mix).any(), "render produced NaN/Inf"
    peak = float(np.max(np.abs(mix)))
    assert 0.01 < peak <= 0.9501, f"unexpected peak: {peak}"
    print(f"  -> PASS: rules, feedback, and 2s render OK (peak={peak:.4f})")


def _http(url, method="GET", body=None):
    data = None
    headers = {"User-Agent": "yexi-precheck/1.0"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        e.close()
        return e.code, raw


def check_live_server_smoke():
    print("[5/5] Starting local server for HTTP smoke test...")
    port = _find_free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["YEXI_PAY_MODE"] = "mock"
    env.pop("YEXI_ALERT_WEBHOOK", None)

    proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE, "server.py")],
        cwd=BASE,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        ready = False
        for _ in range(40):
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                raise AssertionError(f"server exited early ({proc.returncode}):\n{out[-1000:]}")
            try:
                code, raw = _http(base + "/api/health")
                if code == 200:
                    health = json.loads(raw.decode("utf-8"))
                    assert health.get("ok") is True and health.get("db") is True, f"bad health: {health}"
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(0.25)
        assert ready, "timed out waiting for local /api/health"

        code, raw = _http(base + "/api/catalog")
        assert code == 200
        cat = json.loads(raw.decode("utf-8"))
        assert len(cat.get("items") or []) == 41, "unexpected /api/catalog item count"

        code, raw = _http(base + "/api/community_posts")
        assert code == 200 and "posts" in json.loads(raw.decode("utf-8"))

        code, raw = _http(base + "/api/pay/products")
        assert code == 200 and "products" in json.loads(raw.decode("utf-8"))

        code, raw = _http(
            base + "/api/client_error",
            method="POST",
            body={"kind": "error", "page": "/precheck", "message": "smoke test", "line": 1},
        )
        assert code == 200 and json.loads(raw.decode("utf-8")).get("ok") is True

        for page in ("/home.html", "/m.html", "/install.html"):
            code, _ = _http(base + page)
            assert code == 200, f"GET {page} returned {code}"

        code, _ = _http(base + "/home.html", method="HEAD")
        assert code == 200, f"HEAD /home.html returned {code}"

        print(f"  -> PASS: local server HTTP smoke passed on port {port}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


if __name__ == "__main__":
    check_python_syntax()
    check_frontend_static()
    check_catalog_and_assets()
    check_core_logic_and_render()
    check_live_server_smoke()
    print("\nPRECHECK PASSED!")
