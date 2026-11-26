# 轻量后端 API + 静态页面：一个端口同时服务前后端
# key 只在这个文件所在的服务端读取，绝不发给浏览器
# 只用标准库 http.server，不装 Flask

import gzip
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
import sound_catalog
import 素材执行层 as executor
import feedback_translate as ft
import memory_system as memory
import auth_db
import rate_limit
import input_guard
import pay
import nowpay

# 部署平台通过 PORT 环境变量注入端口，本机开发默认 8000
PORT = int(os.environ.get("PORT", "8000"))
BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "agent_output")
SITE_DIR = os.path.join(BASE, "product_site")


def _hotlink_blocked(handler):
    """防盗链：只拦「明确来自外站」的图片/音频请求，不确定的一律放行。
    原则（依据 MDN + 本项目 Referrer-Policy）：
      - 没有 Referer：放行（可能是用户直接打开、或浏览器隐私设置主动省略）
      - 本机/本地开发：放行
      - Referer 的 host 和请求 host 一致（同源）：放行
      - 明确是别的网站：拦截（这就是白嫖带宽的盗链）
    注意：curl 可以伪造 Referer，所以这层只防浏览器里的普通盗链，
    防不住蓄意下载——CC0 音频本来也允许下载，目标只是别让别人网页白嫖带宽。
    """
    ref = (handler.headers.get("Referer") or "").strip()
    if not ref:
        return False
    try:
        ref_host = urllib.parse.urlparse(ref).hostname or ""
    except Exception:
        return False  # 解析不了就放行，宁可漏拦也不误伤
    if not ref_host:
        return False

    # 本机/本地开发白名单
    if ref_host in ("localhost", "127.0.0.1", "::1"):
        return False

    # 和请求目标 host 一致 = 同源，放行
    req_host = (handler.headers.get("Host") or "").split(":")[0].strip().lower()
    if ref_host.lower() == req_host:
        return False

    # 到这里仍是外站 Referer，但可能是我们自己的公网域名/IP（从 GitHub 部署手册看是 IP 访问）
    # 若 ref_host 就是请求 host 的另一种写法，也放行——上面已覆盖大多数情况
    return True


def serve_static(handler, path):
    # 只服务 product_site 里的文件；API 路径不在这里处理。
    # 拆出查询串（?v=12 这类版本号），缓存策略要看它。
    # 注意：调用方传进来的 path 已经被 urlparse 剥过查询串了，
    # 所以这里要从 handler.path 取原始的完整地址。
    clean_path, _, query = handler.path.partition("?")
    if clean_path == "/" or clean_path == "":
        clean_path = "/home.html"
    rel = urllib.parse.unquote(clean_path).lstrip("/")
    full = os.path.normpath(os.path.join(SITE_DIR, rel))
    # 防路径穿越：解析后必须仍在 SITE_DIR 里面
    if not full.startswith(os.path.abspath(SITE_DIR) + os.sep):
        handler.send_json({"error": "forbidden"}, 403)
        return
    if not os.path.isfile(full):
        handler.send_json({"error": "not found"}, 404)
        return
    # 防盗链：只拦图片/音频这类"值得偷"的静态资源，HTML/CSS/JS 不拦
    # （页面本身要能被正常链接、被搜索引擎/微信抓取预览）
    if full.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp3", ".wav", ".ogg")):
        if _hotlink_blocked(handler):
            handler.send_json({"error": "forbidden"}, 403)
            return
    # 图片自动转 WebP（内容协商）：浏览器说支持 image/webp 且磁盘上有同名 .webp，
    # 就发 WebP，体积比 JPG 省 40% 左右；不支持的浏览器照拿原 JPG，不用改一行前端代码。
    # 转换脚本见 make_webp.py，改过原图后重跑一次即可。
    accept_encoding = handler.headers.get("Accept-Encoding", "")
    accept_type = handler.headers.get("Accept", "")
    want_webp = "image/webp" in accept_type and full.lower().endswith(
        (".jpg", ".jpeg", ".png")
    )
    webp_path = os.path.splitext(full)[0] + ".webp"
    if want_webp and os.path.isfile(webp_path):
        full = webp_path

    with open(full, "rb") as f:
        body = f.read()
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    is_text = (
        ctype.startswith("text/")
        or "javascript" in ctype
        or "json" in ctype
        or "svg" in ctype
        or "xml" in ctype
    )
    if is_text and "charset=" not in ctype:
        ctype += "; charset=utf-8"

    # gzip：文本类资源压缩后再发，体积通常能省 60%~75%。
    # 图片/音频本身已是压缩格式，不再压。客户端不支持就原样发。
    if is_text and "gzip" in accept_encoding and len(body) > 512:
        body = gzip.compress(body, compresslevel=6)
        gzipped = True
    else:
        gzipped = False

    # 缓存策略：
    # - HTML 会随功能更新，短缓存（5 分钟），改版后最多等 5 分钟生效
    # - 带 ?v= 版本号的 css/js 内容不会变，长缓存一年，改版靠换版本号
    # - 其他图片/json 一小时
    is_html = clean_path.endswith(".html") or clean_path == "/"
    if is_html:
        cache = "public, max-age=300"
    elif query:
        cache = "public, max-age=31536000, immutable"
    else:
        cache = "public, max-age=3600"

    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", cache)
    # Vary 两个头都发：gzip 版/原始版、WebP 版/JPG 版不能缓存串味
    handler.send_header("Vary", "Accept, Accept-Encoding")
    if gzipped:
        handler.send_header("Content-Encoding", "gzip")
    handler.end_headers()
    handler.wfile.write(body)


def read_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw)


def read_form(handler):
    # 支付宝的异步通知是表单编码（application/x-www-form-urlencoded），不是 JSON
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
    return {k: v[0] for k, v in parsed.items()}


def send_text(handler, text, code=200):
    body = text.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def current_user(handler):
    # 从 Authorization: Bearer <token> 识别登录用户，未登录返回 None（游客）
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth_db.user_from_token(auth[7:].strip())


def get_token(handler):
    auth = handler.headers.get("Authorization", "")
    return auth[7:].strip() if auth.startswith("Bearer ") else ""


# 游客模式边界：这类操作会写公共内容或用到身份，游客一律拦下。
# 返回 user（已登录）或 None（已回 401，调用方直接 return）。
# 只挡写操作，不影响听声/打分/本地存档这些核心体验。
def require_login(handler, what):
    user = current_user(handler)
    if not user:
        self_send_need_login(handler, what)
        return None
    return user


def self_send_need_login(handler, what):
    handler.send_json(
        {"error": "登录后才能" + what + "，游客可以先听听看", "need_login": True}, 401
    )


