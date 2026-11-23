# 从 Freesound 采集 CC0 高码率助眠与 ASMR 候选素材（v3）
# 铁律：
# 1. 原样保存 -hq.mp3 原始字节，绝不做任何音频后处理（不滤波、不降噪、不压缩、不混响、不重编码）
# 2. 只收 Creative Commons 0 (CC0) 授权
# 3. 不修改 scene_assets / product_assets / rejected / 素材库清单.md / 素材执行层.py
#
# 用法：
# C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe collect_candidates_v3.py

import glob
import html
import json
import math
import os
import re
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import soundfile as sf

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "candidates_v3")
MAX_BYTES = 25 * 1024 * 1024  # 25 MB 上限，避免大文件超时
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# 显式排除（已入库 / 已淘汰 / 之前抓过）
EXPLICIT_EXCLUDE_IDS = {
    "717853", "427086", "853672", "717890", "455949", "704381", "876926",
    "171980", "200273", "96729", "846714", "865820", "563766", "563764",
    "592345", "833924", "876999", "854874", "406099", "406100", "771130",
    "822935", "869851", "681366", "864279",
}

NOISE_WORDS = [
    "window", "traffic", "siren", "horn", "voices", "talking", "speech",
    "dog", "bark", "airplane", "plane", "footstep", "music", "melody",
    "piano", "chime", "bells", "car ", "cars ", "motorcycle", "scream", "laugh",
]
NATURE_EXTRA_NOISE = ["storm", "thunder"]

CATEGORIES = [
    # 分组一：自然助眠缺口与质感梯度
    {
        "group": "nature",
        "group_label": "自然助眠补缺与质感梯度",
        "name": "林风树林",
        "target": 3,
        "duration_filters": ["duration:[60 TO 240]", "duration:[60 TO 600]"],
        "queries": ["wind trees forest", "forest wind ambience", "wind foliage"],
        "avoid_crackl": False,
    },
    {
        "group": "nature",
        "group_label": "自然助眠补缺与质感梯度",
        "name": "柔和炉火",
        "target": 3,
        "duration_filters": ["duration:[60 TO 240]", "duration:[60 TO 600]"],
        "queries": ["campfire ambience", "hearth fire", "wood fire ambience", "fireplace soft"],
        "avoid_crackl": True,
    },
    {
        "group": "nature",
        "group_label": "自然助眠补缺与质感梯度",
        "name": "长段海浪",
        "target": 3,
        "duration_filters": ["duration:[60 TO 240]", "duration:[60 TO 600]"],
        "queries": ["gentle ocean waves", "calm sea waves", "ocean waves ambience"],
        "avoid_crackl": False,
    },
    {
        "group": "nature",
        "group_label": "自然助眠补缺与质感梯度",
        "name": "长段溪流",
        "target": 3,
        "duration_filters": ["duration:[60 TO 240]", "duration:[60 TO 600]"],
        "queries": ["gentle stream water", "brook ambience", "river water ambience"],
        "avoid_crackl": False,
    },
    {
        "group": "nature",
        "group_label": "自然助眠补缺与质感梯度",
        "name": "帐篷与柔和雨",
        "target": 3,
        "duration_filters": ["duration:[60 TO 240]", "duration:[60 TO 600]"],
        "queries": ["rain tent", "soft rain ambience", "gentle rain"],
        "avoid_crackl": False,
    },
    {
        "group": "nature",
        "group_label": "自然助眠补缺与质感梯度",
        "name": "柔和山谷风",
        "target": 2,
        "duration_filters": ["duration:[60 TO 240]", "duration:[60 TO 600]"],
        "queries": ["gentle wind ambience", "soft wind nature", "meadow wind"],
        "avoid_crackl": False,
    },
    # 分组二：经典轻 ASMR 触发音试水
    {
        "group": "asmr",
        "group_label": "经典轻 ASMR 触发音试水",
        "name": "ASMR翻书",
        "target": 2,
        "duration_filters": ["duration:[20 TO 600]"],
        "queries": ["page turning", "book pages", "turning pages"],
        "avoid_crackl": False,
    },
    {
        "group": "asmr",
        "group_label": "经典轻 ASMR 触发音试水",
        "name": "ASMR写字",
        "target": 2,
        "duration_filters": ["duration:[20 TO 600]"],
        "queries": ["pencil writing", "writing paper", "pen writing"],
        "avoid_crackl": False,
    },
    {
        "group": "asmr",
        "group_label": "经典轻 ASMR 触发音试水",
        "name": "ASMR轻敲毛刷",
        "target": 2,
        "duration_filters": ["duration:[20 TO 600]"],
        "queries": ["wood tapping", "soft brush", "brushing asmr"],
        "avoid_crackl": False,
    },
]


