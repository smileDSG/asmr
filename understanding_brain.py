# 理解脑：一句话 → 结构化意图（三层降级）
# 主力：Qwen3.8-Flash（云，严格 JSON Schema）
# 降级1：本地 Spark 4B
# 降级2：规则匹配
# 任一成功即停。核心铁律：AI 只做理解和解析，绝不判断音质、绝不后处理。

import json
import os
import sys
import urllib.request

import qwen_client
import sound_catalog

# 本地模型地址需显式配置环境变量 LOCAL_LLM_URL，避免误请求 8080 静态端口
LOCAL_URL = os.environ.get("LOCAL_LLM_URL", "").strip()


def from_local(say):
    if not LOCAL_URL:
        raise RuntimeError("未配置本地模型")
    # 降级1：本地模型，让它吐 JSON（弱 schema，靠提示词约束 + 事后校验）
    req = urllib.request.Request(LOCAL_URL, data=json.dumps({
        "model": "local-model",
        "messages": [
            {"role": "system", "content": qwen_client.SYSTEM_PROMPT},
            {"role": "user", "content": say}
        ],
        "temperature": 0.2
    }).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode("utf-8"))
    text = result["choices"][0]["message"]["content"]
    # 本地模型可能带 ```json 包裹，清掉
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].strip()
    return json.loads(text)


def from_rules(say):
    # 降级2：纯关键词规则，不依赖任何模型
    intent = {
        "scene": "rain", "scene_detail": "窗外雨声", "mood": "sleep",
        "warmth": "neutral", "dynamics": "natural", "avoid": [],
        "duration_minutes": 30, "confidence": 0.5
    }
    # 先把"不要/别/没有"后面的东西剔除，再判断场景，避免"不要雷声"被当成要雷
    positive = say
    for bad in [
        "不要雷声", "不要打雷", "不要雷", "别打雷", "没有雷",
        "不要音乐", "不要人声", "不要炉火", "不要火", "不要鸟", "不要采耳", "不要敲",
    ]:
        positive = positive.replace(bad, "")

    # 场景（优先识别炉火与近场 ASMR，再识别自然水域/风/雨）
    if any(k in positive for k in ["炉火", "壁炉", "篝火", "炭火", "营火"]):
        intent["scene"] = "fire"
        intent["scene_detail"] = "温暖壁炉炉火"
    elif any(k in positive for k in [
        "采耳", "掏耳", "羽毛", "毛刷", "梳头", "梳发", "麦套", "扫麦",
        "翻书", "翻页", "写字", "铅笔", "轻敲", "敲击", "抓挠", "海绵",
        "糖纸", "揉捏", "搓手", "asmr", "ASMR",
    ]):
        intent["scene"] = "asmr"
        intent["scene_detail"] = "近场轻柔 ASMR 触发音"
    elif any(k in positive for k in ["海", "潮汐", "浪"]):
        intent["scene"] = "ocean"
        intent["scene_detail"] = "远处的海浪"
    elif any(k in positive for k in ["溪", "流", "小河", "河水"]):
        intent["scene"] = "stream"
        intent["scene_detail"] = "山间溪流"
    elif any(k in positive for k in ["雷"]):
        intent["scene"] = "thunder"
        intent["scene_detail"] = "远处的雨和闷雷"
    elif any(k in positive for k in ["鸟", "夜莺", "虫", "森林"]):
        intent["scene"] = "forest"
        intent["scene_detail"] = "森林虫鸣夜风"
    elif any(k in positive for k in ["风", "麦田"]):
        intent["scene"] = "wind"
        intent["scene_detail"] = "林间夜晚的风"
    # 心情
    if any(k in say for k in ["专注", "学习", "工作", "自习", "写东西", "看书"]):
        intent["mood"] = "focus"
    elif any(k in say for k in ["放松", "放空", "太累"]):
        intent["mood"] = "relax"
    # 暖 / 稳 / 禁忌
    if any(k in say for k in ["暖", "温柔", "柔和", "不刺耳"]):
        intent["warmth"] = "warm"
    if any(k in say for k in ["稳", "别突然", "不要炸", "别炸", "平稳"]):
        intent["dynamics"] = "steady"
    for word in ["雷声", "尖锐", "白噪音", "循环", "人声", "音乐", "噼啪", "鸟鸣"]:
        if word in say:
            intent["avoid"].append(word)
    return intent


def check(intent):
    # 简单校验：字段齐、场景在允许范围
    needed = ["scene", "scene_detail", "mood", "warmth", "dynamics",
              "avoid", "duration_minutes", "confidence"]
    for k in needed:
        if k not in intent:
            return False
    if intent["scene"] not in qwen_client.SCENE_ENUM:
        return False
    return True


def understand(say):
    # 返回 (intent, 来源)；异常只记录到服务端日志，绝不拼进前端可见字符串
    try:
        intent = qwen_client.understand(say)
        if check(intent):
            return intent, "Qwen3.8-Flash"
        print("[brain] understand 主力返回字段不合规", file=sys.stderr)
    except Exception as e:
        print("[brain] understand 主力失败:", str(e)[:120], file=sys.stderr)

    if LOCAL_URL:
        try:
            intent = from_local(say)
            if check(intent):
                return intent, "本地模型"
            print("[brain] understand 本地返回字段不合规", file=sys.stderr)
        except Exception as e:
            print("[brain] understand 本地失败:", str(e)[:120], file=sys.stderr)

    return from_rules(say), "规则匹配"


# ===== 多轮对话式 Agent 声景编排（支持思考解释、多轨参数、耳朵档案与增量微调） =====

TRACK_CATALOG = sound_catalog.build_track_catalog_dict()
ALLOWED_TRACK_SET = set(sound_catalog.ALLOWED_TRACK_FILES)

ASMR_KEYWORDS = (
    "采耳", "掏耳", "羽毛", "毛刷", "梳头", "梳发", "麦套", "防风罩",
    "扫麦", "轻触麦", "翻书", "翻页", "写字", "铅笔", "笔记", "轻敲",
    "敲击", "抓挠", "海绵", "糖纸", "揉捏", "搓手", "轻抚", "asmr", "ASMR",
)
UNSUPPORTED_SOURCE_KEYWORDS = ("人声", "耳语", "说话", "讲故事", "口腔音", "咖啡馆", "颂钵", "钵音")


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _extract_avoid_tracks(user_context=None):
    if not isinstance(user_context, dict):
        return set()
    raw = user_context.get("avoid_tracks") or []
    return {os.path.basename(str(x).strip()) for x in raw if str(x).strip()}


def _pick_non_avoided(candidates, avoid_tracks, fallback=None):
    for fn in candidates:
        if fn in ALLOWED_TRACK_SET and fn not in avoid_tracks:
            return fn
    if fallback and fallback in ALLOWED_TRACK_SET:
        return fallback
    for fn in candidates:
        if fn in ALLOWED_TRACK_SET:
            return fn
    return "母带_城市夜雨_CC0.mp3"