def get_user_memory(user):
    # 登录用户从数据库读记忆；游客读本地 JSON
    store = _recipe_store(user)
    ep = store.read("ear_profile.json")
    ear_profile = ep if isinstance(ep, dict) and ep.get("archetype_id") else None
    if user:
        # 键名要和 memory_system 写入时一致，都带 .json，否则读出来永远是空
        return {
            "preferences": auth_db.load_memory(user["id"], "preferences.json").get(
                "counts", {}
            ),
            "good_count": len(
                auth_db.load_memory(user["id"], "good_recipes.json").get("recipes", [])
            ),
            "bad_count": len(
                auth_db.load_memory(user["id"], "bad_cases.json").get("cases", [])
            ),
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


def _good_recipes_store(user):
    """AI 配声收藏存在 good_recipes.json；登录用户走数据库，游客走本机。"""
    return memory.DbStore(user["id"]) if user else memory.FileStore()


def _normalize_good_items(items):
    """把 [[path, weight], ...] 或 [{path, weight...}] 统一成前端要的对象格式。"""
    out = []
    for it in items or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            name = os.path.basename(str(it[0]))
            weight = it[1]
            out.append(
                {
                    "path": name,
                    "weight": round(float(weight), 3),
                    "pan": 0,
                    "mode": "loop",
                    "density": 0.4,
                }
            )
        elif isinstance(it, dict) and it.get("path"):
            out.append(
                {
                    "path": os.path.basename(str(it["path"])),
                    "weight": round(float(it.get("weight", 0.5)), 3),
                    "pan": float(it.get("pan", 0)),
                    "mode": it.get("mode", "loop"),
                    "density": float(it.get("density", 0.4)),
                }
            )
    return out


def _list_good_recipes(user, limit=20):
    """把 AI 配声里收藏过的配方列出来，供"我的"页展示。
    每条带一个稳定 key（内容哈希），用于删除。"""
    store = _good_recipes_store(user)
    obj = store.read("good_recipes.json")
    recipes = obj.get("recipes", []) if isinstance(obj, dict) else []
    if not isinstance(recipes, list):
        return []
    out = []
    for idx, r in enumerate(recipes[-limit:]):
        if not isinstance(r, dict):
            continue
        items = _normalize_good_items(r.get("items"))
        if not items:
            continue
        say = str(r.get("say") or "").strip()
        key_src = (
            say + "|" + ",".join(i["path"] + ":" + str(i["weight"]) for i in items)
        )
        key = hashlib.sha1(key_src.encode("utf-8")).hexdigest()[:12]
        out.append(
            {
                "key": key,
                "title": say[:36] or "AI 配的一段夜色",
                "say": say,
                "scene": r.get("scene") or "",
                "items": items,
            }
        )
    # 最近收藏的排前面
    out.reverse()
    return out


def _extract_track_names(items):
    names = []
    if not isinstance(items, list):
        return names
    for it in items:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            p, w = it[0], it[1]
            try:
                if float(w) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            bn = os.path.basename(str(p or "").strip())
            if bn:
                names.append(bn)
        elif isinstance(it, dict):
            p = it.get("path") or it.get("rel") or ""
            try:
                if float(it.get("weight", 1.0)) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            bn = os.path.basename(str(p).strip())
            if bn:
                names.append(bn)
    return names


def _get_user_agent_context(user):
    # 为多轮 Agent 提取耳朵档案、口味统计、满意配方与历史避雷（均带 .json 后缀）
    store = _recipe_store(user)
    ep = store.read("ear_profile.json")
    pref = store.read("preferences.json")
    bad = store.read("bad_cases.json")
    good = store.read("good_recipes.json")

    ctx = {}
    if isinstance(ep, dict) and ep.get("archetype_id"):
        ctx["ear_profile"] = {
            "archetype_name": ep.get("archetype_name", ""),
            "tagline": ep.get("tagline", ""),
            "scores": ep.get("scores", {}),
            "intent": ep.get("intent", {}),
        }
    if (
        isinstance(pref, dict)
        and isinstance(pref.get("counts"), dict)
        and pref["counts"]
    ):
        ctx["preferences"] = pref["counts"]
    if isinstance(bad, dict) and isinstance(bad.get("cases"), list) and bad["cases"]:
        ctx["bad_feedbacks"] = [
            str(c.get("feedback") or "")
            for c in bad["cases"][-5:]
            if isinstance(c, dict) and c.get("feedback")
        ]
        avoid_tracks = []
        seen_avoid = set()
        for c in bad["cases"][-10:]:
            if not isinstance(c, dict):
                continue
            for fn in _extract_track_names(c.get("items")):
                if fn not in seen_avoid:
                    seen_avoid.add(fn)
                    avoid_tracks.append(fn)
        if avoid_tracks:
            ctx["avoid_tracks"] = avoid_tracks[:12]
    if (
        isinstance(good, dict)
        and isinstance(good.get("recipes"), list)
        and good["recipes"]
    ):
        good_list = []
        for r in good["recipes"][-3:]:
            if not isinstance(r, dict):
                continue
            good_list.append(
                {
                    "say": str(r.get("say") or "")[:60],
                    "scene": str(r.get("scene") or ""),
                    "tracks": _extract_track_names(r.get("items")),
                }
            )
        if good_list:
            ctx["good_recipes"] = good_list
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
    # 按 0.25s 分块测有效 RMS，忽略近静音块，对齐到柔和睡前基准 (-32 dBFS / 0.025) 并保护峰值不削波
    import numpy as np

    if len(seg) == 0:
        return 1.0
    block = max(1, int(sr * 0.25))
    usable = (len(seg) // block) * block
    if usable >= block:
        blocks = seg[:usable].reshape(-1, block, 2)
        rms_vals = np.sqrt(np.mean(blocks**2, axis=(1, 2)))
    else:
        rms_vals = np.array([float(np.sqrt(np.mean(seg**2)))], dtype="float32")
    active = rms_vals[rms_vals >= 0.0002]
    if len(active) == 0:
        active_rms = float(np.sqrt(np.mean(seg**2)))
    else:
        active_rms = float(np.median(active))
    if active_rms <= 1e-6:
        return 1.0
    gain = _clamp(0.025 / active_rms, 0.20, 20.0)
    peak = float(np.max(np.abs(seg)))
    if peak > 1e-6 and peak * gain > 0.85:
        gain = max(0.20, 0.85 / peak)
    return gain


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
        chunk = data[idx * bucket_len : (idx + 1) * bucket_len]
        bucket_rms.append(float(np.sqrt(np.mean(chunk**2))))
    med_rms = float(np.median(bucket_rms)) if bucket_rms else 0.0
    active_starts = [
        i * bucket_len
        for i, r in enumerate(bucket_rms)
        if r >= max(0.002, med_rms * 0.65)
    ]
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
            seg = data[src_start : src_start + actual_len].copy()
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

        out[pos : pos + actual_len] += seg
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

    mix_rms = float(np.sqrt(np.mean(mix**2))) if len(mix) > 0 else 0.0
    if mix_rms > 1e-6:
        mix_gain = _clamp(0.025 / mix_rms, 0.25, 4.0)
        mix_peak = float(np.max(np.abs(mix)))
        if mix_peak > 1e-6 and mix_peak * mix_gain > 0.85:
            mix_gain = max(0.20, 0.85 / mix_peak)
        mix = mix * mix_gain

    peak = float(np.max(np.abs(mix))) if len(mix) > 0 else 0.0
    if peak > 0.95:
        mix = mix * (0.95 / peak)
    fi = min(int(sr * 0.5), frames // 2)
    if fi > 0:
        mix[:fi] *= np.linspace(0, 1, fi, dtype="float32")[:, None]
        mix[-fi:] *= np.linspace(1, 0, fi, dtype="float32")[:, None]
    return mix, sr


def find_relpath(name):
    # 给一个文件名，在已验收素材目录（sound_catalog / product_assets / scene_assets）找到它的相对路径（防路径穿越）
    clean = os.path.basename(str(name or "").strip())
    if not clean or clean != str(name or "").strip():
        return ""
    meta = sound_catalog.BY_FILENAME.get(clean)
    if meta:
        return meta["rel_path"]
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
PLAY_SECONDS = 60  # 场景卡/播放页用 60 秒循环基底，前端 loop 播放


def play_file(items, seconds=PLAY_SECONDS):
    # 配方按内容取哈希做文件名：同样的配比复用同一个文件
    os.makedirs(PLAY_DIR, exist_ok=True)
    parts = []
    for raw in items:
        spec = _normalize_track_spec(raw)
        base = os.path.basename(spec["rel"])
        if (
            spec["mode"] == "loop"
            and abs(spec["pan"]) < 1e-4
            and abs(spec["density"] - 0.4) < 1e-4
        ):
            parts.append("%s:%.3f" % (base, spec["weight"]))
        else:
            parts.append(
                "%s:%.3f:%.2f:%s:%.2f"
                % (base, spec["weight"], spec["pan"], spec["mode"], spec["density"])
            )
    key = "v2|" + "|".join(parts)
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


def map_client_tracks(raw_items, allowed=None):
    # 把前端传入的声轨列表（含 weight / pan / mode / density）映射并校验到白名单
    # allowed 不是 None 时，越权的素材直接丢掉（免费用户拿不到付费层）
    if not isinstance(raw_items, list):
        return []
    mapped = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        rel = find_relpath(os.path.basename(str(it.get("path", ""))))
        if not rel:
            continue
        if allowed is not None and rel not in allowed:
            continue
        spec = _normalize_track_spec(
            {
                "rel": rel,
                "weight": it.get("weight", 0),
                "pan": it.get("pan", 0.0),
                "mode": it.get("mode", "loop"),
                "density": it.get("density", 0.4),
            }
        )
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


_BUILTIN_RECIPES = {
    "r1": {
        "title": "窗边夜雨",
        "author": "夜息",
        "items": [
            {
                "path": "母带_城市夜雨_CC0.mp3",
                "weight": 0.6,
                "pan": 0.0,
                "mode": "loop",
                "density": 0.4,
            },
            {
                "path": "柔和雨.hq.mp3",
                "weight": 0.4,
                "pan": -0.2,
                "mode": "loop",
                "density": 0.4,
            },
        ],
    },
    "r2": {
        "title": "雨打树叶",
        "author": "夜息",
        "items": [
            {
                "path": "备选_大雨打树叶_CC0.mp3",
                "weight": 0.7,
                "pan": -0.25,
                "mode": "loop",
                "density": 0.4,
            },
            {
                "path": "母带_城市夜雨_CC0.mp3",
                "weight": 0.3,
                "pan": 0.1,
                "mode": "loop",
                "density": 0.4,
            },
        ],
    },
    "r3": {
        "title": "远海放空",
        "author": "夜息",
        "items": [
            {
                "path": "海浪_远海.hq.mp3",
                "weight": 0.7,
                "pan": 0.0,
                "mode": "loop",
                "density": 0.4,
            },
            {
                "path": "海浪_黑海.hq.mp3",
                "weight": 0.3,
                "pan": -0.22,
                "mode": "loop",
                "density": 0.4,
            },
        ],
    },
    "r4": {
        "title": "夏夜虫鸣",
        "author": "夜息",
        "items": [
            {
                "path": "虫鸣.hq.mp3",
                "weight": 0.5,
                "pan": -0.4,
                "mode": "intermittent",
                "density": 0.55,
            },
            {
                "path": "夜风.hq.mp3",
                "weight": 0.5,
                "pan": 0.35,
                "mode": "loop",
                "density": 0.4,
            },
        ],
    },
    "r5": {
        "title": "山涧溪流",
        "author": "夜息",
        "items": [
            {
                "path": "溪流.hq.mp3",
                "weight": 0.8,
                "pan": -0.16,
                "mode": "loop",
                "density": 0.4,
            },
            {
                "path": "雨中低鸣.hq.mp3",
                "weight": 0.2,
                "pan": 0.16,
                "mode": "loop",
                "density": 0.4,
            },
        ],
    },
    "r6": {
        "title": "雨夜远雷",
        "author": "夜息",
        "items": [
            {
                "path": "母带_城市夜雨_CC0.mp3",
                "weight": 0.7,
                "pan": 0.0,
                "mode": "loop",
                "density": 0.4,
            },
            {
                "path": "远雷.hq.mp3",
                "weight": 0.35,
                "pan": 0.48,
                "mode": "intermittent",
                "density": 0.3,
            },
        ],
    },
}


def _builtin_recipe_items(rid):
    entry = _BUILTIN_RECIPES.get(str(rid or "").strip())
    return entry["items"] if entry else None


def _track_label(path_key):
    base = os.path.basename(str(path_key or ""))
    meta = sound_catalog.BY_FILENAME.get(base)
    if meta and meta.get("name"):
        return meta["name"]
    return os.path.splitext(base)[0]


def _voter_key(handler, user):
    if user and user.get("id"):
        return "u:" + str(user["id"])
    raw = (handler.headers.get("X-Yexi-Client", "") or "").strip()
    if raw and re.match(r"^[A-Za-z0-9_-]{1,40}$", raw):
        return "c:" + raw
    return None


# 免费用户每天能生成几次。付费解锁全库后不限次。
FREE_DAILY_GENERATE = 2


def _nowpay_products_info():
    """给前端看即刻收商品是否可用 + 真实价格（从支付宝 charge.query 读）。
    价格以支付宝后台为准，改完后台前端自动跟上，不用改代码。
    charge.query 失败时降级到 pay.py 里的本地价格，不让页面空白。"""
    products = nowpay.products_config()
    if not products:
        return {"enabled": False, "products": []}
    out = []
    for name, info in products.items():
        price_text = ""
        try:
            q = nowpay.charge_query(name)
            if str(q.get("capability_status", "")) == "ENABLED":
                # 档位列表里取第一个的价格；字段名按官方文档 charging_options
                opts = q.get("charging_options") or []
                if isinstance(opts, list) and opts:
                    # 实测线上返回：{"price": "0.99", "quota_amount": 3, ...}
                    # price 是「元」的字符串，不是分！直接用，不要再除以 100。
                    def _price_of(o):
                        v = (o or {}).get("price")
                        if v is None or v == "":
                            return ""
                        return "%.2f" % float(v)

                    price_text = _price_of(opts[0])
                    # 记下完整档位，将来多档位直接用
                    price_map = []
                    for o in opts:
                        p = _price_of(o)
                        if p:
                            price_map.append({
                                "sku_id": (o or {}).get("sku_id", ""),
                                "price": p,
                                "price_cents": int(round(float(p) * 100)),
                                "quota_amount": (o or {}).get("quota_amount", 0),
                            })
                    out.append({
                        "id": name,
                        "product_id": (info or {}).get("out_product_id", ""),
                        "sku_id": (info or {}).get("sku_id", ""),
                        "price": price_text,
                        "options": price_map,
                    })
                    continue
        except Exception as e:
            print("[nowpay] 查商品价格失败：" + str(e)[:100], flush=True)
        out.append(
            {
                "id": name,
                "product_id": (info or {}).get("out_product_id", ""),
                "sku_id": (info or {}).get("sku_id", ""),
                "price": price_text,
                "options": [],
            }
        )
    return {"enabled": True, "products": out}


def _nowpay_quota(buyer_id):
    """查即刻收的次数余额。没配商品或没启用就返回不可用，不报错给用户。"""
    if not nowpay.ENABLED:
        return {"available": False, "remaining": 0}
    try:
        r = nowpay.quota_query(buyer_id, "trial3")
    except Exception as e:
        print("[nowpay] 查余额失败：" + str(e), flush=True)
        return {"available": False, "remaining": 0, "error": str(e)}
    if str(r.get("code", "")) != "10000":
        return {"available": False, "remaining": 0}
    return {
        "available": True,
        "total": int(r.get("total", 0) or 0),
        "used": int(r.get("used", 0) or 0),
        "remaining": int(r.get("remaining", 0) or 0),
    }


def _access(handler):
    # 一次算清三件事：有没有解锁全库、额度记在谁头上、当前权益。
    # 全库权益两条来源：① 本地 entitlements（支付宝老流程）；② 即刻收的支付宝托管次数余额。
    # 即刻收的真相源是支付宝那边的余额，不能在本地缓存，所以每次都查。
    user = current_user(handler)
    ent = auth_db.list_entitlements(user["id"]) if user else {}
    full = bool(ent.get("full") and ent["full"].get("active"))
    owner = _voter_key(handler, user) or "c:anon"
    buyer = str(user["id"]) if user else owner
    # 即刻收余额塞进 ent 的副本里（不改原字典），调用方无需改签名
    if not full and nowpay.ENABLED and nowpay.products_config():
        info = _nowpay_quota(buyer)
        if info.get("available") and int(info.get("remaining", 0)) > 0:
            full = True
            ent = dict(ent)
            ent["_nowpay_buyer"] = buyer
    return full, owner, ent


def _nowpay_consume(ent):
    """生成成功后核销一次即刻收次数。
    返回 True 表示已扣或无需扣；False 表示扣失败（次数没扣掉，不拦用户，但要记日志）。
    真相源在支付宝，本地不缓存余额。网络结果不明时用原请求号查，不换号重扣。"""
    buyer = ent.get("_nowpay_buyer") if isinstance(ent, dict) else ""
    if not buyer or not nowpay.ENABLED:
        return True  # 不是即刻收用户（免费/老流程），不用扣
    try:
        r = nowpay.quota_verify(buyer, "trial3", 1, "生成一次助眠音频")
        code = str(r.get("code", ""))
        if code == "10000":
            return True
        # 扣失败也不拦用户——钱已经付了，不能因为核销接口抖动就不让生成。
        # 注意：nowpay.quota_verify 内部生成的 out_request_no 没返回，
        # 所以这里没法用 quota_refresh 按原号复查（那是 nowpay.py 的设计缺口）。
        print("[nowpay] 核销失败：" + str(r.get("sub_msg") or r.get("msg") or code), flush=True)
        return False
    except Exception as e:
        print("[nowpay] 核销异常：" + str(e)[:120], flush=True)
        return False


def _quota_exhausted(handler, quota):
    handler.send_json(
        {
            "ok": False,
            "action": "quota",
            "error": "今天的 " + str(FREE_DAILY_GENERATE) + " 次生成用完了",
            "reply": "今天的免费次数用完了。想再生成，明天还有，或者解锁全库继续。",
            "need_pay": True,
            "quota": quota,
            "products": pay.public_products(),
        },
        402,
    )


def _downgrade_tracks(tracks, intent, allowed):
    # 免费用户：配方里只要混进了付费素材，就整条退到该场景的免费默认组合。
    # 这样不会出现「三层被删成一层」的奇怪声音。
    if not tracks:
        return tracks
    if all(t["rel"] in allowed for t in tracks):
        return tracks
    picked = executor.pick(intent, allowed)
    if not picked:
        return tracks
    total = sum(w for _, w in picked) or 1.0
    out = []
    for rel, w in picked:
        out.append(_normalize_track_spec({"rel": rel, "weight": w / total}))
    return out


def _format_public_post(
    post,
    viewer_user,
    voter_votes,
    fork_counts,
    vote_counts,
    force_unlock=False,
    profiles=None,
):
    pid = post["id"]
    is_mine = bool(
        viewer_user and post.get("user_id") and viewer_user["id"] == post.get("user_id")
    )
    starred_by_me = (pid, "borrow") in voter_votes
    policy = post.get("remix_policy") or "star_to_fork"
    if policy not in auth_db.VALID_REMIX_POLICIES:
        policy = "star_to_fork"
    unlocked = bool(
        force_unlock
        or is_mine
        or policy == "open"
        or (policy == "star_to_fork" and starred_by_me)
    )
    items_raw = post.get("items") or []
    lead_path = os.path.basename(items_raw[0].get("path", "")) if items_raw else ""
    lead_meta = sound_catalog.BY_FILENAME.get(lead_path) if lead_path else None
    raw_counts = vote_counts.get(pid) or {}
    counts = {
        k: max(0, int(raw_counts.get(k, 0) or 0)) for k in auth_db.ALLOWED_VOTE_TAGS
    }

    # 作者头像：有 user_id 且能查到 profile 就用预设头像，否则前端退回首字
    author_profile = None
    if profiles and post.get("user_id") in profiles:
        ap = profiles[post.get("user_id")]
        author_profile = {
            "display_name": ap.get("display_name") or "",
            "avatar_glyph": int(ap.get("avatar_glyph") or 0),
            "avatar_tone": int(ap.get("avatar_tone") or 0),
        }

    out = {
        "id": pid,
        "title": post.get("title") or "我的夜息声景",
        "author": post.get("author") or "深夜旅人",
        "author_profile": author_profile,
        "group": post.get("group") or "自然",
        "story": post.get("story") or "",
        "remix_of": post.get("remix_of"),
        "remix_policy": policy,
        "parent_post_id": post.get("parent_post_id") or "",
        "root_post_id": post.get("root_post_id") or "",
        # 「改了什么」里带着每层的名字和新旧比例，没解锁就不给
        "diff_summary": (post.get("diff_summary") or []) if unlocked else [],
        "version": int(post.get("version") or 1),
        "created_at": post.get("created_at") or 0,
        "fork_count": int(fork_counts.get(pid, 0)),
        "counts": counts,
        "is_mine": is_mine,
        "starred_by_me": starred_by_me,
        "unlocked": unlocked,
        "track_count": len(items_raw),
        # 配比没解锁时，连"打底的是哪段素材"也不给，只给封面图和主色（够渲染卡片）
        "lead_path": lead_path if unlocked else "",
        "cover_img": (lead_meta or {}).get("img") or "",
        "cover_accent": (lead_meta or {}).get("accent") or "",
        "items": items_raw if unlocked else [],
        "items_locked": not unlocked,
    }
    return out


def _ensure_community_db():
    auth_db.init_db()
    auth_db.migrate_legacy_community(_read_community_posts(), _read_community_votes())


_ensure_community_db()


def _infer_post_group(tracks):
    if not tracks:
        return "自然"
    lead = max(tracks, key=lambda t: t.get("weight", 0))
    name = os.path.basename(lead.get("rel", ""))
    meta = sound_catalog.BY_FILENAME.get(name)
    if meta:
        grp = meta.get("group", "自然")
        if grp in ("雨声", "海浪", "炉火", "ASMR", "自然"):
            return grp
        return "自然"
    return "雨声" if "雨" in name else "自然"


# 每个会话的当前状态（演示版：只存一份，够单机用）
session = {"intent": None, "items": [], "say": ""}


# CORS 白名单：只有这些来源能跨域调 API。
# 正常访问走同源（前端和 API 同一个 server.py），根本不需要 CORS 头。
# 只放行本地开发的 8080 端口；线上若换域名，在这里加一条即可。
CORS_ALLOWED_ORIGINS = {
    "http://localhost:8080",
    "http://127.0.0.1:8080",
}


class Handler(BaseHTTPRequestHandler):
    def send_response(self, code, message=None):
        """覆盖基类：所有响应统一带安全头，一处改完全局生效。
        注意：send_response 之后、end_headers 之前是加头的正确时机。"""
        super().send_response(code, message)
        # 阻止浏览器猜测文件类型（把 JSON 当 JS 执行这类攻击）
        self.send_header("X-Content-Type-Options", "nosniff")
        # 只允许同源 iframe（m.html 手机入口就是 iframe 套真实页面）；外部站点嵌套仍被拦
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        # 跳转时不把完整 URL 带给外部站点
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        # 限制资源加载来源。项目页面全靠内联 script/style，所以允许 unsafe-inline；
        # 外链资源为 0，其余一律只允许本站，这是当前形态能设的最严策略。
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "script-src-attr 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )
        # HSTS 只在 HTTPS 下加——HTTP 上加了会被忽略，备案/证书到位后自动生效
        if self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            self.send_header(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

    def send_cors_headers(self):
        """按白名单回 CORS 头。不在白名单就不回——浏览器会自动拦跨域请求。"""
        origin = (self.headers.get("Origin") or "").strip()
        if not origin:
            # 同源请求不带 Origin，不需要 CORS 头，正常放行
            return
        if origin in CORS_ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-Yexi-Client",
            )
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def check_rate_limit(self, path):
        """全局限流：只管 /api/，静态页面和音频文件不限速。
        支付宝 notify 回调要放行——它的服务器 IP 不固定，限流会误伤真实付款。"""
        if not path.startswith("/api/"):
            return True
        if path == "/api/pay/notify":
            return True
        ok, cat, left = rate_limit.check(path, self)
        if not ok:
            self.send_json(
                {
                    "error": "操作太频繁了，稍等一会儿再试",
                    "need_slow_down": True,
                },
                429,
            )
            return False
        return True

    def send_audio(self, data, sr):
        # 防盗链：实时生成的音频也不给外站白嫖带宽（检查逻辑见 _hotlink_blocked）
        if _hotlink_blocked(self):
            self.send_json({"error": "forbidden"}, 403)
            return
        # 在线播放发 MP3：30 秒从 5.3MB 降到约 0.5MB，手机公网加载快一个数量级
        # 导出商用仍走 write_wav 保留无损，不受这里影响
        import io

        buf = io.BytesIO()
        fmt = executor.write_mp3(buf, data, sr)
        body = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg" if fmt == "mp3" else "audio/wav")
        self.send_cors_headers()
        self.send_header("Accept-Ranges", "none")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # 预检请求：只在白名单来源时回 CORS 头，其它来源浏览器自己会拦
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        print("[GET] " + path, flush=True)
        if not self.check_rate_limit(path):
            return
        if path == "/api/pay/products":
            np_info = _nowpay_products_info()
            if nowpay.ENABLED and np_info["enabled"]:
                # 即刻收模式：只显示支付宝那边真实建好的商品，避免点了付不了
                all_products = pay.public_products()
                live = dict((p["id"], p) for p in np_info["products"])
                shown = []
                for p in all_products:
                    if p["id"] not in live:
                        continue
                    p = dict(p)  # 不改原字典
                    real_price = live[p["id"]].get("price") or ""
                    if real_price:
                        p["price"] = real_price
                        p["price_cents"] = int(round(float(real_price) * 100))
                    shown.append(p)
                self.send_json(
                    {
                        "products": shown,
                        "mode": "nowpay",
                        "configured": True,
                        "nowpay": np_info,
                    }
                )
                return
            self.send_json(
                {
                    "products": pay.public_products(),
                    "mode": pay.PAY_MODE,
                    "configured": pay.configured(),
                    "nowpay": np_info,
                }
            )
        elif path == "/api/nowpay/return":
            # 即刻收购买页跳回：这里只做展示，真实权益由前端查 quota 确认
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self.send_response(302)
            self.send_header(
                "Location",
                "/pay_return.html?nowpay=1"
                + ("&product=" + urllib.parse.quote(qs.get("product", [""])[0])),
            )
            self.end_headers()
        elif path == "/api/nowpay/trade-no":
            # 查最近一笔购买的支付宝交易号——比赛提交表单要填这个
            user = current_user(self)
            if not user:
                self.send_json({"need_login": True}, 401)
                return
            try:
                r = nowpay.purchase_query()
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
                return
            self.send_json({
                "purchase_status": r.get("purchase_status", ""),
                "trade_no": r.get("trade_no", ""),
                "code": r.get("code", ""),
                "msg": r.get("msg", ""),
            })
        elif path == "/api/nowpay/quota":
            # 查即刻收次数余额；未登录按游客标识查（即刻收用 external_buyer_id 认人）
            user = current_user(self)
            key = str(user["id"]) if user else (_voter_key(self, user) or "c:anon")
            info = _nowpay_quota(key)
            self.send_json(info)
        elif path == "/api/entitlement":
            user = current_user(self)
            if not user:
                self.send_json({"need_login": True, "entitlements": {}}, 401)
                return
            self.send_json({"entitlements": auth_db.list_entitlements(user["id"])})
        elif path == "/api/pay/return":
            # 同步跳回只用来展示结果，真实状态一律以库里为准
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            out_trade_no = qs.get("out_trade_no", [""])[0]
            order = auth_db.get_order(out_trade_no)
            paid = "1" if (order and order["status"] == "paid") else "0"
            self.send_response(302)
            self.send_header(
                "Location",
                "/pay_return.html?order="
                + urllib.parse.quote(out_trade_no)
                + "&paid="
                + paid,
            )
            self.end_headers()
        elif path == "/api/pay/query":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            out_trade_no = qs.get("order", [""])[0]
            user = current_user(self)
            order = auth_db.get_order(out_trade_no)
            if not order:
                self.send_json({"error": "订单不存在"}, 404)
                return
            if not user or user["id"] != order["user_id"]:
                self.send_json({"error": "无权查看这笔订单"}, 403)
                return
            # 通知可能还没到，主动问一次支付宝；问到了就顺手入账
            if order["status"] != "paid" and pay.PAY_MODE != "mock":
                try:
                    trade_status = pay.query(out_trade_no)
                except Exception as e:
                    trade_status = ""
                    print("[pay] 查单失败：" + str(e), flush=True)
                if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
                    pay.grant(out_trade_no, "")
                    order = auth_db.get_order(out_trade_no)
            self.send_json(
                {
                    "status": order["status"],
                    "order": order,
                    "entitlements": auth_db.list_entitlements(user["id"]),
                }
            )
        elif path == "/api/me":
            user = current_user(self)
            self.send_json(
                {
                    "logged_in": user is not None,
                    "username": user["username"] if user else "",
                    "profile": auth_db.get_profile(user["id"]) if user else None,
                }
            )

        elif path == "/api/profile":
            user = current_user(self)
            if not user:
                self.send_json({"error": "请先登录"}, 401)
                return
            self.send_json({"ok": True, "profile": auth_db.get_profile(user["id"])})

        elif path == "/api/memory":
            self.send_json(get_user_memory(current_user(self)))
        elif path == "/api/ear_profile":
            if not require_login(self, "开启听觉图鉴"):
                return
            prof = _recipe_store(current_user(self)).read("ear_profile.json")
            valid = (
                prof if isinstance(prof, dict) and prof.get("archetype_id") else None
            )
            self.send_json({"ear_profile": valid})
        elif path == "/api/queue_state":
            user = current_user(self)
            if not user:
                self.send_json({"logged_in": False, "state": None})
                return
            st = memory.DbStore(user["id"]).read("queue_state.json")
            self.send_json(
                {"logged_in": True, "state": st if isinstance(st, dict) else {}}
            )
        elif path == "/api/catalog":
            full, owner, ent = _access(self)
            self.send_json(
                {
                    "total": len(sound_catalog.ALL_SOUNDS),
                    "items": sound_catalog.ALL_SOUNDS,
                    "free_count": len(sound_catalog.FREE_RELPATHS),
                    "premium_count": sound_catalog.PREMIUM_COUNT,
                    "unlocked": full,
                }
            )
        elif path == "/api/community_votes":
            user = current_user(self)
            voter_key = _voter_key(self, user)
            voter_votes = auth_db.get_voter_votes(voter_key)
            self.send_json(
                {
                    "votes": auth_db.get_all_vote_counts(),
                    "my_votes": {f"{pid}:{tag}": True for pid, tag in voter_votes},
                }
            )
        elif path == "/api/community_posts":
            viewer = current_user(self)
            voter_key = _voter_key(self, viewer)
            voter_votes = auth_db.get_voter_votes(voter_key)
            fork_counts = auth_db.get_fork_counts_map()
            vote_counts = auth_db.get_all_vote_counts()
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                page_size = int(qs.get("limit", ["20"])[0])
            except (TypeError, ValueError):
                page_size = 20
            page_size = max(1, min(page_size, 50))
            cursor = str(qs.get("cursor", [""])[0]).strip()
            before_ts = before_id = None
            if cursor:
                cursor_parts = cursor.split("|", 1)
                if len(cursor_parts) == 2:
                    try:
                        before_ts = float(cursor_parts[0])
                        before_id = cursor_parts[1]
                    except (TypeError, ValueError):
                        before_ts = before_id = None
            # 多取一条，只用来判断还有没有下一页，不返回给前端。
            # 兼容：旧版 auth_db 的这个函数只收 1 个参数（没有分页），
            # 直接传 3 个会 TypeError 断连，整个广场就刷不出帖子。
            # 先看函数签名支持几个参数，再决定怎么调（别用 try/except，
            # 那样会把函数内部的 TypeError 也当成签名不匹配吞掉）。
            import inspect
            supports_cursor = "before_ts" in inspect.signature(
                auth_db.list_community_posts_raw
            ).parameters
            if supports_cursor:
                rows = auth_db.list_community_posts_raw(page_size + 1, before_ts, before_id)
            else:
                rows = auth_db.list_community_posts_raw(page_size + 1)
                if cursor:
                    # 旧版不支持游标分页，取回一批后在内存里过滤
                    rows = [
                        p for p in rows
                        if (float(p.get("created_at") or 0), str(p.get("id") or ""))
                        < (float(before_ts), str(before_id))
                    ]
            has_more = len(rows) > page_size
            posts = rows[:page_size]
            comment_counts = auth_db.get_comment_counts()
            profiles = auth_db.get_profiles_map([p.get("user_id") for p in posts])
            formatted = [
                _format_public_post(
                    p, viewer, voter_votes, fork_counts, vote_counts, profiles=profiles
                )
                for p in posts
            ]
            for fp in formatted:
                fp["comment_count"] = comment_counts.get(fp["id"], 0)
            next_cursor = None
            if has_more and posts:
                tail = posts[-1]
                # repr 保证浮点往返不丢精度：四舍五入会把边界那条重复返回
                next_cursor = "%s|%s" % (
                    repr(float(tail.get("created_at") or 0)),
                    tail.get("id") or "",
                )
            self.send_json(
                {
                    "posts": formatted,
                    "has_more": has_more,
                    "next_cursor": next_cursor,
                    "limit": page_size,
                }
            )
        elif path == "/api/community_post":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            pid = str(qs.get("id", [""])[0]).strip()
            post = auth_db.get_community_post_raw(pid)
            if not post:
                self.send_json({"error": "配方不存在"}, 404)
                return
            viewer = current_user(self)
            voter_key = _voter_key(self, viewer)
            voter_votes = auth_db.get_voter_votes(voter_key)
            fork_counts = auth_db.get_fork_counts_map()
            vote_counts = auth_db.get_all_vote_counts()
            forks = auth_db.list_forks_of(pid)
            all_rows = [post] + forks
            profiles = auth_db.get_profiles_map([p.get("user_id") for p in all_rows])
            self.send_json(
                {
                    "ok": True,
                    "post": _format_public_post(
                        post,
                        viewer,
                        voter_votes,
                        fork_counts,
                        vote_counts,
                        profiles=profiles,
                    ),
                    "forks": [
                        _format_public_post(
                            f,
                            viewer,
                            voter_votes,
                            fork_counts,
                            vote_counts,
                            profiles=profiles,
                        )
                        for f in forks
                    ],
                }
            )
        elif path == "/api/comments":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            pid = str(qs.get("post_id", [""])[0]).strip()
            try:
                cmt_size = int(qs.get("limit", ["20"])[0])
            except (TypeError, ValueError):
                cmt_size = 20
            cmt_size = max(1, min(cmt_size, 50))
            cmt_cursor = str(qs.get("cursor", [""])[0]).strip()
            cmt_before_ts = cmt_before_id = None
            if cmt_cursor:
                cmt_parts = cmt_cursor.split("|", 1)
                if len(cmt_parts) == 2:
                    try:
                        cmt_before_ts = float(cmt_parts[0])
                        cmt_before_id = cmt_parts[1]
                    except (TypeError, ValueError):
                        cmt_before_ts = cmt_before_id = None
            # 多取一条判断还有没有更早的留言；返回的是时间正序，多出来的那条在最前面
            cmt_rows = auth_db.list_comments(
                pid, cmt_size + 1, cmt_before_ts, cmt_before_id
            )
            cmt_has_more = len(cmt_rows) > cmt_size
            comments = cmt_rows[1:] if cmt_has_more else cmt_rows
            me = current_user(self)
            me_id = me["id"] if me else None
            for c in comments:
                c["is_mine"] = bool(me_id and c.get("user_id") == me_id)
            cmt_next = None
            if cmt_has_more and comments:
                oldest = comments[0]
                cmt_next = "%s|%s" % (
                    repr(float(oldest.get("created_at") or 0)),
                    oldest.get("id") or "",
                )
            self.send_json(
                {
                    "ok": True,
                    "comments": comments,
                    "has_more": cmt_has_more,
                    "next_cursor": cmt_next,
                    "total": auth_db.count_comments(pid),
                }
            )
        elif path == "/api/creator":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            author = str(qs.get("author", [""])[0]).strip()[:24]
            if not author:
                self.send_json({"error": "缺少作者名"}, 400)
                return
            self.send_json({"ok": True, "creator": auth_db.get_creator_summary(author)})
        elif path == "/api/me/hub":
            user = current_user(self)
            voter_key = _voter_key(self, user)
            voter_votes = auth_db.get_voter_votes(voter_key)
            hub = auth_db.get_user_hub_data(user["id"] if user else None, voter_key)
            fork_counts = hub["fork_counts"]
            vote_counts = hub["vote_counts"]

            hub_profiles = auth_db.get_profiles_map(
                [p.get("user_id") for p in hub["my_posts"]]
            )
            my_posts = [
                _format_public_post(
                    p,
                    user,
                    voter_votes,
                    fork_counts,
                    vote_counts,
                    force_unlock=True,
                    profiles=hub_profiles,
                )
                for p in hub["my_posts"]
            ]

            starred_posts = []
            starred_builtin_ids = []
            for pid in hub["starred_post_ids"]:
                if pid in _BUILTIN_RECIPES:
                    starred_builtin_ids.append(pid)
                    continue
                p = auth_db.get_community_post_raw(pid)
                if p:
                    starred_posts.append(
                        _format_public_post(
                            p, user, voter_votes, fork_counts, vote_counts
                        )
                    )

            store = _recipe_store(user)
            custom_obj = store.read("custom_recipes.json")
            custom_recipes = (
                custom_obj.get("recipes", []) if isinstance(custom_obj, dict) else []
            )
            if not isinstance(custom_recipes, list):
                custom_recipes = []
            ep = store.read("ear_profile.json")
            valid_ep = ep if isinstance(ep, dict) and ep.get("archetype_id") else None

            # AI 配声里点过「收藏配方」的，列出来放进"我的"页
            ai_recipes = _list_good_recipes(user, limit=20)

            self.send_json(
                {
                    "logged_in": user is not None,
                    "username": user["username"] if user else "",
                    "stats": hub["stats"],
                    "my_posts": my_posts,
                    "starred_posts": starred_posts,
                    "starred_builtin_ids": starred_builtin_ids,
                    "custom_recipes": custom_recipes,
                    "ai_recipes": ai_recipes,
                    "ear_profile": valid_ep,
                    "profile": auth_db.get_profile(user["id"]) if user else None,
                    "memory": get_user_memory(user),
                }
            )
        elif path == "/api/recipes":
            store = _recipe_store(current_user(self))
            data_obj = store.read("custom_recipes.json")
            recipes = data_obj.get("recipes", []) if isinstance(data_obj, dict) else []
            if not isinstance(recipes, list):
                recipes = []
            self.send_json({"recipes": recipes})
        elif path == "/api/good_recipes":
            # agent 里点过「收藏配方」的满意配方，给 DIY 页「AI 帮你配」展示
            store = _recipe_store(current_user(self))
            data_obj = store.read("good_recipes.json")
            raw = data_obj.get("recipes", []) if isinstance(data_obj, dict) else []
            goods = []
            if isinstance(raw, list):
                for r in raw:
                    if not isinstance(r, dict):
                        continue
                    items = r.get("items", [])
                    if not isinstance(items, list):
                        items = []
                    # 老存档是 [路径, 权重] 数组，新存档是对象；统一成对象并丢掉权重为 0 的轨
                    clean_items = []
                    for it in items:
                        if isinstance(it, (list, tuple)) and len(it) >= 2:
                            p, w = it[0], it[1]
                        elif isinstance(it, dict):
                            p, w = (
                                it.get("path") or it.get("rel"),
                                it.get("weight", 1.0),
                            )
                        else:
                            continue
                        try:
                            weight = float(w)
                        except (TypeError, ValueError):
                            weight = 1.0
                        if weight <= 0:
                            continue
                        clean_items.append(
                            {
                                "path": os.path.basename(str(p or "").strip()),
                                "weight": round(weight, 3),
                            }
                        )
                    if not clean_items:
                        continue
                    goods.append(
                        {
                            "say": str(r.get("say") or ""),
                            "scene": r.get("scene") or "",
                            "items": clean_items,
                        }
                    )
            self.send_json({"recipes": goods})
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
            if _hotlink_blocked(self):
                self.send_json({"error": "forbidden"}, 403)
                return
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
            ctype = (
                "audio/wav"
                if ext == ".wav"
                else ("audio/ogg" if ext == ".ogg" else "audio/mpeg")
            )
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
                            chunk = body[start : end + 1]
                            self.send_response(206)
                            self.send_header("Content-Type", ctype)
                            self.send_cors_headers()
                            self.send_header("Accept-Ranges", "bytes")
                            self.send_header("Cache-Control", "public, max-age=86400")
                            self.send_header(
                                "Content-Range", f"bytes {start}-{end}/{total}"
                            )
                            self.send_header("Content-Length", str(len(chunk)))
                            self.end_headers()
                            self.wfile.write(chunk)
                            return
                        else:
                            self.send_response(416)
                            self.send_cors_headers()
                            self.send_header("Content-Range", f"bytes */{total}")
                            self.end_headers()
                            return
                    except ValueError:
                        pass
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_cors_headers()
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(total))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/play_audio":
            # 稳定播放文件：按名字取，支持 Range 请求（拖动/循环更稳）
            if _hotlink_blocked(self):
                self.send_json({"error": "forbidden"}, 403)
                return
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
            self.send_cors_headers()
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            # 非 API 路径交给静态文件服务：前端页面、图片、js/css 都从这里出
            serve_static(self, path)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        print("[POST] " + path, flush=True)
        if not self.check_rate_limit(path):
            return

        if path == "/api/pay/create":
            # 即刻收模式优先：商品和收银台都在支付宝托管
            if nowpay.ENABLED and nowpay.products_config():
                user = require_login(self, "购买")
                if not user:
                    return
                data = read_body(self)
                product_id = str(data.get("product_id") or "").strip()
                info = nowpay.products_config().get(product_id)
                if not info:
                    self.send_json({"error": "没有这个商品"}, 400)
                    return
                try:
                    r = nowpay.purchase_create(user["id"], product_id, info.get("sku_id", ""))
                except Exception as e:
                    print("[nowpay] 下单失败：" + str(e), flush=True)
                    self.send_json({"error": "下单失败，稍后再试"}, 500)
                    return
                if str(r.get("code", "")) != "10000":
                    self.send_json(
                        {"error": "下单失败：" + str(r.get("sub_msg") or r.get("msg") or "")},
                        400,
                    )
                    return
                # 支付宝二维码图片服务器有防盗链，浏览器直接引用会显示"内容被屏蔽"。
                # 服务端把它抓成本地文件再给前端，绕开这个限制。
                qr_local = ""
                qr_url = r.get("purchase_qr_code", "")
                if qr_url:
                    try:
                        from urllib.request import urlretrieve
                        qr_path = os.path.join(SITE_DIR, "_pay_qr.png")
                        urlretrieve(qr_url, qr_path)
                        qr_local = "/_pay_qr.png?v=" + str(int(time.time()))
                    except Exception as e:
                        print("[nowpay] 二维码本地化失败：" + str(e), flush=True)
                self.send_json(
                    {
                        "ok": True,
                        "pay_url": r.get("purchase_url", ""),
                        "qr_code": qr_local or qr_url,
                        "mode": "nowpay",
                        "product": product_id,
                        "product_name": (pay.PRODUCTS.get(product_id) or {}).get("name", ""),
                        "expire_time": r.get("expire_time", ""),
                    }
                )
                return
            user = require_login(self, "购买")
            if not user:
                return
            data = read_body(self)
            product_id = str(data.get("product_id") or "").strip()
            result = pay.create(user["id"], product_id, channel="web")
            if not result:
                self.send_json({"error": "没有这个商品"}, 400)
                return
            self.send_json(result)

        elif path == "/api/pay/notify":
            # 支付宝异步通知：不管成功失败，都必须回纯文本，否则它会一直重发
            form = read_form(self)
            out_trade_no = form.get("out_trade_no", "")
            print(
                "[pay] notify " + out_trade_no + " " + form.get("trade_status", ""),
                flush=True,
            )
            if not pay.verify_notify(form):
                print("[pay] 验签没通过，丢弃", flush=True)
                send_text(self, "fail", 400)
                return
            order = auth_db.get_order(out_trade_no)
            if not pay.check_notify(order, form):
                send_text(self, "fail", 400)
                return
            pay.grant(out_trade_no, form.get("trade_no", ""))
            send_text(self, "success")

        elif path == "/api/pay/mock_success":
            # 只给 mock 模式用：本地演示时点一下就当付过了。线上绝不能开放。
            if pay.PAY_MODE != "mock":
                self.send_json({"error": "模拟支付只在 mock 模式可用"}, 403)
                return
            user = require_login(self, "模拟支付")
            if not user:
                return
            data = read_body(self)
            out_trade_no = str(data.get("order") or "").strip()
            order = auth_db.get_order(out_trade_no)
            if not order or order["user_id"] != user["id"]:
                self.send_json({"error": "订单不存在"}, 404)
                return
            pay.grant(out_trade_no, "MOCK-" + out_trade_no)
            self.send_json(
                {
                    "ok": True,
                    "entitlements": auth_db.list_entitlements(user["id"]),
                }
            )

        elif path == "/api/register":
            data = read_body(self)
            ok, msg = auth_db.register(
                data.get("username", ""), data.get("password", "")
            )
            self.send_json({"ok": ok, "message": msg}, 200 if ok else 400)

        elif path == "/api/login":
            data = read_body(self)
            user, msg = auth_db.login(
                data.get("username", ""), data.get("password", "")
            )
            if not user:
                self.send_json({"ok": False, "message": msg}, 401)
                return
            token = auth_db.create_session(user["id"])
            self.send_json({"ok": True, "token": token, "username": user["username"]})

        elif path == "/api/logout":
            auth_db.logout(get_token(self))
            self.send_json({"ok": True})

        elif path == "/api/profile/update":
            user = current_user(self)
            if not user:
                self.send_json({"error": "请先登录"}, 401)
                return
            data = read_body(self)
            kwargs = {}
            if "display_name" in data:
                name = str(data.get("display_name") or "").strip()
                if len(name) > 16:
                    self.send_json({"error": "昵称最多 16 个字"}, 400)
                    return
                kwargs["display_name"] = name
            if "bio" in data:
                bio = str(data.get("bio") or "").strip()
                if len(bio) > 40:
                    self.send_json({"error": "简介最多 40 个字"}, 400)
                    return
                kwargs["bio"] = bio
            if "avatar_glyph" in data:
                try:
                    g = int(data.get("avatar_glyph"))
                except (TypeError, ValueError):
                    g = 0
                kwargs["avatar_glyph"] = max(0, min(auth_db.AVATAR_GLYPH_COUNT - 1, g))
            if "avatar_tone" in data:
                try:
                    t = int(data.get("avatar_tone"))
                except (TypeError, ValueError):
                    t = 0
                kwargs["avatar_tone"] = max(0, min(auth_db.AVATAR_TONE_COUNT - 1, t))
            prof, msg = auth_db.update_profile(user["id"], **kwargs)
            self.send_json({"ok": True, "message": msg, "profile": prof})

        elif path == "/api/migrate":
            # 注册/登录后：把游客本机档案并进账号（各取并集，不丢数据）
            user = current_user(self)
            if not user:
                self.send_json({"error": "请先登录"}, 401)
                return
            db_store = memory.DbStore(user["id"])
            file_store = memory.FileStore()
            # 四类记忆分别合并
            for name, key in [
                ("preferences.json", "counts"),
                ("good_recipes.json", "recipes"),
                ("bad_cases.json", "cases"),
                ("custom_recipes.json", "recipes"),
            ]:
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
                    existing_ids = {
                        it.get("id")
                        for it in items
                        if isinstance(it, dict) and it.get("id")
                    }
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

            # 边界门禁：只让声音需求进模型，越界问题直接给固定引导，不花模型调用
            has_context = (
                bool(data.get("current_tracks"))
                or bool(data.get("history"))
                or bool(data.get("initial_prompt"))
            )
            allowed, guard_reason = input_guard.check(say, has_context=has_context)
            if not allowed:
                print("[guard] 拦截 " + guard_reason + "：" + say[:40], flush=True)
                reply, suggestions = input_guard.refusal(guard_reason)
                self.send_json(
                    {
                        "ok": False,
                        "action": "blocked",
                        "reply": reply,
                        "suggestions": suggestions,
                    }
                )
                return

            # 免费额度：每天 N 次，用完就地拦下；解锁全库后不限
            full_access, quota_owner, ent = _access(self)
            free_rels = None
            if not full_access:
                peek = auth_db.peek_daily_quota(quota_owner, FREE_DAILY_GENERATE)
                if peek["left"] <= 0:
                    _quota_exhausted(self, peek)
                    return
                free_rels = sound_catalog.relpaths_for(False)

            try:
                seconds = max(5, min(60, int(data.get("seconds", 30) or 30)))
            except (TypeError, ValueError):
                seconds = 30

            clean_current = map_client_tracks(data.get("current_tracks") or [])
            current_for_brain = [
                {
                    "path": os.path.basename(t["rel"]),
                    "weight": round(t["weight"], 2),
                    "pan": round(t["pan"], 2),
                    "mode": t["mode"],
                    "density": round(t["density"], 2),
                }
                for t in clean_current
            ]

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
                self.send_json(
                    {
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
                    }
                )
                return

            role_notes = {}
            for raw_t in design.get("tracks") or []:
                if isinstance(raw_t, dict) and raw_t.get("path"):
                    role_notes[os.path.basename(str(raw_t["path"]))] = str(
                        raw_t.get("role_note") or ""
                    )

            mapped_tracks = map_client_tracks(design.get("tracks") or [])
            if not mapped_tracks:
                fallback_rel = find_relpath("母带_城市夜雨_CC0.mp3")
                if fallback_rel:
                    mapped_tracks = [
                        _normalize_track_spec({"rel": fallback_rel, "weight": 0.72})
                    ]
            quota_info = None
            if free_rels is not None:
                # 免费用户：把配方里越权的付费素材换掉，然后才扣一次额度
                mapped_tracks = _downgrade_tracks(
                    mapped_tracks, design.get("intent") or {}, free_rels
                )
                ok_take, quota_info = auth_db.take_daily_quota(
                    quota_owner, FREE_DAILY_GENERATE
                )
                if not ok_take:
                    _quota_exhausted(self, quota_info)
                    return

            mix, sr = render(mapped_tracks, seconds)
            self.server.last_audio = (mix, sr)
            # 即刻收用户：音频真生成出来了，才核销一次次数
            _nowpay_consume(ent)

            session["intent"] = design["intent"]
            session["items"] = [(t["rel"], t["weight"]) for t in mapped_tracks]
            session["say"] = design.get("final_prompt") or say

            resp_tracks = []
            for t in mapped_tracks:
                base = os.path.basename(t["rel"])
                resp_tracks.append(
                    {
                        "path": base,
                        "weight": round(t["weight"], 2),
                        "pan": round(t["pan"], 2),
                        "mode": t["mode"],
                        "density": round(t["density"], 2),
                        "role_note": role_notes.get(base, ""),
                    }
                )

            self.send_json(
                {
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
                    "full_access": full_access,
                    "quota": quota_info,
                }
            )

        elif path == "/api/generate":
            data = read_body(self)
            say = str(data.get("say") or "").strip()[:300]
            seconds = int(data.get("seconds", 30))
            if not say:
                self.send_json({"error": "空需求"}, 400)
                return

            # 旧接口同样过门禁，避免绕过新入口
            allowed, guard_reason = input_guard.check(say)
            if not allowed:
                print("[guard] 拦截 " + guard_reason + "：" + say[:40], flush=True)
                reply, suggestions = input_guard.refusal(guard_reason)
                self.send_json(
                    {
                        "error": reply,
                        "action": "blocked",
                        "reply": reply,
                        "suggestions": suggestions,
                    },
                    400,
                )
                return

            full_access, quota_owner, ent = _access(self)
            free_rels = None
            if not full_access:
                peek = auth_db.peek_daily_quota(quota_owner, FREE_DAILY_GENERATE)
                if peek["left"] <= 0:
                    _quota_exhausted(self, peek)
                    return
                free_rels = sound_catalog.relpaths_for(False)

            intent, source = understanding_brain.understand(say)
            items = executor.pick(intent, free_rels)
            if free_rels is not None:
                ok_take, quota_info = auth_db.take_daily_quota(
                    quota_owner, FREE_DAILY_GENERATE
                )
                if not ok_take:
                    _quota_exhausted(self, quota_info)
                    return
            session["intent"] = intent
            session["items"] = items
            session["say"] = say
            mix, sr = render(items, seconds)
            # 即刻收用户：音频真生成出来了，才核销一次次数
            _nowpay_consume(ent)

            self.send_json(
                {
                    "source": source,
                    "ai_powered": source in ("Qwen3.8-Flash", "本地模型"),
                    "scene": intent["scene"],
                    "scene_detail": intent["scene_detail"],
                    "mood": intent["mood"],
                    "warmth": intent["warmth"],
                    "dynamics": intent["dynamics"],
                    "avoid": intent.get("avoid", []),
                    "items": [
                        {"path": os.path.basename(p), "weight": round(w, 2)}
                        for p, w in items
                        if w > 0
                    ],
                    "audio": "/api/audio",
                }
            )
            # 把当前音频缓存到内存，供 /api/audio 取
            self.server.last_audio = (mix, sr)

        elif path == "/api/preview":
            # 社区配方试听：直接给配比（或 post_id），不调 Qwen
            data = read_body(self)
            seconds = int(data.get("seconds", 20))
            raw_items = data.get("items", [])
            if not raw_items and data.get("post_id"):
                post = auth_db.get_community_post_raw(str(data.get("post_id")).strip())
                if post:
                    raw_items = post.get("items", [])
            items = map_client_tracks(raw_items)
            if not items:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            mix, sr = render(items, seconds)
            self.server.preview_audio = (mix, sr)
            self.send_json({"ok": True, "audio": "/api/preview_audio"})

        elif path == "/api/play":
            # 场景卡/播放页：按预设配方（或 post_id）直接出声，不调 Qwen、不依赖 key
            data = read_body(self)
            seconds = int(data.get("seconds", PLAY_SECONDS))
            raw_items = data.get("items", [])
            post = None
            if not raw_items and data.get("post_id"):
                post = auth_db.get_community_post_raw(str(data.get("post_id")).strip())
                if post:
                    raw_items = post.get("items", [])
            items = map_client_tracks(raw_items)
            if not items:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            name, _ = play_file(items, seconds)
            shown = data.get("title") or (post.get("title") if post else "") or "夜息"
            resp = {
                "ok": True,
                "name": name,
                "audio": "/api/play_audio?name=" + name,
                "title": shown,
            }
            if not post:
                resp["items"] = [
                    {
                        "path": os.path.basename(t["rel"]),
                        "weight": round(t["weight"], 2),
                        "pan": round(t["pan"], 2),
                        "mode": t["mode"],
                        "density": round(t["density"], 2),
                    }
                    for t in items
                    if t["weight"] > 0
                ]
            self.send_json(resp)

        elif path == "/api/recipes":
            data = read_body(self)
            raw_tracks = data.get("tracks")
            if raw_tracks is None:
                raw_tracks = data.get("items", [])
            tracks = map_client_tracks(raw_tracks)
            if not tracks:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            title = (
                str(data.get("title") or "我的夜息配方").strip()[:40] or "我的夜息配方"
            )
            rid = str(data.get("id") or "").strip()[:32]
            store = _recipe_store(current_user(self))
            data_obj = store.read("custom_recipes.json")
            recipes = (
                list(data_obj.get("recipes", []))
                if isinstance(data_obj, dict)
                and isinstance(data_obj.get("recipes"), list)
                else []
            )
            clean_tracks = [
                {
                    "path": os.path.basename(t["rel"]),
                    "weight": round(t["weight"], 3),
                    "pan": round(t["pan"], 3),
                    "mode": t["mode"],
                    "density": round(t["density"], 3),
                }
                for t in tracks
            ]
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
            recipes = [
                r for r in old_list if isinstance(r, dict) and r.get("id") != rid
            ]
            store.write("custom_recipes.json", {"recipes": recipes})
            self.send_json({"ok": True, "recipes": recipes})

        elif path == "/api/good_recipes/delete":
            data = read_body(self)
            want_key = str(data.get("key") or "").strip()
            store = _good_recipes_store(current_user(self))
            obj = store.read("good_recipes.json")
            old_list = obj.get("recipes", []) if isinstance(obj, dict) else []
            if not isinstance(old_list, list):
                old_list = []
            kept = []
            removed = False
            for r in old_list:
                if not removed and isinstance(r, dict):
                    items = _normalize_good_items(r.get("items"))
                    say = str(r.get("say") or "").strip()
                    key_src = (
                        say
                        + "|"
                        + ",".join(i["path"] + ":" + str(i["weight"]) for i in items)
                    )
                    k = hashlib.sha1(key_src.encode("utf-8")).hexdigest()[:12]
                    if k == want_key:
                        removed = True
                        continue
                kept.append(r)
            if not removed:
                self.send_json({"error": "没有找到这条收藏"}, 404)
                return
            store.write("good_recipes.json", {"recipes": kept})
            self.send_json({"ok": True})

        elif path == "/api/comment":
            user = current_user(self)
            if not user:
                self.send_json({"error": "请先登录后再留言"}, 401)
                return
            data = read_body(self)
            pid = str(data.get("post_id") or "").strip()
            body = str(data.get("body") or "").strip()
            if not pid or len(pid) > 32 or not re.match(r"^[A-Za-z0-9_-]+$", pid):
                self.send_json({"error": "无效配方编号"}, 400)
                return
            if not body:
                self.send_json({"error": "评论不能为空"}, 400)
                return
            if len(body) > 80:
                self.send_json({"error": "留言最多 80 个字"}, 400)
                return
            # 官方示例（r1-r6）不在 posts 表里，但允许真人给它留言
            saved = auth_db.add_comment(
                pid,
                user["id"],
                auth_db.display_name_of(user["id"], user["username"]),
                body,
                allow_builtin=(pid in _BUILTIN_RECIPES),
            )
            if saved is None:
                self.send_json({"error": "配方不存在"}, 404)
                return
            self.send_json({"ok": True, "comment": saved})
        elif path == "/api/comment/delete":
            user = current_user(self)
            if not user:
                self.send_json({"error": "请先登录"}, 401)
                return
            data = read_body(self)
            cid = str(data.get("id") or "").strip()
            ok, code, msg = auth_db.delete_comment(cid, user["id"])
            if not ok:
                self.send_json({"error": msg}, code)
                return
            self.send_json({"ok": True})
        elif path == "/api/community_vote":
            if not require_login(self, "给广场的配方投票"):
                return
            data = read_body(self)
            recipe_id = str(data.get("recipe_id") or "").strip()
            tag = str(data.get("tag") or "").strip()
            if (
                not recipe_id
                or len(recipe_id) > 32
                or not re.match(r"^[A-Za-z0-9_-]+$", recipe_id)
            ):
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

            user = current_user(self)
            voter_key = _voter_key(self, user)
            counts, voted_on = auth_db.toggle_community_vote(
                recipe_id, tag, delta, voter_key=voter_key
            )
            resp = {
                "ok": True,
                "recipe_id": recipe_id,
                "tag": tag,
                "voted": voted_on,
                "counts": counts,
            }
            if tag == "borrow" and voted_on:
                post = auth_db.get_community_post_raw(recipe_id)
                if post:
                    is_mine = bool(user and post.get("user_id") == user["id"])
                    if post.get("remix_policy") in ("open", "star_to_fork") or is_mine:
                        resp["unlocked"] = True
                        resp["items"] = post.get("items") or []
            self.send_json(resp)

        elif path == "/api/community_posts":
            if not require_login(self, "把配方发到广场"):
                return
            data = read_body(self)
            raw_tracks = data.get("tracks")
            if raw_tracks is None:
                raw_tracks = data.get("items", [])
            tracks = map_client_tracks(raw_tracks)
            if not tracks:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return

            user = current_user(self)
            voter_key = _voter_key(self, user)
            voter_votes = auth_db.get_voter_votes(voter_key)

            # 配方默认不外传：没带策略就按「借走解锁」处理，不会是「随便给」
            remix_policy = str(data.get("remix_policy") or "star_to_fork").strip()
            if remix_policy not in auth_db.VALID_REMIX_POLICIES:
                self.send_json({"error": "无效的配方许可"}, 400)
                return

            # 登录用户优先用自定义昵称，其次登录名；游客用填的署名
            if user:
                author = auth_db.display_name_of(user["id"], user["username"])
            else:
                author = str(data.get("author_name") or "").strip()[:20] or "深夜旅人"
            title = (
                str(data.get("title") or "我的夜息声景").strip()[:36] or "我的夜息声景"
            )
            story = str(data.get("story") or "").strip()[:120]

            clean_tracks = [
                {
                    "path": os.path.basename(t["rel"]),
                    "weight": round(t["weight"], 3),
                    "pan": round(t["pan"], 3),
                    "mode": t["mode"],
                    "density": round(t["density"], 3),
                }
                for t in tracks
            ]

            remix_raw = data.get("remix_of")
            remix_of = None
            parent_post_id = ""
            root_post_id = ""
            diff_summary = []

            if isinstance(remix_raw, dict):
                parent_id = str(remix_raw.get("id") or "").strip()[:32]
                parent_items = None
                if parent_id:
                    parent = auth_db.get_community_post_raw(parent_id)
                    if parent:
                        is_parent_owner = bool(
                            user
                            and parent.get("user_id")
                            and user["id"] == parent.get("user_id")
                        )
                        if (
                            parent["remix_policy"] == "listen_only"
                            and not is_parent_owner
                        ):
                            self.send_json(
                                {
                                    "error": "原作者将此配方设为「仅限聆听」，暂不支持 Remix 改编"
                                },
                                403,
                            )
                            return
                        if (
                            parent["remix_policy"] == "star_to_fork"
                            and not is_parent_owner
                            and (parent["id"], "borrow") not in voter_votes
                        ):
                            self.send_json(
                                {"error": "请先点击「借我一晚」解锁该配方的微调权限"},
                                403,
                            )
                            return
                        parent_post_id = parent["id"]
                        root_post_id = parent["root_post_id"] or parent["id"]
                        remix_of = {
                            "id": parent["id"],
                            "title": parent["title"],
                            "author": parent["author"],
                        }
                        parent_items = parent["items"]
                    else:
                        builtin = _BUILTIN_RECIPES.get(parent_id)
                        if builtin:
                            parent_post_id = parent_id
                            root_post_id = parent_id
                            remix_of = {
                                "id": parent_id,
                                "title": builtin["title"],
                                "author": builtin["author"],
                            }
                            parent_items = builtin["items"]

                if parent_items is not None:
                    diff_summary = auth_db.compute_recipe_diff(
                        parent_items, clean_tracks, _track_label
                    )
                    if not diff_summary:
                        self.send_json(
                            {
                                "error": "和原配方几乎一样哦，微调一点声层或空间感再发布吧，或者直接点「借我一晚」收藏"
                            },
                            400,
                        )
                        return
                elif str(remix_raw.get("title") or "").strip():
                    remix_of = {
                        "id": parent_id,
                        "title": str(remix_raw.get("title") or "").strip()[:36],
                        "author": str(remix_raw.get("author") or "夜息").strip()[:24]
                        or "夜息",
                    }

            post_id = "u_" + secrets.token_hex(5)
            delete_token = secrets.token_hex(8)
            now = int(time.time())
            created = auth_db.create_community_post(
                {
                    "id": post_id,
                    "title": title,
                    "author": author,
                    "user_id": user["id"] if user else None,
                    "group": _infer_post_group(tracks),
                    "story": story,
                    "remix_of": remix_of,
                    "remix_policy": remix_policy,
                    "parent_post_id": parent_post_id,
                    "root_post_id": root_post_id,
                    "diff_summary": diff_summary,
                    "recipe_hash": auth_db.normalize_recipe_hash(clean_tracks),
                    "version": 1,
                    "items": clean_tracks,
                    "created_at": now,
                    "updated_at": now,
                    "delete_token": delete_token,
                }
            )

            formatted = _format_public_post(
                created, user, voter_votes, {}, {}, force_unlock=True
            )
            self.send_json(
                {
                    "ok": True,
                    "post": formatted,
                    "delete_token": delete_token,
                }
            )

        elif path == "/api/community_posts/policy":
            user = current_user(self)
            if not user:
                self.send_json({"error": "请先登录"}, 401)
                return
            data = read_body(self)
            pid = str(data.get("id") or "").strip()
            policy = str(data.get("remix_policy") or "").strip()
            ok, msg = auth_db.update_community_post_policy(pid, user["id"], policy)
            if not ok:
                code = 404 if msg == "配方不存在" else (403 if "权限" in msg else 400)
                self.send_json({"error": msg}, code)
                return
            self.send_json({"ok": True, "remix_policy": policy, "message": msg})

        elif path == "/api/community_posts/delete":
            data = read_body(self)
            pid = str(data.get("id") or "").strip()
            dtok = str(data.get("delete_token") or "").strip()
            user = current_user(self)
            ok, code, msg = auth_db.delete_community_post(
                pid, user_id=user["id"] if user else None, delete_token=dtok
            )
            if not ok:
                self.send_json({"error": msg}, code)
                return
            self.send_json({"ok": True})

        elif path == "/api/export_commercial":
            user = require_login(self, "导出商用音频与授权凭证")
            if not user:
                return
            # 商用买断是「一次购买、永久可用」，只校验资格，不扣次数
            ent = auth_db.list_entitlements(user["id"]).get("commercial")
            if not ent or not ent.get("active"):
                self.send_json(
                    {
                        "error": "商用导出需要先购买商用授权",
                        "need_pay": True,
                        "product_id": "commercial",
                        "products": pay.public_products(),
                    },
                    402,
                )
                return
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
            cert_id = (
                "YX-CC0-" + time.strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper()
            )

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_cors_headers()
            self.send_header("Access-Control-Expose-Headers", "X-Yexi-Cert-Id")
            self.send_header("X-Yexi-Cert-Id", cert_id)
            self.send_header(
                "Content-Disposition", 'attachment; filename="yexi_commercial.wav"'
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/download":
            # 整夜版导出：5 分钟可循环母带。解锁全库后才能带走。
            user = require_login(self, "导出整夜版")
            if not user:
                return
            ent = auth_db.list_entitlements(user["id"]).get("full")
            if not ent or not ent.get("active"):
                self.send_json(
                    {
                        "error": "导出需要先解锁全库",
                        "need_pay": True,
                        "product_id": "day3",
                        "products": pay.public_products(),
                    },
                    402,
                )
                return
            data = read_body(self)
            raw_tracks = data.get("items")
            if raw_tracks is None:
                raw_tracks = data.get("tracks", [])
            items = map_client_tracks(raw_tracks)
            if not items:
                self.send_json({"error": "配方里没有可用素材"}, 400)
                return
            mix, sr = render(items, 300)
            import io

            buf = io.BytesIO()
            executor.write_wav(buf, mix, sr)
            body = buf.getvalue()
            cert_id = (
                "YX-LOOP-"
                + time.strftime("%Y%m%d")
                + "-"
                + secrets.token_hex(3).upper()
            )
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_cors_headers()
            self.send_header("Access-Control-Expose-Headers", "X-Yexi-Cert-Id")
            self.send_header("X-Yexi-Cert-Id", cert_id)
            self.send_header(
                "Content-Disposition", 'attachment; filename="yexi_loop.wav"'
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/ear_profile":
            if not require_login(self, "保存听觉图鉴结果"):
                return
            data = read_body(self)
            arch_id = str(data.get("archetype_id") or "").strip()
            if not arch_id or not re.match(r"^[A-Za-z0-9_-]{1,32}$", arch_id):
                self.send_json({"error": "无效耳朵档案编号"}, 400)
                return
            tracks = map_client_tracks(data.get("tracks") or [])
            if not tracks:
                self.send_json({"error": "档案缺少可用声轨"}, 400)
                return

            raw_scores = (
                data.get("scores") if isinstance(data.get("scores"), dict) else {}
            )
            clean_scores = {}
            for sk in ("warmth", "crisp", "space", "nature", "immersion"):
                try:
                    sv = int(round(float(raw_scores.get(sk, 50))))
                except (TypeError, ValueError):
                    sv = 50
                clean_scores[sk] = max(0, min(100, sv))

            raw_intent = (
                data.get("intent") if isinstance(data.get("intent"), dict) else {}
            )
            clean_intent = {
                "scene": str(raw_intent.get("scene") or "rain")[:24],
                "mood": str(raw_intent.get("mood") or "sleep")[:24],
                "warmth": str(raw_intent.get("warmth") or "warm")[:24],
                "dynamics": str(raw_intent.get("dynamics") or "steady")[:24],
            }

            clean_tracks = [
                {
                    "path": os.path.basename(t["rel"]),
                    "weight": round(t["weight"], 3),
                    "pan": round(t["pan"], 3),
                    "mode": t["mode"],
                    "density": round(t["density"], 3),
                }
                for t in tracks
            ]

            profile = {
                "archetype_id": arch_id,
                "archetype_name": str(
                    data.get("archetype_name") or "夜息聆听者"
                ).strip()[:24],
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

        elif path == "/api/queue_state":
            user = current_user(self)
            if not user:
                self.send_json({"error": "游客队列仅保存在本地浏览器"}, 401)
                return
            data = read_body(self)
            raw_state = (
                data.get("state") if isinstance(data.get("state"), dict) else data
            )
            last_good = str(raw_state.get("last_good_id") or "").strip()[:48]
            active_ids = []
            for aid in (raw_state.get("active_ids") or [])[:12]:
                s = str(aid or "").strip()[:48]
                if s and s not in active_ids:
                    active_ids.append(s)
            scores = {}
            raw_scores = raw_state.get("scores")
            if isinstance(raw_scores, dict):
                for k, v in list(raw_scores.items())[:30]:
                    sk = str(k or "").strip()[:48]
                    if not sk:
                        continue
                    try:
                        scores[sk] = round(_clamp(float(v), -50.0, 200.0), 2)
                    except (TypeError, ValueError):
                        pass
            real_skips = {}
            raw_skips = raw_state.get("real_skips")
            if isinstance(raw_skips, dict):
                for k, v in list(raw_skips.items())[:30]:
                    sk = str(k or "").strip()[:48]
                    if not sk:
                        continue
                    try:
                        real_skips[sk] = max(0, min(50, int(v)))
                    except (TypeError, ValueError):
                        pass
            clean_state = {
                "last_good_id": last_good,
                "active_ids": active_ids,
                "scores": scores,
                "real_skips": real_skips,
                "updated_at": int(time.time()),
            }
            memory.DbStore(user["id"]).write("queue_state.json", clean_state)
            self.send_json({"ok": True, "state": clean_state})

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
                memory.save_good_recipe(
                    say_text, intent, [[p, round(w, 3)] for p, w in saved_items], store
                )
                self.send_json({"ok": True, "saved": "good"})
                return

            if not items:
                items = map_client_items(data.get("items"))
            if not items:
                self.send_json({"error": "还没有可调整的声轨"}, 400)
                return

            memory.save_bad_case(
                say_text, fb, [[p, round(w, 3)] for p, w in items], store
            )
            new_items, notes = ft.apply_feedback(fb, items)
            session["items"] = new_items
            mix, sr = render(new_items, seconds)
            self.server.last_audio = (mix, sr)

            self.send_json(
                {
                    "ok": True,
                    "notes": notes,
                    "items": [
                        {"path": os.path.basename(p), "weight": round(w, 2)}
                        for p, w in new_items
                        if w > 0
                    ],
                    "audio": "/api/audio",
                }
            )

        else:
            self.send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        # 安静一点，只打印关键行
        pass


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(PLAY_DIR, exist_ok=True)
    # 支付配置自检：缺 key 时喊出来，但不阻断听声服务
    pay.startup_check()
    # 部署平台要求监听 0.0.0.0，本机开发这样也能访问
    print("夜息已启动：http://0.0.0.0:" + str(PORT), flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
