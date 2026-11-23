# 轻量后端 API + 静态页面：一个端口同时服务前后端
# key 只在这个文件所在的服务端读取，绝不发给浏览器
# 只用标准库 http.server，不装 Flask

import json
import hashlib
import mimetypes
import os
import random
import re
import secrets
import time
import urllib.parse

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import understanding_brain
import 素材执行层 as executor
import feedback_translate as ft
import memory_system as memory
import auth_db

# 部署平台通过 PORT 环境变量注入端口，本机开发默认 8000
PORT = int(os.environ.get("PORT", "8000"))
BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "agent_output")
SITE_DIR = os.path.join(BASE, "product_site")


def serve_static(handler, path):
    # 只服务 product_site 里的文件；API 路径不在这里处理
    if path == "/" or path == "":
        path = "/home.html"
    rel = urllib.parse.unquote(path).lstrip("/")
    full = os.path.normpath(os.path.join(SITE_DIR, rel))
    # 防路径穿越：解析后必须仍在 SITE_DIR 里面
    if not full.startswith(os.path.abspath(SITE_DIR) + os.sep):
        handler.send_json({"error": "forbidden"}, 403)
        return
    if not os.path.isfile(full):
        handler.send_json({"error": "not found"}, 404)
        return
    with open(full, "rb") as f:
        body = f.read()
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    if ctype.startswith("text/") or "javascript" in ctype or "json" in ctype:
        ctype += "; charset=utf-8"
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def read_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw)


def current_user(handler):
    # 从 Authorization: Bearer <token> 识别登录用户，未登录返回 None（游客）
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth_db.user_from_token(auth[7:].strip())


def get_token(handler):
    auth = handler.headers.get("Authorization", "")
    return auth[7:].strip() if auth.startswith("Bearer ") else ""


def get_user_memory(user):
    # 登录用户从数据库读记忆；游客读本地 JSON
    store = _recipe_store(user)
    ep = store.read("ear_profile.json")
    ear_profile = ep if isinstance(ep, dict) and ep.get("archetype_id") else None
    if user:
        # 键名要和 memory_system 写入时一致，都带 .json，否则读出来永远是空
        return {
            "preferences": auth_db.load_memory(user["id"], "preferences.json").get("counts", {}),
            "good_count": len(auth_db.load_memory(user["id"], "good_recipes.json").get("recipes", [])),
            "bad_count": len(auth_db.load_memory(user["id"], "bad_cases.json").get("cases", [])),
            "ear_profile": ear_profile,
        }
    pref = memory.read_file("preferences.json")
    good = memory.read_file("good_recipes.json")
    bad = memory.read_file("bad_cases.json")
    return {
        "preferences": pref.get("counts", {}),
        "good_count": len(good.get("recipes", [])),
        "bad_count": len(bad.get("cases", [])),
        "ear_profile": ear_profile,
    }


def _get_user_agent_context(user):
    # 为多轮 Agent 提取耳朵档案、口味统计和历史避雷（均带 .json 后缀）
    store = _recipe_store(user)
    ep = store.read("ear_profile.json")
    pref = store.read("preferences.json")
    bad = store.read("bad_cases.json")

    ctx = {}
    if isinstance(ep, dict) and ep.get("archetype_id"):
        ctx["ear_profile"] = {
            "archetype_name": ep.get("archetype_name", ""),
            "tagline": ep.get("tagline", ""),
            "scores": ep.get("scores", {}),
            "intent": ep.get("intent", {}),
        }
    if isinstance(pref, dict) and isinstance(pref.get("counts"), dict) and pref["counts"]:
        ctx["preferences"] = pref["counts"]
    if isinstance(bad, dict) and isinstance(bad.get("cases"), list) and bad["cases"]:
        ctx["bad_feedbacks"] = [
            str(c.get("feedback") or "")
            for c in bad["cases"][-5:]
            if isinstance(c, dict) and c.get("feedback")
        ]
    return ctx


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _normalize_track_spec(raw):
    # 兼容旧格式 (rel, weight) 与新格式字典 {"rel", "weight", "pan", "mode", "density"}
    if isinstance(raw, (list, tuple)):
        rel = str(raw[0])
        try:
            w = float(raw[1])
        except (TypeError, ValueError):
            w = 0.0
        return {
            "rel": rel,
            "weight": max(0.0, w),
            "pan": 0.0,
            "mode": "loop",
            "density": 0.4,
        }
    if isinstance(raw, dict):
        rel = str(raw.get("rel") or raw.get("path") or "")
        try:
            w = float(raw.get("weight", 0.0))
        except (TypeError, ValueError):
            w = 0.0
        try:
            pan = float(raw.get("pan", 0.0))
        except (TypeError, ValueError):
            pan = 0.0
        mode = "intermittent" if raw.get("mode") == "intermittent" else "loop"
        try:
            density = float(raw.get("density", 0.4))
        except (TypeError, ValueError):
            density = 0.4
        return {
            "rel": rel,
            "weight": max(0.0, w),
            "pan": _clamp(pan, -1.0, 1.0),
            "mode": mode,
            "density": _clamp(density, 0.1, 1.0),
        }
    return {"rel": "", "weight": 0.0, "pan": 0.0, "mode": "loop", "density": 0.4}


