# 结构化 CC0 声音素材库加载与检索工具（41 段已验收素材单一真相源）
# 铁律：只做元数据组织与声学标签检索，绝不做音频后处理

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE, "sound_catalog.json")


def _load_catalog():
    if not os.path.exists(CATALOG_PATH):
        raise RuntimeError(f"缺少声音标签库文件：{CATALOG_PATH}")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = []
    for it in raw.get("items", []):
        if not isinstance(it, dict):
            continue
        rel = str(it.get("rel_path") or "").strip()
        if not rel:
            continue
        full = os.path.join(BASE, rel)
        if os.path.isfile(full):
            items.append(it)
    return items


ALL_SOUNDS = _load_catalog()
BY_FILENAME = {it["filename"]: it for it in ALL_SOUNDS}
BY_RELPATH = {it["rel_path"]: it for it in ALL_SOUNDS}
ALLOWED_TRACK_FILES = [it["filename"] for it in ALL_SOUNDS]

# 素材分层：free 是免费用户能用的，premium 需要解锁全库。
# 分层原则是「免费不降级、付费是加法」——每个场景的默认首选都在免费层，
# 付费买到的是同场景的更多变体和全部 ASMR 深度。
FREE_RELPATHS = [it["rel_path"] for it in ALL_SOUNDS if it.get("tier") == "free"]
ALL_RELPATHS = [it["rel_path"] for it in ALL_SOUNDS]
PREMIUM_COUNT = len(ALL_SOUNDS) - len(FREE_RELPATHS)


def relpaths_for(unlocked):
    # unlocked 为 True 返回全库，False 只返回免费层
    if unlocked:
        return list(ALL_RELPATHS)
    return list(FREE_RELPATHS)


def tier_of(path_or_name):
    it = get_item(path_or_name)
    if not it:
        return ""
    return it.get("tier", "premium")


def get_item(path_or_name):
    if not path_or_name:
        return None
    s = str(path_or_name).strip()
    if s in BY_RELPATH:
        return BY_RELPATH[s]
    base = os.path.basename(s)
    return BY_FILENAME.get(base)


def build_track_catalog_dict():
    out = {}
    for it in ALL_SOUNDS:
        out[it["filename"]] = {
            "name": it["name"],
            "layer": it["layer"],
            "pan": float(it.get("default_pan", 0.0)),
            "mode": it.get("default_mode", "loop"),
            "density": float(it.get("default_density", 0.4)),
            "role_note": it.get("role_note", it["desc"][:12]),
            "scene": it["scene"],
            "group": it["group"],
            "warmth": it.get("warmth", "neutral"),
            "dynamics": it.get("dynamics", "steady"),
            "intensity": it.get("intensity", "medium"),
            "distance": it.get("distance", "medium"),
            "tags": list(it.get("tags", [])),
            "avoid_tags": list(it.get("avoid_tags", [])),
            "rel_path": it["rel_path"],
            "tier": it.get("tier", "premium"),
            "duration_sec": float(it.get("duration_sec", 60.0)),
            "note": it.get("note", ""),
        }
    return out


def build_library_by_scene():
    """生成按场景分组的默认候选权重表，供素材执行层使用。"""
    lib = {
        "rain": [
            ("product_assets/母带_城市夜雨_CC0.mp3", 1.0),
            ("product_assets/备选_大雨打树叶_CC0.mp3", 0.0),
            ("scene_assets/柔和雨.hq.mp3", 0.0),
            ("scene_assets/乡村小雨.hq.mp3", 0.0),
            ("scene_assets/帐篷雨_小帐篷大雨_592996.hq.mp3", 0.0),
        ],
        "ocean": [
            ("scene_assets/海浪_远海.hq.mp3", 1.0),
            ("scene_assets/海浪_湖海柔浪_451532.hq.mp3", 0.0),
            ("scene_assets/海浪_沙滩柔浪_325197.hq.mp3", 0.0),
            ("scene_assets/海浪_黑海.hq.mp3", 0.0),
        ],
        "stream": [
            ("scene_assets/溪流.hq.mp3", 1.0),
            ("scene_assets/溪流_柔和河水_707576.hq.mp3", 0.0),
            ("scene_assets/溪流_小溪循环_767320.hq.mp3", 0.0),
            ("scene_assets/溪流_野外溪水_180732.hq.mp3", 0.0),
        ],
        "thunder": [
            ("product_assets/母带_城市夜雨_CC0.mp3", 0.7),
            ("scene_assets/远雷.hq.mp3", 0.3),
        ],
        "wind": [
            ("scene_assets/林风_树林波浪风_637989.hq.mp3", 0.7),
            ("scene_assets/夜风.hq.mp3", 0.3),
            ("scene_assets/林风_Akacie_73708.hq.mp3", 0.0),
            ("scene_assets/微风_小镇傍晚风_321904.hq.mp3", 0.0),
            ("scene_assets/微风_麦田柔风_447810.hq.mp3", 0.0),
        ],
        "forest": [
            ("scene_assets/虫鸣.hq.mp3", 0.5),
            ("scene_assets/夜风.hq.mp3", 0.5),
            ("scene_assets/鸟鸣_夜莺鸣叫_853566.hq.mp3", 0.0),
            ("scene_assets/林风_Akacie_73708.hq.mp3", 0.0),
        ],
        "fire": [
            ("scene_assets/炉火_壁炉低燃_836535.hq.mp3", 1.0),
            ("scene_assets/炉火_夜营氛围_766127.hq.mp3", 0.0),
            ("scene_assets/炉火_营地篝火_62487.hq.mp3", 0.0),
        ],
        "asmr": [
            ("scene_assets/ASMR_麦套轻扫抓挠_803595.hq.mp3", 0.65),
            ("scene_assets/ASMR_采耳_690078.hq.mp3", 0.35),
        ],
        "mix": [
            ("product_assets/母带_城市夜雨_CC0.mp3", 0.7),
            ("scene_assets/雨中低鸣.hq.mp3", 0.3),
        ],
    }

    # 补充 asmr 其他已验收条目为 0.0 备选，并过滤掉万一不存在的路径
    asmr_existing = {rel for rel, _ in lib["asmr"]}
    for it in ALL_SOUNDS:
        if it["scene"] == "asmr" and it["rel_path"] not in asmr_existing:
            lib["asmr"].append((it["rel_path"], 0.0))

    cleaned = {}
    for sc, pairs in lib.items():
        valid = [(rel, w) for rel, w in pairs if rel in BY_RELPATH]
        if valid:
            cleaned[sc] = valid
    return cleaned