def _extract_collected_slots(full_text, user_context=None):
    avoid_flags = _extract_avoid_flags(full_text, user_context)
    avoid_tracks = _extract_avoid_tracks(user_context)
    positive = _clean_positive_text(full_text)

    state = ""
    if any(k in full_text for k in ("失眠", "睡不着", "入睡", "睡前", "睡眠")):
        state = "失眠入睡"
    elif any(k in full_text for k in ("凌晨", "易醒", "焦虑")):
        state = "凌晨安神"
    elif any(k in full_text for k in ("专注", "自习", "学习", "写东西", "工作", "看书")):
        state = "安静专注"
    elif any(k in full_text for k in ("累", "放空", "发呆", "放松")):
        state = "疲惫放空"

    scene = ""
    if any(k in positive for k in ("炉火", "壁炉", "篝火", "炭火", "营火")):
        scene = "壁炉暖火" if "壁炉" in positive else "营地篝火"
    elif any(k in positive for k in ("帐篷", "露营")) and any(k in positive for k in ("雨", "滴")):
        scene = "帐篷夜雨"
    elif "黑海" in positive:
        scene = "深沉黑海"
    elif any(k in positive for k in ("沙滩", "海边")):
        scene = "沙滩柔浪"
    elif any(k in positive for k in ("海", "潮汐", "浪")):
        scene = "远海潮汐"
    elif any(k in positive for k in ("溪", "流水", "小河", "河水")):
        scene = "山涧溪流"
    elif any(k in positive for k in ("乡村", "檐下", "外婆家", "院子")) and any(k in positive for k in ("雨", "滴")):
        scene = "檐下乡村小雨"
    elif any(k in positive for k in ("雨", "雷")):
        scene = "窗外雨夜"
    elif any(k in positive for k in ("采耳", "掏耳", "羽毛", "麦套", "扫麦")):
        scene = "近场采耳轻拂"
    elif any(k in positive for k in ("翻书", "翻页", "写字", "铅笔", "笔记")):
        scene = "深夜伴读"
    elif any(k in positive for k in ASMR_KEYWORDS):
        scene = "近场 ASMR"
    elif "鸟" in positive or "夜莺" in positive or "虫" in positive or "夏夜" in positive or "院" in positive:
        scene = "夏夜林院"
    elif any(k in positive for k in ("林风", "树林", "森林", "麦田", "风")):
        scene = "林间微风"

    texture = ""
    tex_parts = []
    if any(k in positive for k in ("暖", "毯子", "包裹", "低鸣", "沉稳", "壁炉", "厚重", "深沉")):
        tex_parts.append("暖厚包裹")
    if any(k in positive for k in ("柔", "绵密", "怕吵", "不吵", "轻一点", "不刺耳", "轻缓", "疏落", "缓流", "平稳", "安静", "沙沙")):
        tex_parts.append("轻柔绵密")
    if any(k in positive for k in ("树叶", "雨叶", "枝叶", "颗粒", "细碎", "噼啪", "帐篷", "露营", "大雨")):
        tex_parts.append("自然颗粒")
    if any(k in positive for k in ("清透", "清爽", "清亮", "干净", "真实", "母带", "山涧", "沙滩")):
        tex_parts.append("清透自然")
    if any(k in positive for k in ("酥麻", "轻拂", "扫麦", "采耳", "翻书", "写字", "梳发", "梳头", "毛刷", "纯近场", "稀疏偶发")):
        tex_parts.append("近场触发")
    if any(k in positive for k in ("配雨声", "配夜风", "夜莺", "虫鸣", "配柔和", "配温暖")) and not tex_parts:
        tex_parts.append("层次混搭")
    if tex_parts:
        texture = " · ".join(tex_parts[:2])

    rhythm_parts = []
    if any(k in positive for k in ("左", "右", "空间", "窗边")):
        rhythm_parts.append("左右空间感")
    if any(k in positive for k in ("偶", "点缀", "时起时歇", "稀疏")):
        rhythm_parts.append("偶发留白")
    if any(k in full_text for k in ("平稳", "稳一点", "求稳", "别突然", "不要炸", "别炸", "持续", "单层", "纯净")):
        rhythm_parts.append("平稳持续")
    if any(k in positive for k in ("夜风", "微风", "风", "虫", "鸟", "夜莺", "低鸣")) and scene not in ("林间微风", "夏夜林院"):
        rhythm_parts.append("多层陪伴")
    elif "雷" in positive and "雷" not in avoid_flags and "雷_档案" not in avoid_flags and "雷_记忆" not in avoid_flags:
        rhythm_parts.append("远雷偶发")
    spatial_rhythm = " · ".join(rhythm_parts[:2])

    avoid_labels = []
    if any(f in avoid_flags for f in ("雷", "雷_档案", "雷_记忆")):
        avoid_labels.append("避开雷声")
    if any(f in avoid_flags for f in ("颗粒_档案", "颗粒_记忆", "树叶")):
        avoid_labels.append("避开尖锐颗粒")
    if "噼啪" in avoid_flags:
        avoid_labels.append("避开噼啪声")
    if "风" in avoid_flags:
        avoid_labels.append("不要夜风")
    if "虫" in avoid_flags:
        avoid_labels.append("不要虫鸣")
    if "鸟" in avoid_flags:
        avoid_labels.append("不要鸟鸣")
    if "低鸣" in avoid_flags:
        avoid_labels.append("不要音乐垫")
    if any(k in full_text for k in ("别太吵", "不要太吵", "不吵", "太杂", "别杂")):
        avoid_labels.append("不杂不吵")
    if avoid_tracks:
        avoid_labels.append("避开历史否决音轨")
    avoid = "、".join(avoid_labels)

    return {
        "state": state,
        "scene": scene,
        "texture": texture,
        "spatial_rhythm": spatial_rhythm,
        "avoid": avoid,
    }


def _format_final_prompt(collected, tracks, fallback_say=""):
    parts = []
    if isinstance(collected, dict):
        for k in ("state", "scene", "texture", "spatial_rhythm", "avoid"):
            v = str(collected.get(k) or "").strip()
            if v:
                parts.append(v)
    if parts:
        return " · ".join(parts)
    if fallback_say:
        return str(fallback_say).strip()[:80]
    names = [TRACK_CATALOG[t["path"]]["name"] for t in (tracks or []) if t.get("path") in TRACK_CATALOG]
    return " + ".join(names) or "定制夜色声景"


def _sanitize_agent_design(raw, fallback_say="", force_compose=False, collected_fallback=None):
    if not isinstance(raw, dict):
        raise ValueError("Agent 输出非字典")

    raw_collected = raw.get("collected") if isinstance(raw.get("collected"), dict) else {}
    fb_col = collected_fallback if isinstance(collected_fallback, dict) else {}
    collected = {}
    for ck in ("state", "scene", "texture", "spatial_rhythm", "avoid"):
        val = str(raw_collected.get(ck) or fb_col.get(ck) or "").strip()[:40]
        collected[ck] = val

    action = "ask" if (raw.get("action") == "ask" and not force_compose) else "compose"
    question = str(raw.get("question") or "").strip()[:120]
    options = [str(x).strip()[:24] for x in (raw.get("options") or []) if str(x).strip()][:4]

    if action == "ask" and (not question or len(options) < 2):
        action = "compose"

    raw_intent = raw.get("intent") if isinstance(raw.get("intent"), dict) else {}
    scene = str(raw_intent.get("scene") or "rain")
    if scene not in qwen_client.SCENE_ENUM:
        scene = "rain"
    mood = str(raw_intent.get("mood") or "sleep")
    if mood not in ("sleep", "calm", "focus", "relax"):
        mood = "sleep"
    warmth = str(raw_intent.get("warmth") or "neutral")
    if warmth not in ("warm", "neutral", "cool"):
        warmth = "neutral"
    dynamics = str(raw_intent.get("dynamics") or "steady")
    if dynamics not in ("steady", "natural", "gentle_swell"):
        dynamics = "steady"
    avoid = [str(x).strip()[:20] for x in (raw_intent.get("avoid") or []) if str(x).strip()][:8]

    if action == "ask":
        title = str(raw.get("title") or raw_intent.get("scene_detail") or collected.get("scene") or "定制夜色").strip()[:24]
        reply = str(raw.get("reply") or "").strip()[:240] or "收到你的初步想法了，我还想确认一个细节。"
        reasoning = [str(x).strip()[:60] for x in (raw.get("reasoning") or []) if str(x).strip()][:4]
        if not reasoning:
            reasoning = ["先读取初始提示词里已明确的画面与需求", "确认最影响听感的缺失细节后再为你编排声轨"]
        return {
            "action": "ask",
            "question": question,
            "options": options,
            "collected": collected,
            "final_prompt": "",
            "title": title,
            "reply": reply,
            "intent": {
                "scene": scene,
                "scene_detail": str(raw_intent.get("scene_detail") or title)[:40],
                "mood": mood,
                "warmth": warmth,
                "dynamics": dynamics,
                "avoid": avoid,
            },
            "reasoning": reasoning,
            "tracks": [],
            "followups": [],
        }

    raw_tracks = raw.get("tracks")
    if not isinstance(raw_tracks, list):
        raw_tracks = []

    tracks = []
    seen_paths = set()
    for it in raw_tracks:
        if not isinstance(it, dict):
            continue
        p = os.path.basename(str(it.get("path") or "").strip())
        if p not in ALLOWED_TRACK_SET or p in seen_paths:
            continue
        seen_paths.add(p)
        meta = TRACK_CATALOG[p]
        try:
            w = float(it.get("weight", 0.5))
        except (TypeError, ValueError):
            w = 0.5
        try:
            pan = float(it.get("pan", meta["pan"]))
        except (TypeError, ValueError):
            pan = meta["pan"]
        mode = "intermittent" if it.get("mode") == "intermittent" else "loop"
        try:
            den = float(it.get("density", meta["density"]))
        except (TypeError, ValueError):
            den = meta["density"]
        note = str(it.get("role_note") or meta["role_note"]).strip()[:20] or meta["role_note"]
        tracks.append({
            "path": p,
            "weight": round(_clamp(w, 0.1, 1.0), 2),
            "pan": round(_clamp(pan, -0.9, 0.9), 2),
            "mode": mode,
            "density": round(_clamp(den, 0.15, 0.85), 2),
            "role_note": note,
        })
        if len(tracks) >= 4:
            break

    if not tracks:
        tracks = [{
            "path": "母带_城市夜雨_CC0.mp3",
            "weight": 0.72,
            "pan": 0.0,
            "mode": "loop",
            "density": 0.4,
            "role_note": "暖厚窗外主雨幕",
        }]

    title = str(raw.get("title") or raw_intent.get("scene_detail") or "").strip()[:24]
    if not title:
        title = TRACK_CATALOG[tracks[0]["path"]]["name"]

    final_prompt = str(raw.get("final_prompt") or "").strip()[:120]
    if not final_prompt:
        final_prompt = _format_final_prompt(collected, tracks, fallback_say)

    reply = str(raw.get("reply") or "").strip()[:240]
    if not reply:
        names = "、".join(TRACK_CATALOG[t["path"]]["name"] for t in tracks)
        reply = f"已为你编排「{title}」，由 {names} 搭配而成，听听看节奏与远近是否舒服。"

    reasoning = [str(x).strip()[:60] for x in (raw.get("reasoning") or []) if str(x).strip()][:4]
    if not reasoning:
        reasoning = [
            f"理解需求：提取场景「{title}」与氛围要求",
            "按底幕与层次分工挑选真实 CC0 原声并安排左右空间",
        ]

    followups = [str(x).strip()[:16] for x in (raw.get("followups") or []) if str(x).strip()][:3]
    if not followups:
        followups = ["再柔和一点", "加一点夜风", "换个更稳的"]

    return {
        "action": "compose",
        "question": "",
        "options": [],
        "collected": collected,
        "final_prompt": final_prompt,
        "title": title,
        "reply": reply,
        "intent": {
            "scene": scene,
            "scene_detail": str(raw_intent.get("scene_detail") or title)[:40],
            "mood": mood,
            "warmth": warmth,
            "dynamics": dynamics,
            "avoid": avoid,
        },
        "reasoning": reasoning,
        "tracks": tracks,
        "followups": followups,
    }