def load_blacklist():
    """读取已有清单与历史链接中的 Freesound ID，防止重复抓到已用或已淘汰素材。"""
    ids = set(EXPLICIT_EXCLUDE_IDS)

    # 1. 素材库清单.md 里的 Freesound id 列与数字 ID
    manifest_md = os.path.join(BASE, "素材库清单.md")
    if os.path.exists(manifest_md):
        with open(manifest_md, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        for m in re.findall(r"\|\s*(\d{4,8})\s*\|", text):
            ids.add(m)

    # 2. 历史抓链文件（tab 分隔或含 previews URL）
    for fname in ["more_links.txt", "scene_links.txt", "hq_links.txt"]:
        fpath = os.path.join(BASE, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                for m in re.findall(r"previews/\d+/(\d+)_\d+", line):
                    ids.add(m)
                parts = line.strip().split("\t")
                for col in parts[:4]:
                    if col.isdigit() and len(col) >= 4:
                        ids.add(col)

    return ids


def is_title_noisy(title, group, skip_crackl=False):
    t = " " + title.lower() + " "
    for w in NOISE_WORDS:
        if w in t:
            return True, f"含噪点词:{w.strip()}"
    if re.search(r"\bcars?\b", t):
        return True, "含噪点词:car"
    if group == "nature":
        for w in NATURE_EXTRA_NOISE:
            if w in t:
                return True, f"自然类排除:{w}"
    if skip_crackl and "crackl" in t:
        return True, "炉火初筛避开crackl"
    return False, ""


def curl_fetch_bytes(url, timeout=25, retries=3):
    """走 Windows Schannel (--http1.1 --tlsv1.2) 抓取网页字节，避开 Python OpenSSL 断流。"""
    last_err = ""
    cmd = [
        "curl.exe", "-fsSL", "--http1.1", "--tlsv1.2",
        "--max-time", str(timeout),
        "-A", HEADERS["User-Agent"],
        url,
    ]
    for attempt in range(retries):
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        err_msg = proc.stderr.decode("utf-8", "ignore").strip()
        last_err = err_msg or f"curl exit {proc.returncode}"
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(last_err)


def fetch_search_results(query, duration_filter, sort_by="rating"):
    """搜索 Freesound CC0 页面并解析结果卡片。"""
    params = urllib.parse.urlencode({
        "q": query,
        "f": f'license:"Creative Commons 0" {duration_filter}',
        "s": sort_by,
    })
    url = "https://freesound.org/search/?" + params
    resp_bytes = curl_fetch_bytes(url, timeout=25, retries=3)
    page_html = resp_bytes.decode("utf-8", "ignore")

    blocks = page_html.split('<div class="bw-search__result"')[1:]
    results = []
    for b in blocks:
        sid_m = re.search(r'data-sound-id="(\d+)"', b)
        mp3_m = re.search(r'data-mp3="([^"]+)-lq\.mp3"', b)
        title_m = re.search(r'aria-label="Sound\s+(.*?)\s+by\s+([^"]+)"', b)
        if not (sid_m and mp3_m):
            continue
        title = html.unescape(title_m.group(1)).strip() if title_m else f"Sound {sid_m.group(1)}"
        author = html.unescape(title_m.group(2)).strip() if title_m else "unknown"
        hq_url = mp3_m.group(1).replace("\\u0026", "&") + "-hq.mp3"
        results.append({
            "id": sid_m.group(1),
            "title": title,
            "author": author,
            "hq_url": hq_url,
            "page_url": f"https://freesound.org/s/{sid_m.group(1)}/",
        })
    return results


def download_raw_hq(url, dest_path, retries=3):
    """用 curl.exe 断点续传并原样下载 -hq.mp3 字节，不做任何音质修改；超 25MB 中止。"""
    tmp_path = dest_path + ".part"
    cmd = [
        "curl.exe", "-fsSL", "--http1.1", "--tlsv1.2",
        "-C", "-",
        "--speed-limit", "2048", "--speed-time", "25",
        "--max-time", "180",
        "--max-filesize", "26214400",
        "-A", HEADERS["User-Agent"],
        "-o", tmp_path,
        url,
    ]
    last_err = ""
    for attempt in range(retries):
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode == 0 and os.path.exists(tmp_path):
            size = os.path.getsize(tmp_path)
            if 10 * 1024 < size <= MAX_BYTES:
                os.replace(tmp_path, dest_path)
                return
            last_err = f"文件大小异常({size} bytes)"
            # 大小异常不能续传，清掉重下
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        else:
            err_msg = proc.stderr.decode("utf-8", "ignore").strip()
            last_err = err_msg or f"curl exit {proc.returncode}"
            # curl 33 表示范围请求不被支持或越界，清掉 .part 下次从头下；其余保留 .part 断点续传
            if proc.returncode == 33 and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))

    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    raise RuntimeError(last_err)


def fetch_sound_page_meta(sid, fallback_title):
    """从 Freesound 单条声音详情页补齐标题和作者，失败则降级返回文件名。"""
    url = f"https://freesound.org/s/{sid}/"
    try:
        raw = curl_fetch_bytes(url, timeout=20, retries=2)
        page = raw.decode("utf-8", "ignore")
        title = fallback_title
        author = "unknown"
        t_m = re.search(r"<title>(.*?)</title>", page, re.S)
        if t_m:
            t_txt = html.unescape(t_m.group(1)).strip()
            m = re.match(r"^Freesound\s*-\s*(.+?)\s+by\s+(.+)$", t_txt)
            if m:
                title = m.group(1).strip()
                author = m.group(2).strip()
        if title == fallback_title:
            h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
            if h1_m:
                title = re.sub(r"<[^>]+>", "", html.unescape(h1_m.group(1))).strip() or title
        if author == "unknown":
            u_m = re.search(rf"/people/([^/]+)/sounds/{sid}/", page)
            if u_m:
                author = html.unescape(u_m.group(1)).strip()
        return title, author
    except Exception:
        return fallback_title, "unknown"