def build_prompt_catalog_text():
    """按三层结构紧凑格式化全部素材清单，供大模型编排时查阅。"""
    layers = [
        ("bed", "【底幕层 bed（建议每次主选 1 个铺底，避免多个满频雨声/海浪/炉火互糊）】"),
        ("texture", "【纹理层 texture（可叠加 0~2 个铺出枝叶、夜风、暖意或稳定近场触发）】"),
        ("accent", "【点缀层 accent（适合设 intermittent 偶发模式留出呼吸感；短触发音勿长时间高频硬循环）】"),
    ]
    lines = []
    for layer_key, heading in layers:
        lines.append(heading)
        for it in ALL_SOUNDS:
            if it["layer"] != layer_key:
                continue
            avoid = ",".join(it.get("avoid_tags") or [])
            avoid_part = f" | 避雷:{avoid}" if avoid else ""
            note = str(it.get("note") or "").strip()
            note_part = f"（{note}）" if "慢一点" in note or "峰值" in note or "自带" in note else ""
            lines.append(
                f"- {it['filename']} | {it['name']} [{it['scene']}] "
                f"({it['warmth']}/{it['dynamics']}/{it['intensity']}/{it['distance']}, "
                f"{int(round(it['duration_sec']))}s): {it['desc']}{note_part}{avoid_part}"
            )
        lines.append("")
    return "\n".join(lines).strip()


def find_alternatives(
    current_filename,
    prefer_softer=False,
    prefer_warmer=False,
    prefer_more_detail=False,
    exclude_filenames=None,
    avoid_tags=None,
):
    """按同场景与声学标签找更柔/更暖/更有细节的已验收替代素材。"""
    cur = get_item(current_filename)
    excluded = {os.path.basename(str(x)) for x in (exclude_filenames or []) if x}
    if cur:
        excluded.add(cur["filename"])
    elif current_filename:
        excluded.add(os.path.basename(str(current_filename)))

    avoid_set = {str(t) for t in (avoid_tags or []) if t}

    scored = []
    for it in ALL_SOUNDS:
        if it["filename"] in excluded:
            continue
        it_avoids = set(it.get("avoid_tags") or [])
        if avoid_set and (it_avoids & avoid_set):
            continue

        score = 0.0
        if cur:
            if it["scene"] == cur["scene"]:
                score += 50.0
            elif it["group"] == cur["group"]:
                score += 25.0
            else:
                continue
            if it["layer"] == cur["layer"]:
                score += 12.0

        if prefer_softer:
            if it["intensity"] == "soft":
                score += 22.0
            elif it["intensity"] == "medium":
                score += 8.0
            else:
                score -= 12.0
            if it["dynamics"] == "steady":
                score += 14.0
            elif it["dynamics"] in ("gentle_swell", "natural"):
                score += 6.0
            elif it["dynamics"] == "spiky":
                score -= 20.0
            if "吵" in it_avoids or "尖锐" in it_avoids or "削波" in it_avoids:
                score -= 18.0

        if prefer_warmer:
            if it["warmth"] == "warm":
                score += 20.0
            elif it["warmth"] == "neutral":
                score += 5.0
            else:
                score -= 10.0

        if prefer_more_detail:
            if it["intensity"] in ("rich", "medium"):
                score += 16.0
            if it["layer"] in ("texture", "accent"):
                score += 12.0
            if it["distance"] == "close":
                score += 6.0

        # 轻微偏向更长、更稳的素材
        score += min(it.get("duration_sec", 30.0) / 100.0, 3.0)
        scored.append((score, it))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [it for _, it in scored]