def _build_track(path, weight=None, pan=None, mode=None, density=None, role_note=None):
    meta = TRACK_CATALOG[path]
    return {
        "path": path,
        "weight": round(_clamp(0.72 if weight is None and meta["layer"] == "bed" else (0.36 if weight is None else weight), 0.1, 1.0), 2),
        "pan": round(_clamp(meta["pan"] if pan is None else pan, -0.9, 0.9), 2),
        "mode": mode if mode in ("loop", "intermittent") else meta["mode"],
        "density": round(_clamp(meta["density"] if density is None else density, 0.15, 0.85), 2),
        "role_note": role_note or meta["role_note"],
    }


def _extract_avoid_flags(say, user_context=None):
    avoid_set = set()
    neg_patterns = [
        ("雷", ["不要雷", "别打雷", "不要打雷", "没有雷", "别突然", "不要炸", "别炸", "稳一点", "怕惊"]),
        ("虫", ["不要虫", "别放虫", "没有虫"]),
        ("风", ["不要风", "别加风", "没有风"]),
        ("树叶", ["不要树叶", "别放树叶", "不要雨叶"]),
        ("低鸣", ["不要低鸣", "不要音乐", "不要垫"]),
        ("鸟", ["不要鸟", "别加鸟", "没有鸟"]),
        ("火", ["不要火", "不要炉火", "不要篝火"]),
        ("噼啪", ["不要噼啪", "别噼啪", "不要太吵", "别太吵"]),
        ("敲击", ["不要敲", "别敲"]),
    ]
    for flag, kws in neg_patterns:
        if any(k in say for k in kws):
            avoid_set.add(flag)

    if isinstance(user_context, dict):
        prof = user_context.get("ear_profile") or {}
        if isinstance(prof, dict):
            scores = prof.get("scores") or {}
            p_intent = prof.get("intent") or {}
            if p_intent.get("dynamics") == "steady" or (isinstance(scores.get("crisp"), (int, float)) and scores.get("crisp", 50) <= 40):
                avoid_set.add("雷_档案")
            if isinstance(scores.get("crisp"), (int, float)) and scores.get("crisp", 50) <= 35:
                avoid_set.add("颗粒_档案")
            if isinstance(scores.get("immersion"), (int, float)) and scores.get("immersion", 50) <= 40:
                avoid_set.add("ASMR_档案")

        for fb in (user_context.get("bad_feedbacks") or []):
            fb_s = str(fb)
            if "雷" in fb_s or "炸" in fb_s or "突然" in fb_s:
                avoid_set.add("雷_记忆")
            if "吵" in fb_s or "刺耳" in fb_s:
                avoid_set.add("颗粒_记忆")

    return avoid_set


def _clean_positive_text(say):
    positive = say
    for bad in [
        "千万别打雷", "不要雷声", "不要打雷", "别打雷", "不要雷", "没有雷",
        "不要虫鸣", "不要虫", "别放虫", "不要夜风", "不要风", "不要树叶",
        "不要低鸣", "不要音乐", "不要人声", "不要炸", "别炸", "别突然",
        "不要鸟鸣", "不要鸟", "别加鸟", "不要炉火", "不要篝火", "不要火",
        "不要噼啪", "别噼啪", "不要采耳", "不要敲击", "不要敲", "别敲",
        "不要羽毛", "不要翻书", "不要写字", "不要糖纸",
    ]:
        positive = positive.replace(bad, "")
    return positive


def _has_negated_target(say, key):
    return any(p + key in say or p + "一点" + key in say or p + "加" + key in say
               for p in ("不要", "别", "去掉", "删掉", "删除", "关掉", "拿掉", "没有"))


def _default_followups(tracks):
    paths = {t["path"] for t in tracks}
    out = []
    if "夜风.hq.mp3" not in paths:
        out.append("加一点夜风")
    else:
        out.append("夜风再轻一点")
    if "远雷.hq.mp3" in paths:
        out.append("把远雷改成偶尔响") if next((t for t in tracks if t["path"] == "远雷.hq.mp3" and t["mode"] == "loop"), None) else out.append("去掉远雷更稳")
    elif "虫鸣.hq.mp3" not in paths and ("海浪_远海.hq.mp3" in paths or "溪流.hq.mp3" in paths or "乡村小雨.hq.mp3" in paths):
        out.append("加一点夏夜虫鸣")
    elif "备选_大雨打树叶_CC0.mp3" not in paths:
        out.append("加一点雨打树叶")
    else:
        out.append("换成柔和一点的雨")
    if "雨中低鸣.hq.mp3" not in paths:
        out.append("声音更暖一点")
    else:
        out.append("去掉低鸣更清透")
    while len(out) < 3:
        out.append("整体再轻柔一点")
    return out[:3]


def _parse_pan_override(say):
    if "左" in say and "右" not in say:
        return -0.48
    if "右" in say and "左" not in say:
        return 0.48
    if "正中" in say or "中间" in say:
        return 0.0
    return None


# 叠加元素与关键词映射表（供规则编排与局部微调复用）
OVERLAY_SPECS = [
    (("树叶", "雨叶", "枝叶", "颗粒", "细碎"), "备选_大雨打树叶_CC0.mp3", 0.38, -0.32, "loop", 0.4, "树叶"),
    (("麦田",), "微风_麦田柔风_447810.hq.mp3", 0.36, 0.28, "loop", 0.4, "风"),
    (("风", "微风", "夜风"), "夜风.hq.mp3", 0.34, 0.36, "loop", 0.4, "风"),
    (("鸟", "夜莺"), "鸟鸣_夜莺鸣叫_853566.hq.mp3", 0.30, 0.42, "intermittent", 0.30, "鸟"),
    (("虫", "虫鸣"), "虫鸣.hq.mp3", 0.42, -0.44, "intermittent", 0.50, "虫"),
    (("采耳", "掏耳"), "ASMR_采耳_690078.hq.mp3", 0.46, -0.20, "loop", 0.4, "采耳"),
    (("麦套", "防风罩", "扫麦"), "ASMR_麦套轻扫抓挠_803595.hq.mp3", 0.48, 0.0, "loop", 0.4, "麦套"),
    (("轻触麦",), "ASMR_轻触麦克风_530347.hq.mp3", 0.34, 0.0, "loop", 0.4, "麦套"),
    (("羽毛",), "ASMR_羽毛轻拂_708086.hq.mp3", 0.40, 0.32, "intermittent", 0.38, "羽毛"),
    (("梳头",), "ASMR_轻柔梳头_825798.hq.mp3", 0.42, 0.18, "intermittent", 0.40, "毛刷"),
    (("毛刷", "梳发"), "ASMR_毛刷梳发_765369.hq.mp3", 0.42, -0.18, "intermittent", 0.40, "毛刷"),
    (("翻书", "翻页", "看书"), "ASMR_翻书单人_360781.hq.mp3", 0.38, -0.28, "intermittent", 0.45, "翻书"),
    (("写字", "铅笔", "笔记"), "ASMR_铅笔写字柔_336381.hq.mp3", 0.40, 0.25, "loop", 0.4, "写字"),
    (("海绵",), "ASMR_海绵抓挠_690084.hq.mp3", 0.38, 0.25, "loop", 0.4, "海绵"),
    (("轻敲", "敲击", "指尖"), "ASMR_指尖轻敲刮擦_866230.hq.mp3", 0.34, -0.32, "intermittent", 0.40, "敲击"),
    (("手部", "搓手"), "ASMR_手部轻搓抓挠_684746.hq.mp3", 0.32, 0.20, "intermittent", 0.32, "抓挠"),
    (("轻抚", "抓挠"), "ASMR_轻抚抓挠_695629.hq.mp3", 0.38, -0.22, "intermittent", 0.38, "抓挠"),
    (("糖纸", "揉捏"), "ASMR_糖纸揉捏_802609.hq.mp3", 0.28, 0.30, "intermittent", 0.32, "糖纸"),
]