def inspect_audio_readonly(filepath, group, category_name):
    """只读工程底线扫描：读取时长、采样率、声道、RMS/峰值、瞬态突刺密度。"""
    data, sr = sf.read(filepath, dtype="float32", always_2d=True)
    if len(data) == 0:
        raise RuntimeError("空音频")
    frames, channels = data.shape
    dur = frames / float(sr)
    mono = np.mean(data, axis=1)
    rms = float(np.sqrt(np.mean(mono ** 2)))
    peak = float(np.max(np.abs(mono)))
    rms_db = round(20.0 * math.log10(max(rms, 1e-9)), 1)
    peak_db = round(20.0 * math.log10(max(peak, 1e-9)), 1)

    diff = np.abs(np.diff(mono))
    thresh = max(0.05, 6.0 * rms)
    spikes = int(np.sum(diff > thresh))
    spikes_per_sec = round(spikes / max(dur, 1e-6), 2)

    # 工程提示徽章（只用于提示听前注意，不替代人耳评判）
    if peak >= 0.98:
        badge = "⚠️ 接近削波"
        badge_level = "warn"
    elif group == "nature":
        if category_name == "柔和炉火" and spikes_per_sec >= 1.5:
            badge = "⚠️ 有噼啪瞬态"
            badge_level = "warn"
        elif spikes_per_sec >= 3.0:
            badge = "⚠️ 瞬态较多"
            badge_level = "warn"
        else:
            badge = "平稳"
            badge_level = "ok"
    else:
        if spikes_per_sec >= 15.0:
            badge = "⚠️ 瞬态密集"
            badge_level = "warn"
        else:
            badge = "轻触发（正常瞬态）"
            badge_level = "info"

    return {
        "duration_sec": round(dur, 1),
        "samplerate": int(sr),
        "channels": int(channels),
        "peak": round(peak, 4),
        "peak_db": peak_db,
        "rms": round(rms, 5),
        "rms_db": rms_db,
        "spikes_total": spikes,
        "spikes_per_sec": spikes_per_sec,
        "badge": badge,
        "badge_level": badge_level,
        "size_kb": round(os.path.getsize(filepath) / 1024.0, 1),
    }


def find_existing_file(sound_id):
    matches = glob.glob(os.path.join(OUT_DIR, f"*_{sound_id}.hq.mp3"))
    for p in matches:
        if os.path.getsize(p) > 10 * 1024:
            return p
    return None