def _load_stereo_resampled(path, sr):
    import numpy as np
    data, file_sr = executor.read_audio(path)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    if file_sr != sr and len(data) > 0:
        old_len = len(data)
        new_len = max(1, int(old_len * sr / file_sr))
        x_old = np.linspace(0, old_len - 1, old_len)
        x_new = np.linspace(0, old_len - 1, new_len)
        left = np.interp(x_new, x_old, data[:, 0])
        right = np.interp(x_new, x_old, data[:, 1])
        data = np.stack([left, right], axis=1).astype("float32")
    return data


def _calc_active_rms_gain(seg, sr=44100):
    # 按 0.25s 分块测有效 RMS，忽略近静音块，给一个恒定标量响度对齐（零动态压缩）
    import numpy as np
    if len(seg) == 0:
        return 1.0
    block = max(1, int(sr * 0.25))
    usable = (len(seg) // block) * block
    if usable >= block:
        blocks = seg[:usable].reshape(-1, block, 2)
        rms_vals = np.sqrt(np.mean(blocks ** 2, axis=(1, 2)))
    else:
        rms_vals = np.array([float(np.sqrt(np.mean(seg ** 2)))], dtype="float32")
    active = rms_vals[rms_vals >= 0.002]
    if len(active) == 0:
        return 1.0
    active_rms = float(np.median(active))
    if active_rms <= 1e-6:
        return 1.0
    return _clamp(0.10 / active_rms, 0.35, 2.2)


def _render_intermittent_track(path, frames, sr, density):
    # 在总时长内生成确定性的自然偶发事件窗口（2.0s 淡入 + 2.5s 淡出，零音色篡改）
    import numpy as np
    data = _load_stereo_resampled(path, sr)
    out = np.zeros((frames, 2), dtype="float32")
    if len(data) == 0 or frames <= 0:
        return out

    bucket_len = max(1, int(sr * 2.0))
    n_buckets = max(1, len(data) // bucket_len)
    bucket_rms = []
    for idx in range(n_buckets):
        chunk = data[idx * bucket_len:(idx + 1) * bucket_len]
        bucket_rms.append(float(np.sqrt(np.mean(chunk ** 2))))
    med_rms = float(np.median(bucket_rms)) if bucket_rms else 0.0
    active_starts = [i * bucket_len for i, r in enumerate(bucket_rms) if r >= max(0.002, med_rms * 0.65)]
    if not active_starts:
        active_starts = [0]

    d = _clamp(density, 0.1, 1.0)
    seed_src = f"{os.path.basename(path)}:{d:.2f}"
    seed = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # 稀疏(0.1~0.2): 16~28s; 适中(0.5): 7~14s; 频繁(0.9~1.0): 2~6s
    if d <= 0.5:
        u = _clamp((0.5 - d) / 0.4, 0.0, 1.0)
        min_gap_s = 7.0 + u * 9.0
        max_gap_s = 14.0 + u * 14.0
    else:
        u = _clamp((d - 0.5) / 0.4, 0.0, 1.0)
        min_gap_s = 7.0 - u * 5.0
        max_gap_s = 14.0 - u * 8.0

    pos = int(sr * rng.uniform(0.5, 1.4))
    while pos < frames:
        win_frames = int(sr * rng.uniform(6.0, 10.0))
        if len(data) < win_frames:
            win_frames = len(data)
        actual_len = min(win_frames, frames - pos)
        if actual_len <= int(sr * 0.5):
            break

        src_start = rng.choice(active_starts)
        if src_start + actual_len <= len(data):
            seg = data[src_start:src_start + actual_len].copy()
        else:
            part1 = data[src_start:]
            need = actual_len - len(part1)
            part2 = data[:need]
            seg = np.concatenate([part1, part2], axis=0).copy()

        fi = min(int(sr * 2.0), actual_len // 3)
        fo = min(int(sr * 2.5), actual_len // 3)
        if fi > 0:
            t_in = np.linspace(0.0, np.pi, fi, dtype="float32")[:, None]
            seg[:fi] *= 0.5 * (1.0 - np.cos(t_in))
        if fo > 0:
            t_out = np.linspace(0.0, np.pi, fo, dtype="float32")[:, None]
            seg[-fo:] *= 0.5 * (1.0 + np.cos(t_out))

        out[pos:pos + actual_len] += seg
        gap_frames = int(sr * rng.uniform(min_gap_s, max_gap_s))
        pos += actual_len + gap_frames

    cal_gain = _calc_active_rms_gain(data, sr)
    return out * cal_gain


def render(items, seconds):
    # 按配比、恒定响度对齐与声像拼一段成品，零音质处理
    import numpy as np
    sr = 44100
    frames = int(sr * seconds)
    mix = np.zeros((frames, 2), dtype="float32")
    for raw in items:
        spec = _normalize_track_spec(raw)
        rel = spec["rel"]
        w = spec["weight"]
        if not rel or w <= 0:
            continue
        path = os.path.join(BASE, rel)
        if not os.path.exists(path):
            continue
        if spec["mode"] == "intermittent":
            seg = _render_intermittent_track(path, frames, sr, spec["density"])
        else:
            seg = executor.load_loop(path, frames, sr)
            cal_gain = _calc_active_rms_gain(seg, sr)
            seg = seg * cal_gain

        pan = spec["pan"]
        if abs(pan) > 1e-4:
            theta = (pan + 1.0) * np.pi / 4.0
            left_gain = float(np.cos(theta) * np.sqrt(2.0))
            right_gain = float(np.sin(theta) * np.sqrt(2.0))
            seg = seg.copy()
            seg[:, 0] *= left_gain
            seg[:, 1] *= right_gain

        mix += seg * w

    peak = float(np.max(np.abs(mix))) if len(mix) > 0 else 0.0
    if peak > 0.95:
        mix = mix * (0.95 / peak)
    fi = min(int(sr * 0.5), frames // 2)
    if fi > 0:
        mix[:fi] *= np.linspace(0, 1, fi, dtype="float32")[:, None]
        mix[-fi:] *= np.linspace(1, 0, fi, dtype="float32")[:, None]
    return mix, sr


def find_relpath(name):
    # 给一个文件名，在已验收素材目录（product_assets / scene_assets）找到它的相对路径（防路径穿越）
    clean = os.path.basename(str(name or "").strip())
    if not clean or clean != str(name or "").strip():
        return ""
    for scene in executor.LIBRARY:
        for rel, w in executor.LIBRARY[scene]:
            if os.path.basename(rel) == clean:
                return rel
    if clean.lower().endswith(".mp3"):
        for folder in ("product_assets", "scene_assets"):
            candidate = os.path.join(BASE, folder, clean)
            if os.path.isfile(candidate):
                return folder + "/" + clean
    return ""


# ---- 稳定播放：按配方内容落盘，URL 不随别的试听改变，供跨页面/场景卡使用 ----
PLAY_DIR = os.path.join(OUT_DIR, "play")
PLAY_SECONDS = 60   # 场景卡/播放页用 60 秒循环基底，前端 loop 播放


def play_file(items, seconds=PLAY_SECONDS):
    # 配方按内容取哈希做文件名：同样的配比复用同一个文件
    os.makedirs(PLAY_DIR, exist_ok=True)
    parts = []
    for raw in items:
        spec = _normalize_track_spec(raw)
        base = os.path.basename(spec["rel"])
        if spec["mode"] == "loop" and abs(spec["pan"]) < 1e-4 and abs(spec["density"] - 0.4) < 1e-4:
            parts.append("%s:%.3f" % (base, spec["weight"]))
        else:
            parts.append("%s:%.3f:%.2f:%s:%.2f" % (
                base, spec["weight"], spec["pan"], spec["mode"], spec["density"]
            ))
    key = "|".join(parts)
    name = hashlib.md5(key.encode("utf-8")).hexdigest()[:16] + ".wav"
    path = os.path.join(PLAY_DIR, name)
    if not os.path.exists(path):
        mix, sr = render(items, seconds)
        executor.write_wav(path, mix, sr)
    return name, path


def map_client_items(raw_items):
    # 把前端传入的 [{path, weight}] 映射回白名单相对路径
    if not isinstance(raw_items, list):
        return []
    mapped = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        rel = find_relpath(os.path.basename(str(it.get("path", ""))))
        try:
            w = float(it.get("weight", 0))
        except (TypeError, ValueError):
            w = 0.0
        if rel and w > 0:
            mapped.append((rel, w))
    return mapped


def map_client_tracks(raw_items):
    # 把前端传入的声轨列表（含 weight / pan / mode / density）映射并校验到白名单
    if not isinstance(raw_items, list):
        return []
    mapped = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        rel = find_relpath(os.path.basename(str(it.get("path", ""))))
        if not rel:
            continue
        spec = _normalize_track_spec({
            "rel": rel,
            "weight": it.get("weight", 0),
            "pan": it.get("pan", 0.0),
            "mode": it.get("mode", "loop"),
            "density": it.get("density", 0.4),
        })
        if spec["weight"] > 0:
            mapped.append(spec)
    return mapped


def _recipe_store(user):
    return memory.DbStore(user["id"]) if user else memory.FileStore()


ALLOWED_EVAL_TAGS = ("steady", "warm", "crisp", "deep", "borrow")


def _read_community_votes():
    data = memory.FileStore().read("community_votes.json")
    if isinstance(data, dict) and isinstance(data.get("votes"), dict):
        return data["votes"]
    return {}


def _write_community_votes(votes):
    memory.FileStore().write("community_votes.json", {"votes": votes})


def _read_community_posts():
    data = memory.FileStore().read("community_posts.json")
    if isinstance(data, dict) and isinstance(data.get("posts"), list):
        return [p for p in data["posts"] if isinstance(p, dict)]
    return []


def _write_community_posts(posts):
    memory.FileStore().write("community_posts.json", {"posts": posts[:100]})


def _public_post(post):
    out = dict(post)
    out.pop("delete_token", None)
    out.pop("user_id", None)
    return out


def _infer_post_group(tracks):
    if not tracks:
        return "自然"
    lead = max(tracks, key=lambda t: t.get("weight", 0))
    name = os.path.basename(lead.get("rel", ""))
    return "雨声" if "雨" in name else "自然"


# 每个会话的当前状态（演示版：只存一份，够单机用）
session = {"intent": None, "items": [], "say": ""}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_audio(self, data, sr):
        import io
        buf = io.BytesIO()
        executor.write_wav(buf, data, sr)
        body = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/me":
            user = current_user(self)
            self.send_json({"logged_in": user is not None,
                            "username": user["username"] if user else ""})

        elif path == "/api/memory":
            self.send_json(get_user_memory(current_user(self)))
        elif path == "/api/ear_profile":
            prof = _recipe_store(current_user(self)).read("ear_profile.json")
            valid = prof if isinstance(prof, dict) and prof.get("archetype_id") else None
            self.send_json({"ear_profile": valid})
        elif path == "/api/community_votes":
            self.send_json({"votes": _read_community_votes()})
        elif path == "/api/community_posts":
            posts = [_public_post(p) for p in _read_community_posts()]
            self.send_json({"posts": posts})
        elif path == "/api/recipes":
            store = _recipe_store(current_user(self))
            data_obj = store.read("custom_recipes.json")
            recipes = data_obj.get("recipes", []) if isinstance(data_obj, dict) else []
            if not isinstance(recipes, list):
                recipes = []
            self.send_json({"recipes": recipes})
        elif path == "/api/audio":
            if not hasattr(self.server, "last_audio"):
                self.send_json({"error": "还没有音频"}, 404)
                return
            mix, sr = self.server.last_audio
            self.send_audio(mix, sr)
        elif path == "/api/preview_audio":
            if not hasattr(self.server, "preview_audio"):
                self.send_json({"error": "还没有试听音频"}, 404)
                return
            mix, sr = self.server.preview_audio
            self.send_audio(mix, sr)
        elif path == "/api/asset":
            # 供前端多轨实时混音器直接拉取 CC0 原声素材（只允许库内白名单文件）
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = qs.get("name", [""])[0]
            if not name or "/" in name or "\\" in name or ".." in name:
                self.send_json({"error": "无效素材名"}, 400)
                return
            rel = find_relpath(name)
            if not rel:
                self.send_json({"error": "素材不在白名单"}, 404)
                return
            fpath = os.path.join(BASE, rel)
            if not os.path.exists(fpath):
                self.send_json({"error": "素材文件缺失"}, 404)
                return
            with open(fpath, "rb") as f:
                body = f.read()
            total = len(body)
            ext = os.path.splitext(rel)[1].lower()
            ctype = "audio/wav" if ext == ".wav" else ("audio/ogg" if ext == ".ogg" else "audio/mpeg")
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes=") and "," not in rng:
                spec = rng[6:].strip()
                parts = spec.split("-", 1)
                if len(parts) == 2:
                    try:
                        if parts[0] == "":
                            suffix = int(parts[1])
                            start = max(0, total - suffix)
                            end = total - 1
                        else:
                            start = int(parts[0])
                            end = int(parts[1]) if parts[1] != "" else total - 1
                        end = min(end, total - 1)
                        if 0 <= start <= end < total:
                            chunk = body[start:end + 1]
                            self.send_response(206)
                            self.send_header("Content-Type", ctype)
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.send_header("Accept-Ranges", "bytes")
                            self.send_header("Cache-Control", "public, max-age=86400")
                            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
                            self.send_header("Content-Length", str(len(chunk)))
                            self.end_headers()
                            self.wfile.write(chunk)
                            return
                        else:
                            self.send_response(416)
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.send_header("Content-Range", f"bytes */{total}")
                            self.end_headers()
                            return
                    except ValueError:
                        pass
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(total))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/play_audio":
            # 稳定播放文件：按名字取，支持 Range 请求（拖动/循环更稳）
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = qs.get("name", [""])[0]
            if not name or "/" in name or "\\" in name or ".." in name:
                self.send_json({"error": "无效音频名"}, 400)
                return
            fpath = os.path.join(PLAY_DIR, name)
            if not os.path.exists(fpath):
                self.send_json({"error": "音频不存在"}, 404)
                return
            with open(fpath, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            # 非 API 路径交给静态文件服务：前端页面、图片、js/css 都从这里出
            serve_static(self, path)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/register":
            data = read_body(self)
            ok, msg = auth_db.register(data.get("username", ""), data.get("password", ""))
            self.send_json({"ok": ok, "message": msg}, 200 if ok else 400)

        elif path == "/api/login":
            data = read_body(self)
            user, msg = auth_db.login(data.get("username", ""), data.get("password", ""))
            if not user:
                self.send_json({"ok": False, "message": msg}, 401)
                return
            token = auth_db.create_session(user["id"])
            self.send_json({"ok": True, "token": token, "username": user["username"]})

        elif path == "/api/logout":
            auth_db.logout(get_token(self))
            self.send_json({"ok": True})

        elif path == "/api/migrate":
            # 注册/登录后：把游客本机档案并进账号（各取并集，不丢数据）
            user = current_user(self)
            if not user:
                self.send_json({"error": "请先登录"}, 401)
                return
            db_store = memory.DbStore(user["id"])
            file_store = memory.FileStore()
            # 四类记忆分别合并
            for name, key in [("preferences.json", "counts"),
                              ("good_recipes.json", "recipes"),
                              ("bad_cases.json", "cases"),
                              ("custom_recipes.json", "recipes")]:
                local = file_store.read(name)
                remote = db_store.read(name)
                merged = dict(remote)
                if key == "counts":
                    counts = dict(merged.get("counts", {}))
                    for k, v in local.get("counts", {}).items():
                        counts[k] = counts.get(k, 0) + v
                    merged["counts"] = counts
                else:
                    items = list(merged.get(key, []))
                    existing_ids = {it.get("id") for it in items if isinstance(it, dict) and it.get("id")}
                    for it in local.get(key, []):
                        it_id = it.get("id") if isinstance(it, dict) else None
                        if it_id and it_id in existing_ids:
                            continue
                        if it not in items:
                            items.append(it)
                            if it_id:
                                existing_ids.add(it_id)
                    if name == "custom_recipes.json":
                        items = items[:50]
                    merged[key] = items
                db_store.write(name, merged)
            # 迁移后清空本机档案，避免下次重复累加
            file_store.write("preferences.json", {})
            file_store.write("good_recipes.json", {})
            file_store.write("bad_cases.json", {})
            file_store.write("custom_recipes.json", {})
            local_ep = file_store.read("ear_profile.json")
            remote_ep = db_store.read("ear_profile.json")
            if isinstance(local_ep, dict) and local_ep.get("archetype_id"):
                if not (isinstance(remote_ep, dict) and remote_ep.get("archetype_id")):
                    db_store.write("ear_profile.json", local_ep)
                file_store.write("ear_profile.json", {})
            self.send_json({"ok": True, "message": "档案已迁移到账号"})

        elif path == "/api/agent_chat":
            data = read_body(self)
            say = str(data.get("say") or "").strip()[:300]
            if not say:
                self.send_json({"error": "说说你此刻想要什么声音吧"}, 400)
                return
            try:
                seconds = max(5, min(60, int(data.get("seconds", 30) or 30)))
            except (TypeError, ValueError):
                seconds = 30

            clean_current = map_client_tracks(data.get("current_tracks") or [])
            current_for_brain = [{
                "path": os.path.basename(t["rel"]),
                "weight": round(t["weight"], 2),
                "pan": round(t["pan"], 2),
                "mode": t["mode"],
                "density": round(t["density"], 2),
            } for t in clean_current]

            raw_hist = data.get("history")
            clean_hist = []
            if isinstance(raw_hist, list):
                for h in raw_hist[-6:]:
                    if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
                        txt = str(h.get("content") or "").strip()[:300]
                        if txt:
                            clean_hist.append({"role": h["role"], "content": txt})

            initial_prompt = str(data.get("initial_prompt") or "").strip()[:300]
            try:
                qa_round = max(0, min(5, int(data.get("qa_round", 0) or 0)))
            except (TypeError, ValueError):
                qa_round = 0
            force_compose = bool(data.get("force_compose", False))

            ctx = _get_user_agent_context(current_user(self))
            used_profile = ""
            if isinstance(ctx.get("ear_profile"), dict):
                used_profile = str(ctx["ear_profile"].get("archetype_name") or "")

            design, source = understanding_brain.design_soundscape(
                say,
                current_tracks=current_for_brain,
                history=clean_hist,
                user_context=ctx,
                qa_round=qa_round,
                force_compose=force_compose,
                initial_prompt=initial_prompt,
            )

            ai_powered = source in ("Qwen3.8-Flash", "本地模型")

            if design.get("action") == "ask":
                self.send_json({
                    "ok": True,
                    "action": "ask",
                    "source": source,
                    "ai_powered": ai_powered,
                    "reply": design.get("reply", ""),
                    "question": design.get("question", ""),
                    "options": design.get("options", []),
                    "collected": design.get("collected", {}),
                    "intent": design.get("intent", {}),
                    "reasoning": design.get("reasoning", []),
                    "tracks": [],
                    "used_profile": used_profile,
                })
                return

            role_notes = {}
            for raw_t in design.get("tracks") or []:
                if isinstance(raw_t, dict) and raw_t.get("path"):
                    role_notes[os.path.basename(str(raw_t["path"]))] = str(raw_t.get("role_note") or "")

            mapped_tracks = map_client_tracks(design.get("tracks") or [])
            if not mapped_tracks:
                fallback_rel = find_relpath("母带_城市夜雨_CC0.mp3")
                if fallback_rel:
                    mapped_tracks = [_normalize_track_spec({"rel": fallback_rel, "weight": 0.72})]

            mix, sr = render(mapped_tracks, seconds)
            self.server.last_audio = (mix, sr)

            session["intent"] = design["intent"]
            session["items"] = [(t["rel"], t["weight"]) for t in mapped_tracks]
            session["say"] = design.get("final_prompt") or say

            resp_tracks = []
            for t in mapped_tracks:
                base = os.path.basename(t["rel"])
                resp_tracks.append({
                    "path": base,
                    "weight": round(t["weight"], 2),
                    "pan": round(t["pan"], 2),
                    "mode": t["mode"],
                    "density": round(t["density"], 2),
                    "role_note": role_notes.get(base, ""),
                })

            self.send_json({
                "ok": True,
                "action": "compose",
                "source": source,
                "ai_powered": ai_powered,
                "title": design["title"],
                "reply": design["reply"],
                "final_prompt": design.get("final_prompt", ""),
                "collected": design.get("collected", {}),
                "intent": design["intent"],
                "reasoning": design["reasoning"],
                "tracks": resp_tracks,
                "followups": design["followups"],
                "used_profile": used_profile,
                "audio": "/api/audio",
            })

        elif path == "/api/generate":
            data = read_body(self)
            say = data.get("say", "")
            seconds = int(data.get("seconds", 30))
            if not say:
                self.send_json({"error": "空需求"}, 400)
                return

            intent, source = understanding_brain.understand(say)
            items = executor.pick(intent)
            session["intent"] = intent
            session["items"] = items
            session["say"] = say
            mix, sr = render(items, seconds)

            self.send_json({
                "source": source,
                "ai_powered": source in ("Qwen3.8-Flash", "本地模型"),
                "scene": intent["scene"],
                "scene_detail": intent["scene_detail"],
                "mood": intent["mood"],
                "warmth": intent["warmth"],
                "dynamics": intent["dynamics"],
                "avoid": intent.get("avoid", []),
                "items": [{"path": os.path.basename(p), "weight": round(w, 2)}
                          for p, w in items if w > 0],
                "audio": "/api/audio"
            })
            # 把当前音频缓存到内存，供 /api/audio 取
            self.server.last_audio = (mix, sr)

        elif path == "/api/preview":
            # 社区配方试听：直接给配比，不调 Qwen
            data = read_body(self)
            seconds = int(data.get("seconds", 20))
            items = map_client_tracks(data.get("items", []))
            if not items:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            mix, sr = render(items, seconds)
            self.server.preview_audio = (mix, sr)
            self.send_json({"ok": True, "audio": "/api/preview_audio"})

        elif path == "/api/play":
            # 场景卡/播放页：按预设配方直接出声，不调 Qwen、不依赖 key
            data = read_body(self)
            seconds = int(data.get("seconds", PLAY_SECONDS))
            items = map_client_tracks(data.get("items", []))
            if not items:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            name, _ = play_file(items, seconds)
            shown = data.get("title", "夜息")
            self.send_json({
                "ok": True,
                "name": name,
                "audio": "/api/play_audio?name=" + name,
                "title": shown,
                "items": [{
                    "path": os.path.basename(t["rel"]),
                    "weight": round(t["weight"], 2),
                    "pan": round(t["pan"], 2),
                    "mode": t["mode"],
                    "density": round(t["density"], 2),
                } for t in items if t["weight"] > 0]
            })

        elif path == "/api/recipes":
            data = read_body(self)
            raw_tracks = data.get("tracks")
            if raw_tracks is None:
                raw_tracks = data.get("items", [])
            tracks = map_client_tracks(raw_tracks)
            if not tracks:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            title = str(data.get("title") or "我的夜息配方").strip()[:40] or "我的夜息配方"
            rid = str(data.get("id") or "").strip()[:32]
            store = _recipe_store(current_user(self))
            data_obj = store.read("custom_recipes.json")
            recipes = list(data_obj.get("recipes", [])) if isinstance(data_obj, dict) and isinstance(data_obj.get("recipes"), list) else []
            clean_tracks = [{
                "path": os.path.basename(t["rel"]),
                "weight": round(t["weight"], 3),
                "pan": round(t["pan"], 3),
                "mode": t["mode"],
                "density": round(t["density"], 3),
            } for t in tracks]
            now = int(time.time())
            saved = None
            if rid:
                for idx, old in enumerate(recipes):
                    if isinstance(old, dict) and old.get("id") == rid:
                        saved = {
                            "id": rid,
                            "title": title,
                            "tracks": clean_tracks,
                            "created_at": old.get("created_at", now),
                            "updated_at": now,
                        }
                        recipes[idx] = saved
                        break
            if saved is None:
                rid = secrets.token_hex(6)
                saved = {
                    "id": rid,
                    "title": title,
                    "tracks": clean_tracks,
                    "created_at": now,
                    "updated_at": now,
                }
                recipes.insert(0, saved)
            recipes = recipes[:50]
            store.write("custom_recipes.json", {"recipes": recipes})
            self.send_json({"ok": True, "recipe": saved, "recipes": recipes})

        elif path == "/api/recipes/delete":
            data = read_body(self)
            rid = str(data.get("id") or "").strip()
            store = _recipe_store(current_user(self))
            data_obj = store.read("custom_recipes.json")
            old_list = data_obj.get("recipes", []) if isinstance(data_obj, dict) else []
            recipes = [r for r in old_list if isinstance(r, dict) and r.get("id") != rid]
            store.write("custom_recipes.json", {"recipes": recipes})
            self.send_json({"ok": True, "recipes": recipes})

        elif path == "/api/community_vote":
            data = read_body(self)
            recipe_id = str(data.get("recipe_id") or "").strip()
            tag = str(data.get("tag") or "").strip()
            if not recipe_id or len(recipe_id) > 32 or not re.match(r"^[A-Za-z0-9_-]+$", recipe_id):
                self.send_json({"error": "无效配方编号"}, 400)
                return
            if tag not in ALLOWED_EVAL_TAGS:
                self.send_json({"error": "无效评价标签"}, 400)
                return
            try:
                delta = int(data.get("delta", 1))
            except (TypeError, ValueError):
                delta = 1
            if delta not in (1, -1):
                delta = 1
            votes = _read_community_votes()
            raw_entry = votes.get(recipe_id) if isinstance(votes.get(recipe_id), dict) else {}
            entry = {k: max(0, int(raw_entry.get(k, 0))) for k in ALLOWED_EVAL_TAGS}
            entry[tag] = max(0, entry[tag] + delta)
            votes[recipe_id] = entry
            _write_community_votes(votes)
            self.send_json({"ok": True, "recipe_id": recipe_id, "counts": entry})

        elif path == "/api/community_posts":
            data = read_body(self)
            raw_tracks = data.get("tracks")
            if raw_tracks is None:
                raw_tracks = data.get("items", [])
            tracks = map_client_tracks(raw_tracks)
            if not tracks:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return

            user = current_user(self)
            author = user["username"] if user else (str(data.get("author_name") or "").strip()[:20] or "深夜旅人")
            title = str(data.get("title") or "我的夜息声景").strip()[:36] or "我的夜息声景"
            story = str(data.get("story") or "").strip()[:120]

            remix_raw = data.get("remix_of")
            remix_of = None
            if isinstance(remix_raw, dict) and str(remix_raw.get("title") or "").strip():
                remix_of = {
                    "id": str(remix_raw.get("id") or "").strip()[:32],
                    "title": str(remix_raw.get("title") or "").strip()[:36],
                    "author": str(remix_raw.get("author") or "夜息").strip()[:24] or "夜息",
                }

            clean_tracks = [{
                "path": os.path.basename(t["rel"]),
                "weight": round(t["weight"], 3),
                "pan": round(t["pan"], 3),
                "mode": t["mode"],
                "density": round(t["density"], 3),
            } for t in tracks]

            post_id = "u_" + secrets.token_hex(5)
            delete_token = secrets.token_hex(8)
            post = {
                "id": post_id,
                "title": title,
                "author": author,
                "user_id": user["id"] if user else None,
                "group": _infer_post_group(tracks),
                "story": story,
                "remix_of": remix_of,
                "items": clean_tracks,
                "created_at": int(time.time()),
                "delete_token": delete_token,
            }

            posts = _read_community_posts()
            posts.insert(0, post)
            _write_community_posts(posts[:100])
            self.send_json({
                "ok": True,
                "post": _public_post(post),
                "delete_token": delete_token,
            })

        elif path == "/api/community_posts/delete":
            data = read_body(self)
            pid = str(data.get("id") or "").strip()
            dtok = str(data.get("delete_token") or "").strip()
            user = current_user(self)
            posts = _read_community_posts()
            target = None
            for p in posts:
                if p.get("id") == pid:
                    target = p
                    break
            if not target:
                self.send_json({"error": "配方不存在"}, 404)
                return

            owner_ok = bool(user and target.get("user_id") and user["id"] == target.get("user_id"))
            token_ok = bool(dtok and target.get("delete_token") and secrets.compare_digest(dtok, str(target.get("delete_token"))))
            if not (owner_ok or token_ok):
                self.send_json({"error": "没有删除权限"}, 403)
                return

            next_posts = [p for p in posts if p.get("id") != pid]
            _write_community_posts(next_posts)
            self.send_json({"ok": True})

        elif path == "/api/export_commercial":
            import io
            data = read_body(self)
            raw_tracks = data.get("items")
            if raw_tracks is None:
                raw_tracks = data.get("tracks", [])
            items = map_client_tracks(raw_tracks)
            if not items:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            try:
                sec = int(data.get("seconds", 30))
            except (TypeError, ValueError):
                sec = 30
            if sec not in (30, 180, 300):
                sec = 30

            mix, sr = render(items, sec)
            buf = io.BytesIO()
            executor.write_wav(buf, mix, sr)
            body = buf.getvalue()
            cert_id = "YX-CC0-" + time.strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper()

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", "X-Yexi-Cert-Id")
            self.send_header("X-Yexi-Cert-Id", cert_id)
            self.send_header("Content-Disposition", 'attachment; filename="yexi_commercial.wav"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/ear_profile":
            data = read_body(self)
            arch_id = str(data.get("archetype_id") or "").strip()
            if not arch_id or not re.match(r"^[A-Za-z0-9_-]{1,32}$", arch_id):
                self.send_json({"error": "无效耳朵档案编号"}, 400)
                return
            tracks = map_client_tracks(data.get("tracks") or [])
            if not tracks:
                self.send_json({"error": "档案缺少可用声轨"}, 400)
                return

            raw_scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
            clean_scores = {}
            for sk in ("warmth", "crisp", "space", "nature"):
                try:
                    sv = int(round(float(raw_scores.get(sk, 50))))
                except (TypeError, ValueError):
                    sv = 50
                clean_scores[sk] = max(0, min(100, sv))

            raw_intent = data.get("intent") if isinstance(data.get("intent"), dict) else {}
            clean_intent = {
                "scene": str(raw_intent.get("scene") or "rain")[:24],
                "mood": str(raw_intent.get("mood") or "sleep")[:24],
                "warmth": str(raw_intent.get("warmth") or "warm")[:24],
                "dynamics": str(raw_intent.get("dynamics") or "steady")[:24],
            }

            clean_tracks = [{
                "path": os.path.basename(t["rel"]),
                "weight": round(t["weight"], 3),
                "pan": round(t["pan"], 3),
                "mode": t["mode"],
                "density": round(t["density"], 3),
            } for t in tracks]

            profile = {
                "archetype_id": arch_id,
                "archetype_name": str(data.get("archetype_name") or "夜息聆听者").strip()[:24],
                "tagline": str(data.get("tagline") or "").strip()[:80],
                "icon": str(data.get("icon") or "☾").strip()[:8],
                "scores": clean_scores,
                "intent": clean_intent,
                "tracks": clean_tracks,
                "prompt": str(data.get("prompt") or "").strip()[:100],
                "updated_at": int(time.time()),
            }

            store = _recipe_store(current_user(self))
            store.write("ear_profile.json", profile)
            memory.save_preferences(clean_intent, store)
            self.send_json({"ok": True, "ear_profile": profile})

        elif path == "/api/feedback":
            data = read_body(self)
            fb = data.get("feedback", "")
            seconds = int(data.get("seconds", 30))
            items = session["items"]
            intent = session["intent"] or {}

            # 登录用户存自己的库，游客存本机；记忆按人隔离
            user = current_user(self)
            store = memory.DbStore(user["id"]) if user else memory.FileStore()

            say_text = session["say"] or str(data.get("say", ""))

            if fb in ("满意", "", "like"):
                mapped = map_client_items(data.get("items"))
                saved_items = mapped if mapped else items
                memory.save_preferences(intent, store)
                memory.save_good_recipe(say_text, intent,
                                        [[p, round(w, 3)] for p, w in saved_items], store)
                self.send_json({"ok": True, "saved": "good"})
                return

            if not items:
                items = map_client_items(data.get("items"))
            if not items:
                self.send_json({"error": "还没有可调整的声轨"}, 400)
                return

            memory.save_bad_case(say_text, fb,
                                 [[p, round(w, 3)] for p, w in items], store)
            new_items, notes = ft.apply_feedback(fb, items)
            session["items"] = new_items
            mix, sr = render(new_items, seconds)
            self.server.last_audio = (mix, sr)

            self.send_json({
                "ok": True,
                "notes": notes,
                "items": [{"path": os.path.basename(p), "weight": round(w, 2)}
                          for p, w in new_items if w > 0],
                "audio": "/api/audio"
            })

        else:
            self.send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        # 安静一点，只打印关键行
        pass


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(PLAY_DIR, exist_ok=True)
    # 部署平台要求监听 0.0.0.0，本机开发这样也能访问
    print("夜息已启动：http://0.0.0.0:" + str(PORT), flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