def _apply_incremental_tweak(say, current_tracks, user_context=None):
    tracks = [_build_track(t["path"], t.get("weight"), t.get("pan"), t.get("mode"), t.get("density"), t.get("role_note"))
              for t in current_tracks if t.get("path") in ALLOWED_TRACK_SET]
    if not tracks:
        return None

    changes = []
    reasoning = []
    avoid_flags = _extract_avoid_flags(say, user_context)
    avoid_tracks = _extract_avoid_tracks(user_context)

    def find_idx(path):
        for i, t in enumerate(tracks):
            if t["path"] == path:
                return i
        return -1

    def remove_path(path, label=None):
        idx = find_idx(path)
        if idx != -1:
            tracks.pop(idx)
            changes.append("移除了" + (label or TRACK_CATALOG[path]["name"]))

    # 1. 明确删除元素（覆盖自然元素与新增的鸟鸣/炉火/近场 ASMR）
    remove_rules = [
        ("雷", ("远雷.hq.mp3",)),
        ("风", ("夜风.hq.mp3", "微风_麦田柔风_447810.hq.mp3", "林风_树林波浪风_637989.hq.mp3", "林风_Akacie_73708.hq.mp3", "微风_小镇傍晚风_321904.hq.mp3")),
        ("虫", ("虫鸣.hq.mp3",)),
        ("鸟", ("鸟鸣_夜莺鸣叫_853566.hq.mp3",)),
        ("夜莺", ("鸟鸣_夜莺鸣叫_853566.hq.mp3",)),
        ("树叶", ("备选_大雨打树叶_CC0.mp3",)),
        ("雨叶", ("备选_大雨打树叶_CC0.mp3",)),
        ("火", ("炉火_壁炉低燃_836535.hq.mp3", "炉火_夜营氛围_766127.hq.mp3", "炉火_营地篝火_62487.hq.mp3")),
        ("采耳", ("ASMR_采耳_690078.hq.mp3",)),
        ("羽毛", ("ASMR_羽毛轻拂_708086.hq.mp3",)),
        ("毛刷", ("ASMR_毛刷梳发_765369.hq.mp3", "ASMR_轻柔梳头_825798.hq.mp3")),
        ("梳头", ("ASMR_轻柔梳头_825798.hq.mp3", "ASMR_毛刷梳发_765369.hq.mp3")),
        ("翻书", ("ASMR_翻书单人_360781.hq.mp3", "ASMR_翻书多人_575764.hq.mp3")),
        ("写字", ("ASMR_铅笔写字柔_336381.hq.mp3", "ASMR_铅笔写字轻快_376706.hq.mp3")),
        ("敲", ("ASMR_指尖轻敲刮擦_866230.hq.mp3", "ASMR_木件桌游轻敲_569788.hq.mp3")),
        ("糖纸", ("ASMR_糖纸揉捏_802609.hq.mp3",)),
        ("抓挠", ("ASMR_手部轻搓抓挠_684746.hq.mp3", "ASMR_轻抚抓挠_695629.hq.mp3", "ASMR_海绵抓挠_690084.hq.mp3")),
        ("麦套", ("ASMR_麦套轻扫抓挠_803595.hq.mp3",)),
    ]
    for kw, paths in remove_rules:
        if _has_negated_target(say, kw) or (kw == "雷" and ("太突然" in say or "别炸" in say)):
            for p in paths:
                remove_path(p)
    if _has_negated_target(say, "低鸣") or _has_negated_target(say, "音乐") or "雨声小" in say or "雨太小" in say:
        remove_path("雨中低鸣.hq.mp3", "暖夜低鸣")

    # 2. 经典整体反馈（跨全部 41 段多场景生效）
    if any(k in say for k in ("吵", "刺耳", "太尖")):
        for harsh in ("远雷.hq.mp3", "备选_大雨打树叶_CC0.mp3", "ASMR_木件桌游轻敲_569788.hq.mp3", "ASMR_糖纸揉捏_802609.hq.mp3"):
            remove_path(harsh)
        swapped = False
        used_paths = {t["path"] for t in tracks}
        for i, t in enumerate(tracks):
            meta = TRACK_CATALOG[t["path"]]
            if meta["layer"] == "bed" or i == 0:
                alts = sound_catalog.find_alternatives(
                    t["path"],
                    prefer_softer=True,
                    exclude_filenames=avoid_tracks | used_paths,
                    avoid_tags=["吵", "尖锐", "削波", "噼啪"],
                )
                if alts and meta["intensity"] != "soft":
                    new_fn = alts[0]["filename"]
                    tracks[i] = _build_track(new_fn, min(t["weight"], 0.65), t["pan"], "loop", 0.4)
                    used_paths.add(new_fn)
                    swapped = True
                    changes.append(f"将「{meta['name']}」换成更轻柔的「{alts[0]['name']}」")
                    continue
            t["weight"] = round(max(0.18, t["weight"] * 0.72), 2)
        if not swapped:
            changes.append("整体压轻了高频与响度")
        reasoning.append("识别到“太吵/刺耳”：撤掉瞬态冲击并切换更柔和稳重的版本")

    if any(k in say for k in ("杂", "乱", "好几层")):
        tracks.sort(key=lambda x: x["weight"], reverse=True)
        main = tracks[0]
        main["weight"] = round(max(0.70, main["weight"]), 2)
        main["pan"] = 0.0
        tracks = [main]
        changes.append("只保留主声景「" + TRACK_CATALOG[main["path"]]["name"] + "」")
        reasoning.append("识别到“声音杂”：收束多层叠加为单轨纯净声景")

    if any(k in say for k in ("假", "电子", "不真实")):
        tracks = [_build_track("母带_城市夜雨_CC0.mp3", 0.78, 0.0, "loop", 0.4, "真实城市夜雨母带")]
        changes.append("切回纯净「城市夜雨」母带单段")
        reasoning.append("识别到“不真实”：回归最稳妥的真实录音母带")

    if any(k in say for k in ("闷", "没细节", "听不清")):
        main_meta = TRACK_CATALOG[tracks[0]["path"]]
        if main_meta["scene"] == "rain" and find_idx("备选_大雨打树叶_CC0.mp3") == -1:
            tracks.append(_build_track("备选_大雨打树叶_CC0.mp3", 0.35, -0.30, "loop", 0.4, "补充细碎雨滴细节"))
            changes.append("加入左前「雨打树叶」补回颗粒细节")
        else:
            used_paths = {t["path"] for t in tracks}
            alts = sound_catalog.find_alternatives(
                tracks[0]["path"],
                prefer_more_detail=True,
                exclude_filenames=avoid_tracks | used_paths,
            )
            if alts:
                tracks[0] = _build_track(alts[0]["filename"], tracks[0]["weight"], tracks[0]["pan"], tracks[0]["mode"], tracks[0]["density"])
                changes.append(f"将「{main_meta['name']}」换成细节更丰富的「{alts[0]['name']}」")
            else:
                for t in tracks:
                    if TRACK_CATALOG[t["path"]]["layer"] != "bed":
                        t["weight"] = round(min(0.85, t["weight"] * 1.25), 2)
                changes.append("适度提升了细节层清晰度")
        reasoning.append("识别到“太闷/没细节”：增加清晰纹理细节")

    if any(k in say for k in ("更稳", "稳一点", "别突然")):
        remove_path("远雷.hq.mp3", "远处闷雷")
        if not changes:
            for t in tracks:
                if TRACK_CATALOG[t["path"]]["layer"] == "bed":
                    t["weight"] = round(max(0.65, t["weight"]), 2)
            changes.append("收稳底幕并避开突兀响动")

    if any(k in say for k in ("清透", "清爽")) and find_idx("雨中低鸣.hq.mp3") != -1:
        remove_path("雨中低鸣.hq.mp3", "暖夜低鸣")

    if any(k in say for k in ("更暖", "暖一点", "暖些")) and not _has_negated_target(say, "低鸣"):
        if find_idx("雨中低鸣.hq.mp3") == -1 and len(tracks) < 4:
            tracks.append(_build_track("雨中低鸣.hq.mp3", 0.28, 0.0, "loop"))
            changes.append("加入了「暖夜低鸣」增加暖意包裹感")

    # 2.5 底幕替换（保留已有配角纹理与点缀）
    if any(k in say for k in ("换", "改")) and not any(k in say for k in ("偶发", "偶尔", "持续")):
        bed_swap_rules = [
            (("帐篷", "露营"), "帐篷雨_小帐篷大雨_592996.hq.mp3"),
            (("柔和", "轻雨", "细雨"), "柔和雨.hq.mp3"),
            (("乡村", "小雨"), "乡村小雨.hq.mp3"),
            (("城市",), "母带_城市夜雨_CC0.mp3"),
            (("夜营", "余烬"), "炉火_夜营氛围_766127.hq.mp3"),
            (("篝火",), "炉火_营地篝火_62487.hq.mp3"),
            (("壁炉", "炉火", "火"), "炉火_壁炉低燃_836535.hq.mp3"),
            (("黑海",), "海浪_黑海.hq.mp3"),
            (("沙滩",), "海浪_沙滩柔浪_325197.hq.mp3"),
            (("湖", "柔浪"), "海浪_湖海柔浪_451532.hq.mp3"),
            (("海", "浪"), "海浪_远海.hq.mp3"),
            (("河水", "柔和河"), "溪流_柔和河水_707576.hq.mp3"),
            (("小溪",), "溪流_小溪循环_767320.hq.mp3"),
            (("野外溪",), "溪流_野外溪水_180732.hq.mp3"),
            (("溪",), "溪流.hq.mp3"),
            (("林风", "树林", "森林"), "林风_树林波浪风_637989.hq.mp3"),
            (("傍晚", "微风"), "微风_小镇傍晚风_321904.hq.mp3"),
        ]
        new_bed = None
        for kws, cand_fn in bed_swap_rules:
            if any(k in say for k in kws):
                new_bed = cand_fn
                break
        if new_bed and find_idx(new_bed) == -1:
            replaced = False
            for i, t in enumerate(tracks):
                if TRACK_CATALOG[t["path"]]["layer"] == "bed":
                    tracks[i] = _build_track(new_bed, t["weight"], t["pan"], "loop", 0.4)
                    replaced = True
                    break
            if not replaced:
                tracks.insert(0, _build_track(new_bed, 0.72, 0.0, "loop", 0.4))
            changes.append(f"将底幕换成「{TRACK_CATALOG[new_bed]['name']}」")

    # 3. 明确增加或切换纹理/点缀
    pan_override = _parse_pan_override(say)
    want_intermittent = any(k in say for k in ("偶尔", "偶发", "稀疏", "时起时歇", "少响"))
    want_loop = any(k in say for k in ("持续", "一直", "不断", "连续"))

    add_cues = ("加", "来点", "添", "配", "放", "多点", "补", "要")
    if any(c in say for c in add_cues):
        for kws, path, w, default_pan, default_mode, den, flag in OVERLAY_SPECS:
            if len(tracks) >= 4:
                break
            if any(k in say for k in kws) and not _has_negated_target(say, flag) and flag not in avoid_flags:
                if find_idx(path) == -1 and path not in avoid_tracks:
                    p = pan_override if pan_override is not None else default_pan
                    mode = "intermittent" if want_intermittent else ("loop" if want_loop else default_mode)
                    tracks.append(_build_track(path, w, p, mode, den))
                    changes.append(f"加入了「{TRACK_CATALOG[path]['name']}」")
        if "雷" in say and not _has_negated_target(say, "雷") and "雷" not in avoid_flags:
            if find_idx("远雷.hq.mp3") == -1 and len(tracks) < 4:
                p = pan_override if pan_override is not None else 0.48
                tracks.append(_build_track("远雷.hq.mp3", 0.36, p, "loop" if want_loop else "intermittent", 0.28))
                changes.append("在右侧天边加入了「天际远雷」（偶发）")
        if ("低鸣" in say or "暖" in say or "厚" in say) and not _has_negated_target(say, "低鸣"):
            if find_idx("雨中低鸣.hq.mp3") == -1 and len(tracks) < 4:
                tracks.append(_build_track("雨中低鸣.hq.mp3", 0.28, 0.0, "loop"))
                changes.append("加入了「暖夜低鸣」托住温度")

    # 4. 针对已有轨道的节奏 / 方位 / 轻重微调
    targeted = []
    for t in tracks:
        meta = TRACK_CATALOG[t["path"]]
        if any(tag in say for tag in meta["tags"]) or meta["name"] in say:
            targeted.append(t["path"])

    if want_intermittent:
        chosen = targeted or [t["path"] for t in tracks if TRACK_CATALOG[t["path"]]["layer"] != "bed"]
        for p in chosen:
            idx = find_idx(p)
            if idx != -1:
                tracks[idx]["mode"] = "intermittent"
                if "稀疏" in say or "少" in say:
                    tracks[idx]["density"] = 0.22
                elif "频繁" in say or "多" in say:
                    tracks[idx]["density"] = 0.78
                changes.append(f"将「{TRACK_CATALOG[p]['name']}」切换为偶发呼吸节奏")
    elif want_loop:
        chosen = targeted or [t["path"] for t in tracks if t["mode"] == "intermittent"]
        for p in chosen:
            idx = find_idx(p)
            if idx != -1:
                tracks[idx]["mode"] = "loop"
                changes.append(f"将「{TRACK_CATALOG[p]['name']}」切换为持续陪伴")

    if pan_override is not None:
        chosen = targeted or [t["path"] for t in tracks if TRACK_CATALOG[t["path"]]["layer"] != "bed"] or [tracks[0]["path"]]
        for p in chosen:
            idx = find_idx(p)
            if idx != -1:
                tracks[idx]["pan"] = pan_override
                side_txt = "左窗" if pan_override < -0.1 else ("右侧" if pan_override > 0.1 else "正中")
                changes.append(f"将「{TRACK_CATALOG[p]['name']}」移到{side_txt}")

    softer = any(k in say for k in ("小点", "小一点", "小声", "轻点", "轻一点", "轻柔", "柔和一点", "少一点", "弱一点"))
    louder = any(k in say for k in ("大点", "大一点", "大声", "重点", "重一点", "多一点", "响一点", "明显一点"))
    if softer or louder:
        chosen = targeted or [t["path"] for t in tracks]
        for p in chosen:
            idx = find_idx(p)
            if idx != -1:
                cur_w = tracks[idx]["weight"]
                tracks[idx]["weight"] = round(_clamp(cur_w * (0.68 if softer else 1.32), 0.12, 1.0), 2)
        if not changes:
            changes.append("调轻了目标声轨音量占比" if softer else "增强了目标声轨存在感")

    if not tracks:
        tracks = [_build_track("柔和雨.hq.mp3", 0.65, 0.0, "loop")]
        changes.append("为你保留柔和雨幕打底")

    if not changes:
        return None

    if not reasoning:
        reasoning = [
            "保留你原先喜欢的主体声景，只按要求做局部微调",
            "调整内容：" + "、".join(changes[:2]),
        ]
    title = TRACK_CATALOG[tracks[0]["path"]]["name"]
    if len(tracks) > 1:
        title = title + "·" + TRACK_CATALOG[tracks[1]["path"]]["name"]
    reply = "好的，已经" + "，".join(changes) + "。现在这段的层次会更贴合你。"

    collected_tweak = _extract_collected_slots(say, user_context)
    lead_scene = TRACK_CATALOG[tracks[0]["path"]]["scene"]
    if lead_scene not in qwen_client.SCENE_ENUM:
        lead_scene = "mix"
    return _sanitize_agent_design({
        "action": "compose",
        "title": title[:14],
        "reply": reply,
        "collected": collected_tweak,
        "intent": {
            "scene": lead_scene,
            "scene_detail": title,
            "mood": "sleep",
            "warmth": "warm" if "暖" in say or find_idx("雨中低鸣.hq.mp3") != -1 else "neutral",
            "dynamics": "steady" if find_idx("远雷.hq.mp3") == -1 else "natural",
            "avoid": list(avoid_flags),
        },
        "reasoning": reasoning,
        "tracks": tracks,
        "followups": _default_followups(tracks),
    }, say, force_compose=True, collected_fallback=collected_tweak)