def fmt_duration(sec):
    sec = int(round(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def build_html(items, categories):
    cards_by_group = {"nature": [], "asmr": []}
    for it in items:
        cards_by_group[it["group"]].append(it)

    data_json = json.dumps(items, ensure_ascii=False)

    def render_cards(group_items):
        # 按分类聚合展示
        cat_order = []
        by_cat = {}
        for it in group_items:
            c = it["category"]
            if c not in by_cat:
                by_cat[c] = []
                cat_order.append(c)
            by_cat[c].append(it)

        parts = []
        for c in cat_order:
            parts.append(f'<div class="cat-block"><h3 class="cat-title">{html.escape(c)} <span>({len(by_cat[c])} 段)</span></h3><div class="grid">')
            for it in by_cat[c]:
                ch_label = "立体声" if it["channels"] >= 2 else "单声道"
                sr_label = f'{it["samplerate"] / 1000:.1f}kHz'.replace(".0kHz", "kHz")
                badge_cls = {
                    "ok": "badge-ok",
                    "warn": "badge-warn",
                    "info": "badge-info",
                }.get(it["badge_level"], "badge-info")
                parts.append(f'''
                <article class="card" data-id="{html.escape(it["id"])}" data-idx="{html.escape(it["index_str"])}" data-status="pending">
                  <div class="card-head">
                    <div class="card-ids">
                      <span class="num-pill">{html.escape(it["index_str"])}</span>
                      <span class="cat-pill">{html.escape(it["category"])}</span>
                    </div>
                    <span class="eng-badge {badge_cls}" title="每2秒/每秒瞬态参考：{it["spikes_per_sec"]}/s，峰值 {it["peak_db"]} dB">{html.escape(it["badge"])}</span>
                  </div>
                  <h4 class="sound-title" title="{html.escape(it["title"])}">{html.escape(it["title"])}</h4>
                  <div class="sound-meta">
                    <span>作者：{html.escape(it["author"])}</span>
                    <span>·</span>
                    <a href="{html.escape(it["page_url"])}" target="_blank" rel="noopener">Freesound #{html.escape(it["id"])}</a>
                  </div>
                  <div class="tech-pills">
                    <span>时长 {fmt_duration(it["duration_sec"])}</span>
                    <span>{sr_label} · {ch_label}</span>
                    <span>RMS {it["rms_db"]} dB</span>
                    <span>瞬态 {it["spikes_per_sec"]}/s</span>
                    <span>{it["size_kb"]/1024:.2f} MB</span>
                  </div>
                  <div class="audio-wrap">
                    <audio controls preload="none" src="./{urllib.parse.quote(it["filename"])}"></audio>
                  </div>
                  <div class="decision-row">
                    <button type="button" class="btn-dec btn-keep" data-act="keep">✅ 保留</button>
                    <button type="button" class="btn-dec btn-drop" data-act="drop">❌ 淘汰</button>
                    <button type="button" class="btn-dec btn-pend is-active" data-act="pending">⏳ 待定</button>
                  </div>
                  <input type="text" class="note-input" placeholder="听感备注（如：暖且稳 / 有底噪 / 噼啪太响 / 接缝有感）" />
                </article>''')
            parts.append("</div></div>")
        return "\n".join(parts)

    nature_html = render_cards(cards_by_group["nature"])
    asmr_html = render_cards(cards_by_group["asmr"])

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>夜息 · CC0 候选素材试听挑选（v3）</title>
<style>
  :root {{
    --y-bg: #0b0814;
    --y-bg2: #120d22;
    --y-card: rgba(25, 19, 44, 0.72);
    --y-card-hi: rgba(36, 28, 62, 0.88);
    --y-border: rgba(218, 200, 255, 0.14);
    --y-border-hi: rgba(164, 140, 248, 0.48);
    --y-accent: #8e74e8;
    --y-accent-soft: rgba(142, 116, 232, 0.18);
    --y-text: #f3effb;
    --y-sub: #a99dc5;
    --y-muted: #7e729c;
    --y-ok: #4ade80;
    --y-ok-bg: rgba(74, 222, 128, 0.14);
    --y-warn: #fbbf24;
    --y-warn-bg: rgba(251, 191, 36, 0.14);
    --y-drop: #f87171;
    --y-drop-bg: rgba(248, 113, 113, 0.14);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    color: var(--y-text);
    background: radial-gradient(circle at 20% 0%, #1c1338 0%, var(--y-bg) 55%);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    line-height: 1.55;
    min-height: 100vh;
  }}
  .sticky-bar {{
    position: sticky;
    top: 0;
    z-index: 50;
    backdrop-filter: blur(16px);
    background: rgba(11, 8, 20, 0.84);
    border-bottom: 1px solid var(--y-border);
    padding: 12px 24px;
  }}
  .bar-inner {{
    max-width: 1320px;
    margin: 0 auto;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .brand h1 {{
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.4px;
  }}
  .brand small {{
    color: var(--y-sub);
    font-size: 12px;
  }}
  .stats {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 13px;
  }}
  .stat-pill {{
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid var(--y-border);
    background: rgba(255, 255, 255, 0.04);
    cursor: pointer;
    user-select: none;
    transition: all 0.15s ease;
  }}
  .stat-pill.is-filter-active {{
    border-color: var(--y-accent);
    background: var(--y-accent-soft);
  }}
  .stat-keep {{ color: var(--y-ok); }}
  .stat-drop {{ color: var(--y-drop); }}
  .stat-pend {{ color: var(--y-sub); }}
  .actions {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .loop-toggle {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--y-sub);
    cursor: pointer;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid var(--y-border);
    background: rgba(255, 255, 255, 0.03);
  }}
  .btn-copy {{
    appearance: none;
    border: 1px solid rgba(164, 140, 248, 0.5);
    background: linear-gradient(135deg, #7c5fe6, #5e42c4);
    color: #fff;
    padding: 8px 16px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.12s ease, filter 0.15s ease;
  }}
  .btn-copy:hover {{ filter: brightness(1.1); }}
  .btn-copy:active {{ transform: scale(0.98); }}
  .btn-reset {{
    appearance: none;
    border: 1px solid var(--y-border);
    background: transparent;
    color: var(--y-muted);
    padding: 7px 10px;
    border-radius: 8px;
    font-size: 12px;
    cursor: pointer;
  }}
  .btn-reset:hover {{ color: var(--y-text); border-color: var(--y-border-hi); }}

  main {{
    max-width: 1320px;
    margin: 0 auto;
    padding: 24px 24px 64px;
  }}
  .intro-note {{
    background: var(--y-card);
    border: 1px solid var(--y-border);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 24px;
    color: var(--y-sub);
    font-size: 13px;
  }}
  .intro-note strong {{ color: var(--y-text); }}
  .section-head {{
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin: 28px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--y-border);
  }}
  .section-head h2 {{
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }}
  .section-head span {{
    color: var(--y-muted);
    font-size: 13px;
  }}
  .cat-block {{ margin-bottom: 26px; }}
  .cat-title {{
    margin: 14px 0 12px;
    font-size: 15px;
    color: #d8cefa;
    font-weight: 600;
  }}
  .cat-title span {{
    color: var(--y-muted);
    font-weight: 400;
    font-size: 12px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: var(--y-card);
    border: 1px solid var(--y-border);
    border-radius: 16px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
  }}
  .card.is-playing {{
    border-color: var(--y-accent);
    background: var(--y-card-hi);
    box-shadow: 0 0 24px rgba(142, 116, 232, 0.22);
  }}
  .card[data-status="keep"] {{
    border-color: rgba(74, 222, 128, 0.55);
  }}
  .card[data-status="drop"] {{
    opacity: 0.62;
    border-color: rgba(248, 113, 113, 0.35);
  }}
  .card.is-hidden {{ display: none; }}
  .card-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }}
  .card-ids {{ display: flex; align-items: center; gap: 6px; }}
  .num-pill {{
    background: var(--y-accent-soft);
    color: #d7cbff;
    border: 1px solid rgba(142, 116, 232, 0.35);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }}
  .cat-pill {{
    font-size: 12px;
    color: var(--y-sub);
  }}
  .eng-badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 500;
  }}
  .badge-ok {{ color: var(--y-ok); background: var(--y-ok-bg); }}
  .badge-warn {{ color: var(--y-warn); background: var(--y-warn-bg); }}
  .badge-info {{ color: #a5b4fc; background: rgba(165, 180, 252, 0.14); }}
  .sound-title {{
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--y-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .sound-meta {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--y-muted);
    flex-wrap: wrap;
  }}
  .sound-meta a {{
    color: #b7a5f6;
    text-decoration: none;
  }}
  .sound-meta a:hover {{ text-decoration: underline; }}
  .tech-pills {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }}
  .tech-pills span {{
    font-size: 11px;
    color: var(--y-sub);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    padding: 2px 7px;
    border-radius: 6px;
  }}
  .audio-wrap audio {{
    width: 100%;
    height: 36px;
    border-radius: 8px;
    color-scheme: dark;
  }}
  .decision-row {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
  }}
  .btn-dec {{
    appearance: none;
    border: 1px solid var(--y-border);
    background: rgba(255, 255, 255, 0.03);
    color: var(--y-sub);
    padding: 6px 8px;
    border-radius: 8px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.12s ease;
  }}
  .btn-dec:hover {{ border-color: var(--y-border-hi); color: var(--y-text); }}
  .btn-keep.is-active {{
    background: var(--y-ok-bg);
    border-color: var(--y-ok);
    color: var(--y-ok);
    font-weight: 600;
  }}
  .btn-drop.is-active {{
    background: var(--y-drop-bg);
    border-color: var(--y-drop);
    color: var(--y-drop);
    font-weight: 600;
  }}
  .btn-pend.is-active {{
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(218, 200, 255, 0.32);
    color: var(--y-text);
  }}
  .note-input {{
    width: 100%;
    border: 1px solid var(--y-border);
    background: rgba(8, 6, 15, 0.55);
    color: var(--y-text);
    padding: 7px 10px;
    border-radius: 8px;
    font-size: 12px;
    outline: none;
  }}
  .note-input:focus {{ border-color: var(--y-accent); }}
  .export-box {{
    margin-top: 28px;
    background: var(--y-card);
    border: 1px solid var(--y-border);
    border-radius: 14px;
    padding: 16px;
    display: none;
  }}
  .export-box.is-open {{ display: block; }}
  .export-box textarea {{
    width: 100%;
    min-height: 160px;
    background: #08060f;
    color: var(--y-text);
    border: 1px solid var(--y-border);
    border-radius: 8px;
    padding: 10px;
    font-family: Consolas, monospace;
    font-size: 12px;
    margin-top: 8px;
  }}
  .toast {{
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: #2b2052;
    border: 1px solid var(--y-accent);
    color: #fff;
    padding: 10px 18px;
    border-radius: 999px;
    font-size: 13px;
    opacity: 0;
    pointer-events: none;
    transition: all 0.2s ease;
    z-index: 100;
  }}
  .toast.is-show {{
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }}
</style>
</head>
<body>
  <header class="sticky-bar">
    <div class="bar-inner">
      <div class="brand">
        <h1>🌙 夜息 · 候选素材试听台</h1>
        <small>CC0 原样高码率 · 零后处理</small>
      </div>
      <div class="stats">
        <span class="stat-pill is-filter-active" data-filter="all">全部 <b id="cntAll">{len(items)}</b></span>
        <span class="stat-pill stat-keep" data-filter="keep">✅ 保留 <b id="cntKeep">0</b></span>
        <span class="stat-pill stat-drop" data-filter="drop">❌ 淘汰 <b id="cntDrop">0</b></span>
        <span class="stat-pill stat-pend" data-filter="pending">⏳ 待定 <b id="cntPend">{len(items)}</b></span>
      </div>
      <div class="actions">
        <label class="loop-toggle">
          <input type="checkbox" id="loopToggle" />
          <span>循环试听（检接缝）</span>
        </label>
        <button type="button" class="btn-copy" id="copyBtn">📋 一键复制挑选结果</button>
        <button type="button" class="btn-reset" id="resetBtn">清空标记</button>
      </div>
    </div>
  </header>

  <main>
    <div class="intro-note">
      <strong>使用说明：</strong> 所有音频均为 Freesound <strong>CC0 授权</strong>原始 <code>-hq.mp3</code>，未做任何滤波/降噪/压缩。点击播放会自动暂停其它音频；勾选右上角「循环试听」可重点听首尾衔接。选好后点<strong>「一键复制挑选结果」</strong>发回给我，即可自动入库到正式素材库并归档淘汰项。
    </div>

    <section>
      <div class="section-head">
        <h2>一、自然助眠补缺与质感梯度</h2>
        <span>补齐林风、炉火、长海浪、长溪流、柔和雨、山谷风</span>
      </div>
      {nature_html}
    </section>

    <section>
      <div class="section-head">
        <h2>二、经典轻 ASMR 触发音试水</h2>
        <span>探索翻书、写字、轻敲/毛刷是否适合加入</span>
      </div>
      {asmr_html}
    </section>

    <section class="export-box" id="exportBox">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong>挑选结果文本（可直接全选复制）</strong>
        <button type="button" class="btn-reset" onclick="document.getElementById('exportBox').classList.remove('is-open')">收起</button>
      </div>
      <textarea id="exportText" readonly></textarea>
    </section>
  </main>

  <div class="toast" id="toast">已复制到剪贴板</div>

<script>
(function() {{
  const STORAGE_KEY = "yexi_candidates_v3_decisions";
  const ITEMS = {data_json};
  const ITEM_MAP = Object.fromEntries(ITEMS.map(x => [x.id, x]));
  let state = {{}};
  try {{
    state = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}");
  }} catch (e) {{
    state = {{}};
  }}
  let activeFilter = "all";

  const cards = Array.from(document.querySelectorAll(".card"));
  const audios = Array.from(document.querySelectorAll("audio"));

  function saveState() {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }} catch (e) {{}}
  }}

  function showToast(msg) {{
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.classList.add("is-show");
    setTimeout(() => t.classList.remove("is-show"), 2200);
  }}

  function refreshCounts() {{
    let keep = 0, drop = 0, pend = 0;
    cards.forEach(c => {{
      const st = c.dataset.status || "pending";
      if (st === "keep") keep++;
      else if (st === "drop") drop++;
      else pend++;
      c.classList.toggle("is-hidden", activeFilter !== "all" && st !== activeFilter);
    }});
    document.getElementById("cntKeep").textContent = keep;
    document.getElementById("cntDrop").textContent = drop;
    document.getElementById("cntPend").textContent = pend;
  }}

  // 恢复状态并绑定事件
  cards.forEach(card => {{
    const id = card.dataset.id;
    const saved = state[id] || {{ status: "pending", note: "" }};
    const noteEl = card.querySelector(".note-input");
    noteEl.value = saved.note || "";

    function setStatus(st) {{
      card.dataset.status = st;
      card.querySelectorAll(".btn-dec").forEach(b => {{
        b.classList.toggle("is-active", b.dataset.act === st);
      }});
      state[id] = {{ status: st, note: noteEl.value.trim() }};
      saveState();
      refreshCounts();
    }}

    setStatus(saved.status || "pending");
    card.querySelectorAll(".btn-dec").forEach(btn => {{
      btn.addEventListener("click", () => setStatus(btn.dataset.act));
    }});
    noteEl.addEventListener("input", () => {{
      state[id] = {{ status: card.dataset.status || "pending", note: noteEl.value.trim() }};
      saveState();
    }});
  }});

  // 互斥播放
  audios.forEach(aud => {{
    aud.addEventListener("play", () => {{
      audios.forEach(other => {{
        if (other !== aud && !other.paused) other.pause();
      }});
      cards.forEach(c => c.classList.remove("is-playing"));
      aud.closest(".card").classList.add("is-playing");
    }});
    aud.addEventListener("pause", () => {{
      aud.closest(".card").classList.remove("is-playing");
    }});
    aud.addEventListener("ended", () => {{
      aud.closest(".card").classList.remove("is-playing");
    }});
  }});

  // 循环切换
  document.getElementById("loopToggle").addEventListener("change", e => {{
    const on = e.target.checked;
    audios.forEach(a => {{ a.loop = on; }});
  }});

  // 顶部过滤
  document.querySelectorAll(".stat-pill").forEach(pill => {{
    pill.addEventListener("click", () => {{
      activeFilter = pill.dataset.filter;
      document.querySelectorAll(".stat-pill").forEach(p => p.classList.remove("is-filter-active"));
      pill.classList.add("is-filter-active");
      refreshCounts();
    }});
  }});

  // 一键复制
  document.getElementById("copyBtn").addEventListener("click", async () => {{
    const keeps = [], drops = [], pends = [];
    ITEMS.forEach(it => {{
      const s = state[it.id] || {{ status: "pending", note: "" }};
      const line = `- [${{it.index_str}}] ${{it.category}} | ${{it.filename}} (id:${{it.id}}) | ${{it.title}}` + (s.note ? ` | 备注: ${{s.note}}` : "");
      if (s.status === "keep") keeps.push(line);
      else if (s.status === "drop") drops.push(line);
      else pends.push(line);
    }});
    const report = [
      "=== 夜息候选素材挑选结果（v3） ===",
      `保留 (${{keeps.length}}):`,
      ...(keeps.length ? keeps : ["（无）"]),
      "",
      `淘汰 (${{drops.length}}):`,
      ...(drops.length ? drops : ["（无）"]),
      "",
      `待定 (${{pends.length}}):`,
      ...(pends.length ? pends : ["（无）"]),
    ].join("\\n");

    const box = document.getElementById("exportBox");
    const ta = document.getElementById("exportText");
    ta.value = report;
    box.classList.add("is-open");

    let copied = false;
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      try {{
        await navigator.clipboard.writeText(report);
        copied = true;
      }} catch (e) {{}}
    }}
    if (!copied) {{
      ta.select();
      try {{ copied = document.execCommand("copy"); }} catch (e) {{}}
    }}
    showToast(copied ? "已复制挑选结果，直接粘贴发给我即可" : "请从下方文本框手动全选复制");
  }});

  // 清空标记
  document.getElementById("resetBtn").addEventListener("click", () => {{
    if (!confirm("确定清空当前所有保留/淘汰标记和备注吗？")) return;
    state = {{}};
    saveState();
    cards.forEach(c => {{
      c.querySelector(".note-input").value = "";
      c.dataset.status = "pending";
      c.querySelectorAll(".btn-dec").forEach(b => b.classList.toggle("is-active", b.dataset.act === "pending"));
    }});
    refreshCounts();
    showToast("已清空所有标记");
  }});
}})();
</script>
</body>
</html>
'''


def load_cached_items():
    """读取现有 manifest.json 与磁盘已有 .hq.mp3，复用已下完素材并补齐缺失元数据。"""
    cat_map = {c["name"]: c for c in CATEGORIES}
    items_by_cat = {c["name"]: [] for c in CATEGORIES}

    manifest_map = {}
    manifest_path = os.path.join(OUT_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for it in data.get("items", []):
                if isinstance(it, dict) and "id" in it:
                    manifest_map[str(it["id"])] = it
        except Exception:
            pass

    # 扫描磁盘上的正式候选文件
    disk_files = []
    for fname in sorted(os.listdir(OUT_DIR)):
        if fname.startswith("_") or fname.startswith(".") or not fname.endswith(".hq.mp3"):
            continue
        m = re.match(r"^(\d+)_([^_]+)_(\d+)\.hq\.mp3$", fname)
        if not m:
            continue
        seq_num, cname, sid = int(m.group(1)), m.group(2), m.group(3)
        if cname not in cat_map:
            continue
        fpath = os.path.join(OUT_DIR, fname)
        if os.path.getsize(fpath) <= 10 * 1024:
            continue
        disk_files.append((seq_num, cname, sid, fname, fpath))

    seen_disk_ids = set()
    for _, cname, sid, fname, fpath in disk_files:
        if sid in seen_disk_ids:
            continue
        seen_disk_ids.add(sid)
        cat = cat_map[cname]
        cached = manifest_map.get(sid)
        if cached and cached.get("category") == cname:
            item = dict(cached)
            item["filename"] = fname
            # 确认磁盘音频可读
            try:
                if "duration_sec" not in item or "spikes_per_sec" not in item:
                    item.update(inspect_audio_readonly(fpath, cat["group"], cname))
                else:
                    sf.info(fpath)
            except Exception as e:
                print(f"  ⚠️ 已有文件损坏跳过 {fname}: {e}", flush=True)
                continue
        else:
            try:
                metrics = inspect_audio_readonly(fpath, cat["group"], cname)
            except Exception as e:
                print(f"  ⚠️ 已有文件损坏跳过 {fname}: {e}", flush=True)
                continue
            title, author = fetch_sound_page_meta(sid, fname)
            item = {
                "index": 0,
                "index_str": "00",
                "group": cat["group"],
                "group_label": cat["group_label"],
                "category": cname,
                "id": sid,
                "title": title,
                "author": author,
                "hq_url": f"https://freesound.org/s/{sid}/",
                "page_url": f"https://freesound.org/s/{sid}/",
                "mp3_url": "",
                "filename": fname,
                "query": "cached",
                "sort_by": "cached",
                **metrics,
            }
            print(f"  [补齐元数据] {fname} -> {title} (by {author})", flush=True)

        items_by_cat[cname].append(item)

    return items_by_cat


def renumber_and_persist(items_by_cat):
    """按 CATEGORIES 统一顺序重排 01..N 编号（两段安全重命名防冲突），实时写入 manifest 与 HTML。"""
    collected = []
    rename_plan = []
    seq = 1

    for cat in CATEGORIES:
        cname = cat["name"]
        for it in items_by_cat[cname]:
            idx_str = f"{seq:02d}"
            old_fname = it["filename"]
            new_fname = f"{idx_str}_{cname}_{it['id']}.hq.mp3"
            old_path = os.path.join(OUT_DIR, old_fname)
            new_path = os.path.join(OUT_DIR, new_fname)
            if os.path.exists(old_path) and old_fname != new_fname:
                tmp_path = os.path.join(OUT_DIR, f"._renaming_{it['id']}.hq.mp3")
                rename_plan.append((old_path, tmp_path, new_path))
            it["index"] = seq
            it["index_str"] = idx_str
            it["filename"] = new_fname
            collected.append(it)
            seq += 1

    for old_path, tmp_path, _ in rename_plan:
        if os.path.exists(old_path):
            os.replace(old_path, tmp_path)
    for _, tmp_path, new_path in rename_plan:
        if os.path.exists(tmp_path):
            os.replace(tmp_path, new_path)

    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(collected),
        "items": collected,
    }
    manifest_path = os.path.join(OUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    html_path = os.path.join(OUT_DIR, "试听挑选.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(collected, CATEGORIES))

    return collected, manifest_path, html_path


def download_and_inspect_worker(cand, group, cname):
    """线程池 worker：下载到临时文件名并做只读工程扫描。"""
    sid = cand["id"]
    tmp_dest = os.path.join(OUT_DIR, f"_tmp_{cname}_{sid}.hq.mp3")
    try:
        if os.path.exists(tmp_dest) and os.path.getsize(tmp_dest) > 10 * 1024:
            pass
        else:
            download_raw_hq(cand["hq_url"], tmp_dest)
        metrics = inspect_audio_readonly(tmp_dest, group, cname)
        return {"ok": True, "cand": cand, "tmp_dest": tmp_dest, "metrics": metrics}
    except Exception as e:
        for p in (tmp_dest, tmp_dest + ".part"):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        return {"ok": False, "cand": cand, "error": str(e)}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # 清理上次中断可能留下的临时文件
    for f in os.listdir(OUT_DIR):
        if f.startswith("_tmp_") or f.startswith("._renaming_"):
            try:
                os.remove(os.path.join(OUT_DIR, f))
            except OSError:
                pass

    blacklist = load_blacklist()
    items_by_cat = load_cached_items()
    cached_ids = {it["id"] for lst in items_by_cat.values() for it in lst}
    seen_ids = set(blacklist) | cached_ids

    print(f"已加载去重黑名单：{len(blacklist)} 个 ID；复用磁盘已有素材：{len(cached_ids)} 条", flush=True)
    collected, manifest_path, html_path = renumber_and_persist(items_by_cat)
    print(f"已完成既有素材重编与落盘（{len(collected)} 条）\n", flush=True)

    for cat in CATEGORIES:
        cname = cat["name"]
        target = cat["target"]
        group = cat["group"]
        cat_items = items_by_cat[cname]

        if len(cat_items) >= target:
            print(f"=== [{cat['group_label']}] {cname}：已有 {len(cat_items)}/{target} 条，直接复用跳过检索 ===", flush=True)
            for it in cat_items:
                print(f"  = [{it['index_str']}] #{it['id']} | {it['duration_sec']}s | {it['badge']} | {it['title'][:55]}", flush=True)
            print(flush=True)
            continue

        print(f"=== [{cat['group_label']}] {cname} (已有 {len(cat_items)}/{target}，需补 {target - len(cat_items)} 条) ===", flush=True)
        passes = [True, False] if cat["avoid_crackl"] else [False]
        search_cache = {}

        for dur_filter in cat["duration_filters"]:
            if len(cat_items) >= target:
                break
            for skip_crackl in passes:
                if len(cat_items) >= target:
                    break
                if cat["avoid_crackl"] and not skip_crackl:
                    print(f"  [{cname}] 放宽 crackl 标题过滤（仍检测瞬态密度）...", flush=True)

                # 先收集当前 (dur_filter, skip_crackl) 下的可用候选
                candidates = []
                need_now = target - len(cat_items)
                want_pool = need_now + 4

                for sort_by in ["rating", "downloads_desc"]:
                    if len(candidates) >= want_pool:
                        break
                    for query in cat["queries"]:
                        if len(candidates) >= want_pool:
                            break
                        cache_key = (dur_filter, query, sort_by)
                        if cache_key not in search_cache:
                            try:
                                time.sleep(0.8)
                                search_cache[cache_key] = fetch_search_results(query, dur_filter, sort_by)
                            except Exception as e:
                                print(f"  搜索失败 ({dur_filter} / {query} / {sort_by}): {e}", flush=True)
                                search_cache[cache_key] = []

                        for r in search_cache[cache_key]:
                            sid = r["id"]
                            if sid in seen_ids:
                                continue
                            noisy, _ = is_title_noisy(r["title"], group, skip_crackl=skip_crackl)
                            if noisy:
                                continue
                            seen_ids.add(sid)
                            c_copy = dict(r)
                            c_copy["query"] = query
                            c_copy["sort_by"] = sort_by
                            candidates.append(c_copy)
                            if len(candidates) >= want_pool:
                                break

                # 分批并发下载（每批取 need + 2 个，最多 4 并发）
                pos = 0
                while len(cat_items) < target and pos < len(candidates):
                    need = target - len(cat_items)
                    batch_n = min(len(candidates) - pos, need + 2)
                    batch = candidates[pos:pos + batch_n]
                    pos += batch_n

                    print(f"  并发下载 {len(batch)} 个候选（{dur_filter}）...", flush=True)
                    with ThreadPoolExecutor(max_workers=4) as pool:
                        futs = [pool.submit(download_and_inspect_worker, c, group, cname) for c in batch]
                        results = [f.result() for f in futs]

                    for res in results:
                        cand = res["cand"]
                        sid = cand["id"]
                        if not res["ok"]:
                            print(f"  跳过 #{sid} ({cand['title'][:40]}): {res['error']}", flush=True)
                            continue
                        tmp_dest = res["tmp_dest"]
                        metrics = res["metrics"]

                        if len(cat_items) >= target:
                            try:
                                os.remove(tmp_dest)
                            except OSError:
                                pass
                            continue

                        if cname == "柔和炉火" and skip_crackl and metrics["spikes_per_sec"] > 8.0:
                            print(f"  跳过噼啪过密炉火 #{sid} ({metrics['spikes_per_sec']}/s): {cand['title'][:40]}", flush=True)
                            try:
                                os.remove(tmp_dest)
                            except OSError:
                                pass
                            continue

                        temp_final_name = f"99_{cname}_{sid}.hq.mp3"
                        temp_final_path = os.path.join(OUT_DIR, temp_final_name)
                        os.replace(tmp_dest, temp_final_path)

                        item = {
                            "index": 0,
                            "index_str": "99",
                            "group": group,
                            "group_label": cat["group_label"],
                            "category": cname,
                            "id": sid,
                            "title": cand["title"],
                            "author": cand["author"],
                            "hq_url": cand["page_url"],
                            "page_url": cand["page_url"],
                            "mp3_url": cand["hq_url"],
                            "filename": temp_final_name,
                            "query": cand["query"],
                            "sort_by": cand["sort_by"],
                            **metrics,
                        }
                        cat_items.append(item)
                        print(f"  + #{sid} | {metrics['duration_sec']}s | {metrics['badge']} | {cand['title'][:55]}", flush=True)

        if len(cat_items) < target:
            print(f"  ⚠️ [{cname}] 仅采集到 {len(cat_items)}/{target} 条", flush=True)

        # 逐类增量重编落盘
        collected, manifest_path, html_path = renumber_and_persist(items_by_cat)
        print(f"  -> [{cname}] 已落盘，当前总计 {len(collected)} 条\n", flush=True)

    print(f"完成！共采集 {len(collected)} 条候选素材。", flush=True)
    print(f"清单：{manifest_path}", flush=True)
    print(f"试听页：{html_path}", flush=True)


if __name__ == "__main__":
    main()