def _pan_for_clause(text, keywords, default_pan):
    # 按句段局部分析左右方位，避免“左虫鸣；右夜风”互相串扰
    for clause in text.replace("，", "；").replace("。", "；").split("；"):
        if any(k in clause for k in keywords):
            p = _parse_pan_override(clause)
            if p is not None:
                return p
    return default_pan


def _build_ask_turn(collected, merged_text, user_context=None, history=None):
    avoid_flags = _extract_avoid_flags(merged_text, user_context)
    scene_txt = collected.get("scene") or ""
    tex_txt = collected.get("texture") or ""
    rhythm_txt = collected.get("spatial_rhythm") or ""
    avoid_txt = collected.get("avoid") or ""

    asked_Assist = " ".join(
        str(h.get("content") or "")
        for h in (history or [])
        if isinstance(h, dict) and h.get("role") == "assistant"
    )
    already_asked_tex = any(k in asked_Assist for k in ("什么质感", "哪种海浪", "哪种氛围", "哪种燃感", "配点自然底", "哪种感觉"))
    already_asked_rhythm = "陪伴或点缀" in asked_Assist

    if not scene_txt:
        is_racing = any(k in merged_text for k in ("焦虑", "胡思乱想", "停不下来", "压力", "心烦", "思绪", "想太多", "烦躁", "加班"))
        return _sanitize_agent_design({
            "action": "ask",
            "title": "待选夜色",
            "reply": "思绪有点满时，轻情境比纯白噪音更容易帮脑子放空。你更想听哪一类？" if is_racing else "先定一个主画面，纯自然或无人声轻情境都可以。",
            "question": "今晚更偏爱纯自然，还是加一点无人声轻情境？",
            "options": ["窗外夜雨", "雨夜书房翻书", "轻柔采耳梳发", "远处海浪"],
            "collected": collected,
            "reasoning": [
                "已了解你的当前睡前状态",
                "同步提供纯自然白噪音与无人声轻情境选项，确认主方向",
            ],
            "tracks": [],
        }, merged_text, force_compose=False, collected_fallback=collected)

    if not tex_txt and not already_asked_tex:
        if "海" in scene_txt or "浪" in scene_txt:
            q = "偏爱哪种海浪听感？"
            opts = ["远海柔和推浪", "深沉厚重黑海", "长段平稳湖浪", "清透沙滩浪"]
        elif "溪" in scene_txt:
            q = "溪流想要哪种氛围？"
            opts = ["柔和缓流河水", "清亮山涧小溪", "加点夜莺鸟鸣", "溪水配夜风"]
        elif "火" in scene_txt:
            q = "炉火想要哪种燃感？"
            opts = ["平稳壁炉低燃", "极柔和夜营微火", "带木柴噼啪篝火", "炉火配雨声"]
        elif "ASMR" in scene_txt or "采耳" in scene_txt or "伴读" in scene_txt:
            q = "近场 ASMR 想配点自然底吗？"
            opts = ["纯近场触发就好", "配一点柔和夜雨", "配温暖壁炉低燃", "稀疏偶发轻一点"]
        elif "夏夜" in scene_txt or "微风" in scene_txt:
            q = "林院想偏哪种感觉？"
            opts = ["安静林间空气", "林风配稀疏夜莺", "加点夏夜虫鸣", "麦田沙沙微风"]
        else:
            q = "这场雨想要什么质感？"
            opts = ["绵密暖厚像毯子", "露营帐篷大雨", "轻缓檐下小雨", "沉稳城市夜雨"]
        return _sanitize_agent_design({
            "action": "ask",
            "title": scene_txt,
            "reply": f"已定好「{scene_txt}」。",
            "question": q,
            "options": opts,
            "collected": collected,
            "reasoning": [
                f"已锁定主场景「{scene_txt}」",
                "确认声音质感，避免过吵或发闷",
            ],
            "tracks": [],
        }, merged_text, force_compose=False, collected_fallback=collected)

    if not rhythm_txt and not avoid_txt and not already_asked_rhythm:
        q = "还要加点陪伴或点缀吗？"
        if any(f in avoid_flags for f in ("雷", "雷_档案", "雷_记忆")):
            opts = ["纯净单层就够了", "右侧加点林间夜风", "偶尔一点羽毛轻拂", "左侧偶尔几声虫鸣"]
        else:
            opts = ["纯净平稳，别打雷", "右侧加点林间夜风", "天边偶尔一声闷雷", "加点稀疏夜莺鸟鸣"]
        return _sanitize_agent_design({
            "action": "ask",
            "title": scene_txt,
            "reply": f"质感「{tex_txt}」已确认。",
            "question": q,
            "options": opts,
            "collected": collected,
            "reasoning": [
                f"已定「{scene_txt} · {tex_txt}」",
                "确认空间陪伴与禁忌后即刻出稿",
            ],
            "tracks": [],
        }, merged_text, force_compose=False, collected_fallback=collected)

    return None


def design_soundscape_rules(
    say,
    current_tracks=None,
    user_context=None,
    qa_round=0,
    force_compose=False,
    initial_prompt="",
    history=None,
):
    # 多轮问答共创 + 规则兜底：先追问确认缺失维度，再综合全部上下文出稿或做增量微调
    if current_tracks:
        has_new_scene_switch = any(k in say for k in ("改听", "重新配"))
        if not has_new_scene_switch:
            tweaked = _apply_incremental_tweak(say, current_tracks, user_context)
            if tweaked is not None:
                return tweaked

    user_pieces = []
    hist_users = [
        str(h.get("content") or "")
        for h in (history or [])
        if isinstance(h, dict) and h.get("role") == "user"
    ]
    for piece in [initial_prompt] + hist_users + [say]:
        p = str(piece or "").strip()
        if p and p not in user_pieces:
            user_pieces.append(p)
    merged_text = "；".join(user_pieces) if user_pieces else str(say or "")

    skip_qa = bool(force_compose) or int(qa_round or 0) >= 2 or any(
        k in say for k in ("直接生成", "直接配", "跳过", "按目前信息", "不用再问")
    )

    # 越界声源诚实边界检测（如人声耳语/讲故事/口腔音等库里完全未收录的声源）
    positive_merged = _clean_positive_text(merged_text)
    has_unsupported = any(k in positive_merged for k in UNSUPPORTED_SOURCE_KEYWORDS)
    has_supported_scene = any(
        k in positive_merged
        for k in ("雨", "海", "浪", "溪", "火", "炉", "风", "虫", "鸟", "夜莺") + ASMR_KEYWORDS
    )
    if has_unsupported and not has_supported_scene:
        avoid_tracks = _extract_avoid_tracks(user_context)
        t1 = _pick_non_avoided(["ASMR_采耳_690078.hq.mp3", "ASMR_麦套轻扫抓挠_803595.hq.mp3"], avoid_tracks)
        t2 = _pick_non_avoided(["ASMR_羽毛轻拂_708086.hq.mp3", "柔和雨.hq.mp3"], avoid_tracks)
        tracks = [_build_track(t1, 0.56, 0.0, "loop")]
        if t2 != t1:
            tracks.append(_build_track(t2, 0.36, 0.25, "intermittent", 0.35))
        return _sanitize_agent_design({
            "action": "compose",
            "title": "轻柔近场替代",
            "reply": "目前素材库暂未收录人声耳语或讲故事等声源，先为你搭配最轻柔的「轻柔采耳 + 羽毛轻拂」近场组合试试。",
            "collected": _extract_collected_slots(merged_text, user_context),
            "final_prompt": "暂未收录人声耳语，推荐近场轻柔采耳与羽毛轻拂替代",
            "intent": {
                "scene": "asmr",
                "scene_detail": "近场轻柔采耳与羽毛轻拂",
                "mood": "sleep",
                "warmth": "warm",
                "dynamics": "steady",
                "avoid": [],
            },
            "reasoning": [
                "诚实边界：库内暂无真人耳语/口腔/讲故事录音",
                "改用已验收的近场采耳与羽毛轻拂替代",
            ],
            "tracks": tracks,
            "followups": ["换成城市夜雨", "加一点柔和雨", "声音更轻柔"],
        }, merged_text, force_compose=True)

    collected = _extract_collected_slots(merged_text, user_context)
    if not current_tracks and not skip_qa:
        ask_turn = _build_ask_turn(collected, merged_text, user_context, history=history)
        if ask_turn is not None:
            return ask_turn

    # 出稿时用合并后的全部上下文，避免第2~3轮短回答丢失初始主场景
    full_say = merged_text
    avoid_flags = _extract_avoid_flags(full_say, user_context)
    avoid_tracks = _extract_avoid_tracks(user_context)
    positive = _clean_positive_text(full_say)

    tracks = []
    reasoning = []
    scene = "rain"
    mood = "sleep"
    warmth = "neutral"
    dynamics = "natural"

    if any(k in full_say for k in ("专注", "自习", "学习", "写东西", "工作", "看书", "笔记")):
        mood = "focus"
    elif any(k in full_say for k in ("放空", "发呆", "放松", "太累", "累")):
        mood = "relax"

    if any(k in full_say for k in ("暖", "温柔", "柔和", "不刺耳", "毯子", "壁炉")):
        warmth = "warm"
    elif any(k in full_say for k in ("清透", "清爽", "凉")):
        warmth = "cool"

    if any(k in full_say for k in ("稳", "别突然", "不要炸", "别炸", "平稳", "别太吵", "不要太吵", "浅睡", "易醒", "打呼", "车流", "隔音", "遮蔽")) or "雷" in avoid_flags or "雷_档案" in avoid_flags:
        dynamics = "steady"

    is_masking_sleep = any(k in full_say for k in ("浅睡", "易醒", "打呼", "呼噜", "车流", "隔音", "遮蔽", "外面吵", "窗外吵", "太吵"))
    is_racing_mind = any(k in full_say for k in ("焦虑", "胡思乱想", "停不下来", "压力", "心烦", "思绪", "想太多", "烦躁", "加班"))
    wants_pure_only = any(k in full_say for k in ("纯自然", "纯白噪音", "单轨", "单层", "只要雨", "只要海", "不要ASMR", "不要asmr"))
    ear_immersion = 50
    if isinstance(user_context, dict) and isinstance(user_context.get("ear_profile"), dict):
        sc = user_context["ear_profile"].get("scores") or {}
        if isinstance(sc.get("immersion"), (int, float)):
            ear_immersion = sc["immersion"]

    # 1. 选主底幕（覆盖自然场景 18 段 + 纯 ASMR 起手场景）
    bed_path = None
    if any(k in positive for k in ("炉火", "壁炉", "篝火", "炭火", "营火")) and "火" not in avoid_flags:
        if any(k in positive for k in ("夜营", "微火", "余烬", "别太吵", "不要太吵", "怕吵", "不吵", "极柔")):
            bed_path = _pick_non_avoided(["炉火_夜营氛围_766127.hq.mp3", "炉火_壁炉低燃_836535.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("篝火", "噼啪", "木柴")) and "噼啪" not in avoid_flags:
            bed_path = _pick_non_avoided(["炉火_营地篝火_62487.hq.mp3", "炉火_壁炉低燃_836535.hq.mp3"], avoid_tracks)
        else:
            bed_path = _pick_non_avoided(["炉火_壁炉低燃_836535.hq.mp3", "炉火_夜营氛围_766127.hq.mp3"], avoid_tracks)
        scene = "fire"
    elif any(k in positive for k in ("帐篷", "露营")) and any(k in positive for k in ("雨", "滴")):
        bed_path = _pick_non_avoided(["帐篷雨_小帐篷大雨_592996.hq.mp3", "母带_城市夜雨_CC0.mp3"], avoid_tracks)
        scene = "rain"
    elif "黑海" in positive:
        bed_path = _pick_non_avoided(["海浪_黑海.hq.mp3", "海浪_远海.hq.mp3"], avoid_tracks)
        scene = "ocean"
    elif any(k in positive for k in ("沙滩", "海边")):
        bed_path = _pick_non_avoided(["海浪_沙滩柔浪_325197.hq.mp3", "海浪_湖海柔浪_451532.hq.mp3"], avoid_tracks)
        scene = "ocean"
    elif any(k in positive for k in ("湖浪", "柔浪")):
        bed_path = _pick_non_avoided(["海浪_湖海柔浪_451532.hq.mp3", "海浪_远海.hq.mp3"], avoid_tracks)
        scene = "ocean"
    elif any(k in positive for k in ("海", "潮汐", "浪")):
        if dynamics == "steady" or warmth == "warm":
            bed_path = _pick_non_avoided(["海浪_湖海柔浪_451532.hq.mp3", "海浪_远海.hq.mp3"], avoid_tracks)
        else:
            bed_path = _pick_non_avoided(["海浪_远海.hq.mp3", "海浪_湖海柔浪_451532.hq.mp3"], avoid_tracks)
        scene = "ocean"
    elif any(k in positive for k in ("溪", "流水", "小河", "河水")):
        if any(k in positive for k in ("河水", "长", "柔和", "平稳", "不吵", "暖")):
            bed_path = _pick_non_avoided(["溪流_柔和河水_707576.hq.mp3", "溪流_小溪循环_767320.hq.mp3", "溪流.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("小溪", "安静", "轻缓")):
            bed_path = _pick_non_avoided(["溪流_小溪循环_767320.hq.mp3", "溪流_柔和河水_707576.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("野外", "水花")):
            bed_path = _pick_non_avoided(["溪流_野外溪水_180732.hq.mp3", "溪流_柔和河水_707576.hq.mp3"], avoid_tracks)
        else:
            bed_path = _pick_non_avoided(["溪流.hq.mp3", "溪流_柔和河水_707576.hq.mp3"], avoid_tracks)
        scene = "stream"
    elif any(k in positive for k in ("乡村", "檐下", "外婆家", "院子")) and any(k in positive for k in ("雨", "滴")):
        bed_path = _pick_non_avoided(["乡村小雨.hq.mp3", "柔和雨.hq.mp3"], avoid_tracks)
        scene = "rain"
    elif any(k in positive for k in ("柔和雨", "轻雨", "细雨", "怕吵", "不吵", "轻柔", "柔一点", "绵密柔和")) and "雨" in positive:
        bed_path = _pick_non_avoided(["柔和雨.hq.mp3", "乡村小雨.hq.mp3", "母带_城市夜雨_CC0.mp3"], avoid_tracks)
        scene = "rain"
    elif any(k in positive for k in ("雨", "雷")):
        if "颗粒_档案" in avoid_flags or "颗粒_记忆" in avoid_flags or any(k in positive for k in ("柔和", "怕吵", "别太吵")):
            bed_path = _pick_non_avoided(["柔和雨.hq.mp3", "母带_城市夜雨_CC0.mp3"], avoid_tracks)
        else:
            bed_path = _pick_non_avoided(["母带_城市夜雨_CC0.mp3", "柔和雨.hq.mp3"], avoid_tracks)
        scene = "rain"
    elif any(k in positive for k in ASMR_KEYWORDS):
        # 纯近场 ASMR 场景（未同时要求自然雨/海/溪/火铺底）
        scene = "asmr"
        if any(k in positive for k in ("麦套", "防风罩", "扫麦")):
            bed_path = _pick_non_avoided(["ASMR_麦套轻扫抓挠_803595.hq.mp3", "ASMR_采耳_690078.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("采耳", "掏耳")):
            bed_path = _pick_non_avoided(["ASMR_采耳_690078.hq.mp3", "ASMR_麦套轻扫抓挠_803595.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("梳头", "毛刷", "梳发")):
            bed_path = _pick_non_avoided(["ASMR_轻柔梳头_825798.hq.mp3", "ASMR_毛刷梳发_765369.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("翻书", "翻页", "看书")):
            bed_path = _pick_non_avoided(["ASMR_翻书多人_575764.hq.mp3", "ASMR_翻书单人_360781.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("写字", "铅笔", "笔记")):
            bed_path = _pick_non_avoided(["ASMR_铅笔写字柔_336381.hq.mp3", "ASMR_铅笔写字轻快_376706.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("羽毛",)):
            bed_path = _pick_non_avoided(["ASMR_羽毛轻拂_708086.hq.mp3", "ASMR_采耳_690078.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("海绵",)):
            bed_path = _pick_non_avoided(["ASMR_海绵抓挠_690084.hq.mp3", "ASMR_麦套轻扫抓挠_803595.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("轻敲", "敲击", "指尖")):
            bed_path = _pick_non_avoided(["ASMR_指尖轻敲刮擦_866230.hq.mp3", "ASMR_木件桌游轻敲_569788.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("糖纸", "揉捏")):
            bed_path = _pick_non_avoided(["ASMR_糖纸揉捏_802609.hq.mp3", "ASMR_海绵抓挠_690084.hq.mp3"], avoid_tracks)
        elif any(k in positive for k in ("轻抚", "抓挠", "搓手")):
            bed_path = _pick_non_avoided(["ASMR_轻抚抓挠_695629.hq.mp3", "ASMR_手部轻搓抓挠_684746.hq.mp3"], avoid_tracks)
        else:
            bed_path = _pick_non_avoided(["ASMR_麦套轻扫抓挠_803595.hq.mp3", "ASMR_采耳_690078.hq.mp3"], avoid_tracks)
    elif any(k in positive for k in ("林风", "树林", "森林", "松涛")):
        if any(k in positive for k in ("静", "轻", "柔", "不吵")):
            bed_path = _pick_non_avoided(["林风_Akacie_73708.hq.mp3", "林风_树林波浪风_637989.hq.mp3"], avoid_tracks)
        else:
            bed_path = _pick_non_avoided(["林风_树林波浪风_637989.hq.mp3", "林风_Akacie_73708.hq.mp3"], avoid_tracks)
        scene = "wind"
    elif any(k in positive for k in ("麦田", "傍晚", "山谷", "微风")):
        bed_path = _pick_non_avoided(["微风_小镇傍晚风_321904.hq.mp3", "微风_麦田柔风_447810.hq.mp3"], avoid_tracks)
        scene = "wind"
    elif any(k in positive for k in ("鸟", "夜莺", "虫", "风")):
        bed_path = _pick_non_avoided(["林风_Akacie_73708.hq.mp3", "夜风.hq.mp3"], avoid_tracks)
        scene = "forest" if ("虫" in positive or "鸟" in positive or "夜莺" in positive) else "wind"
    else:
        bed_path = _pick_non_avoided(["母带_城市夜雨_CC0.mp3", "柔和雨.hq.mp3"], avoid_tracks)
        scene = "rain"

    # 主声轨默认走无缝循环，避免单轨 ASMR 走偶发模式出现十几秒死寂像没声音
    lead_mode = "intermittent" if (scene == "asmr" and any(k in full_say for k in ("偶发", "偶尔", "稀疏"))) else "loop"
    tracks.append(_build_track(bed_path, 0.70 if scene != "asmr" else 0.60, 0.0, lead_mode))
    reasoning.append(f"综合需求与标签匹配，选定「{TRACK_CATALOG[bed_path]['name']}」作为主声轨")

    # 2. 叠加兼容的纹理与点缀层（支持跨自然与 ASMR 混搭，严格避开 avoid_tracks）
    def add_if_valid(path, w, p, mode, den):
        if len(tracks) >= 4:
            return
        if path in avoid_tracks or any(t["path"] == path for t in tracks):
            return
        tracks.append(_build_track(path, w, p, mode, den))

    for kws, path, w, default_pan, default_mode, den, flag in OVERLAY_SPECS:
        if len(tracks) >= 4:
            break
        if any(k in positive for k in kws) and flag not in avoid_flags and path != bed_path:
            # 避免同一个关键词选出重复语义轨道（例如"翻书"不重复叠双书）
            if any(TRACK_CATALOG[t["path"]]["scene"] == TRACK_CATALOG[path]["scene"] and TRACK_CATALOG[t["path"]]["name"][:2] == TRACK_CATALOG[path]["name"][:2] for t in tracks):
                continue
            p = _pan_for_clause(positive, kws, default_pan)
            mode = "intermittent" if any(k in positive for k in ("偶", "稀疏", "点缀")) else default_mode
            add_if_valid(path, w, p, mode, den)

    if "雷" in positive and "雷" not in avoid_flags and "雷_档案" not in avoid_flags and "雷_记忆" not in avoid_flags:
        p = _pan_for_clause(positive, ("雷", "闷雷", "远雷"), 0.48)
        add_if_valid("远雷.hq.mp3", 0.36, p, "intermittent", 0.28)
        scene = "thunder"

    if (warmth == "warm" or "低鸣" in positive) and "低鸣" not in avoid_flags and bed_path in ("母带_城市夜雨_CC0.mp3", "柔和雨.hq.mp3", "海浪_远海.hq.mp3"):
        if len(tracks) < 3 and "溪" not in positive and scene != "asmr":
            add_if_valid("雨中低鸣.hq.mp3", 0.28, 0.0, "loop", 0.4)

    # 2.5 助眠心理学策略：浅睡遮蔽 vs 高认知唤醒轻情境转移杂念
    has_asmr_track = any(TRACK_CATALOG[t["path"]]["scene"] == "asmr" for t in tracks)
    if is_masking_sleep and scene != "asmr":
        # 浅睡/遮蔽外界杂音：去除雷声与未点名的近耳触发，保证宽频平稳不断档
        tracks = [t for t in tracks if TRACK_CATALOG[t["path"]]["layer"] == "bed" or t["path"] == "雨中低鸣.hq.mp3"]
        if not tracks:
            tracks = [_build_track("母带_城市夜雨_CC0.mp3", 0.72, 0.0, "loop")]
        reasoning.append("浅睡遮蔽策略：保留平稳宽频自然底幕，避开近耳突响防惊醒")
    elif not has_asmr_track and not wants_pure_only and "ASMR_档案" not in avoid_flags:
        if is_racing_mind or (ear_immersion >= 65 and len(tracks) < 3 and not any(k in positive for k in ("海", "浪", "溪", "火"))):
            if mood == "focus":
                cand_asmr = _pick_non_avoided(["ASMR_翻书单人_360781.hq.mp3", "ASMR_铅笔写字柔_336381.hq.mp3"], avoid_tracks)
                add_if_valid(cand_asmr, 0.34, -0.24, "intermittent", 0.42)
            else:
                cand_asmr = _pick_non_avoided(["ASMR_轻柔梳头_825798.hq.mp3", "ASMR_羽毛轻拂_708086.hq.mp3", "ASMR_采耳_690078.hq.mp3"], avoid_tracks)
                add_if_valid(cand_asmr, 0.34, -0.22, "intermittent", 0.38)
            if is_racing_mind:
                reasoning.append("睡前放空策略：自然底幕叠入无人声轻情境触发，温和拉走杂念")
            else:
                reasoning.append("结合你的听觉图鉴情境偏好，轻柔叠入无人声近耳伴随")

    if isinstance(user_context, dict) and isinstance(user_context.get("ear_profile"), dict):
        arch = user_context["ear_profile"].get("archetype_name")
        if arch:
            reasoning.append(f"已结合你的「{arch}」听觉图鉴偏好过滤敏感声音")
    if avoid_tracks:
        reasoning.append("已自动避开你历史否决过的音轨")

    if len(tracks) > 1:
        layer_names = "、".join(TRACK_CATALOG[t["path"]]["name"] for t in tracks[1:])
        reasoning.append(f"搭配「{layer_names}」并拉开左右方位与呼吸感")
    else:
        reasoning.append("保持单轨纯净真实录音，避免多余层干扰入睡")

    # 3. 构造标题、最终提示词与回复
    if scene == "fire":
        title = TRACK_CATALOG[bed_path]["name"]
    elif scene == "asmr":
        title = TRACK_CATALOG[tracks[0]["path"]]["name"]
        if len(tracks) > 1:
            title = title + "·" + TRACK_CATALOG[tracks[1]["path"]]["name"]
    elif scene == "ocean":
        title = "星夜远海" if "夜风.hq.mp3" in {t["path"] for t in tracks} else TRACK_CATALOG[bed_path]["name"]
    elif scene == "stream":
        title = TRACK_CATALOG[bed_path]["name"]
    elif scene == "forest":
        title = "夏夜林院"
    elif scene == "thunder":
        title = "雨夜远雷"
    elif warmth == "warm" and bed_path == "母带_城市夜雨_CC0.mp3":
        title = "窗边暖雨"
    else:
        title = TRACK_CATALOG[bed_path]["name"]

    final_prompt = _format_final_prompt(collected, tracks, full_say)
    layer_desc = " + ".join(TRACK_CATALOG[t["path"]]["name"] for t in tracks)
    avoid_note = "，已避开雷声" if ("雷" in avoid_flags or "雷_档案" in avoid_flags) else ""
    reply = f"已配好「{title}」（{layer_desc}）{avoid_note}。"

    return _sanitize_agent_design({
        "action": "compose",
        "title": title[:20],
        "reply": reply,
        "collected": collected,
        "final_prompt": final_prompt,
        "intent": {
            "scene": scene,
            "scene_detail": title,
            "mood": mood,
            "warmth": warmth,
            "dynamics": dynamics,
            "avoid": list(avoid_flags),
        },
        "reasoning": reasoning,
        "tracks": tracks,
        "followups": _default_followups(tracks),
    }, full_say, force_compose=True, collected_fallback=collected)


def from_local_design(
    say,
    current_tracks=None,
    history=None,
    user_context=None,
    qa_round=0,
    force_compose=False,
    initial_prompt="",
):
    if not LOCAL_URL:
        raise RuntimeError("未配置本地模型")
    messages = [{"role": "system", "content": qwen_client.AGENT_SYSTEM_PROMPT}]
    ctx_txt = "用户上下文：" + json.dumps({
        "qa_round": int(qa_round or 0),
        "force_compose": bool(force_compose),
        "initial_prompt": str(initial_prompt or "")[:300],
        "user_context": user_context or {},
        "current_tracks": current_tracks or [],
    }, ensure_ascii=False)
    messages.append({"role": "system", "content": ctx_txt})
    if isinstance(history, list):
        for h in history[-4:]:
            if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": str(h["content"])[:250]})
    messages.append({"role": "user", "content": say + "\n请严格输出 JSON。"})

    req = urllib.request.Request(LOCAL_URL, data=json.dumps({
        "model": "local-model",
        "messages": messages,
        "temperature": 0.2
    }).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    resp = urllib.request.urlopen(req, timeout=25)
    result = json.loads(resp.read().decode("utf-8"))
    text = result["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def design_soundscape(
    say,
    current_tracks=None,
    history=None,
    user_context=None,
    qa_round=0,
    force_compose=False,
    initial_prompt="",
):
    # 三层降级编排：Qwen3.8-Flash -> 本地 Spark 4B -> 多轮问答规则引擎
    must_compose = bool(force_compose) or int(qa_round or 0) >= 2 or bool(current_tracks) or any(
        k in str(say or "") for k in ("直接生成", "直接配", "跳过", "按目前信息", "不用再问")
    )
    merged_text = "；".join(
        p for p in [str(initial_prompt or "").strip(), str(say or "").strip()] if p
    )
    collected_fb = _extract_collected_slots(merged_text, user_context)

    try:
        raw = qwen_client.design_soundscape(
            say,
            current_tracks=current_tracks,
            history=history,
            user_context=user_context,
            qa_round=qa_round,
            force_compose=must_compose,
            initial_prompt=initial_prompt,
        )
        return _sanitize_agent_design(raw, merged_text, force_compose=must_compose, collected_fallback=collected_fb), "Qwen3.8-Flash"
    except Exception as e:
        print("[brain] design_soundscape 主力失败:", str(e)[:120], file=sys.stderr)

    if LOCAL_URL:
        try:
            raw_local = from_local_design(
                say,
                current_tracks=current_tracks,
                history=history,
                user_context=user_context,
                qa_round=qa_round,
                force_compose=must_compose,
                initial_prompt=initial_prompt,
            )
            return _sanitize_agent_design(raw_local, merged_text, force_compose=must_compose, collected_fallback=collected_fb), "本地模型"
        except Exception as e:
            print("[brain] design_soundscape 本地失败:", str(e)[:120], file=sys.stderr)

    return design_soundscape_rules(
        say,
        current_tracks=current_tracks,
        user_context=user_context,
        qa_round=qa_round,
        force_compose=must_compose,
        initial_prompt=initial_prompt,
        history=history,
    ), "规则匹配"


if os.environ.get("BRAIN_SELFTEST") == "1":
    test = "睡不着，想要窗外下大雨的声音，暖一点，别突然炸一下，不要雷声"
    intent, src = understand(test)
    print("来源：" + src)
    print(json.dumps(intent, ensure_ascii=False, indent=2))
