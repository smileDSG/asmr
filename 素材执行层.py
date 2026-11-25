# 执行层：意图 → 从 41 段 CC0 素材库（sound_catalog）挑 + 配 → 零处理拼接
# 铁律：不滤波、不降噪、不压缩、不加混响、不调音
# 唯一允许的处理：循环补时长 + 接缝短交叉淡化（避免 click，不属于音质加工）

import os
import numpy as np

import sound_catalog

try:
    import soundfile as _sf
except ImportError:
    _sf = None


def read_audio(path):
    """读取音频为 float32 二维数组 (frames, channels) 和采样率；优先 soundfile，缺省回退 PyAV。"""
    if _sf is not None:
        return _sf.read(path, dtype="float32", always_2d=True)
    import av
    container = av.open(path)
    try:
        stream = container.streams.audio[0]
        file_sr = int(stream.rate)
        chunks = []
        for frame in container.decode(audio=0):
            arr = frame.to_ndarray()
            if arr.ndim == 1:
                arr = arr[:, None]
            elif frame.format.is_planar:
                arr = arr.T
            if np.issubdtype(arr.dtype, np.integer):
                info = np.iinfo(arr.dtype)
                scale = float(max(abs(info.min), info.max))
                arr = arr.astype("float32") / scale
            else:
                arr = arr.astype("float32")
            chunks.append(arr)
    finally:
        container.close()
    if not chunks:
        return np.zeros((0, 2), dtype="float32"), file_sr
    return np.concatenate(chunks, axis=0).astype("float32"), file_sr


def write_wav(target, data, sr):
    """写出 16-bit PCM WAV（支持文件路径或 BytesIO）；优先 soundfile，缺省回退 scipy.io.wavfile。"""
    if _sf is not None:
        _sf.write(target, data, int(sr), format="WAV", subtype="PCM_16")
        return
    from scipy.io import wavfile
    pcm = (np.clip(data, -1.0, 1.0) * 32767.0).astype("<i2")
    wavfile.write(target, int(sr), pcm)

BASE = os.path.dirname(os.path.abspath(__file__))

# 素材库：从单一真相源 sound_catalog 动态构建按场景分布的候选权重表
LIBRARY = sound_catalog.build_library_by_scene()

# 心情 → 微调权重（只动配比，不动音质）
MOOD_TWEAK = {
    "sleep": {"dynamics": "steady"},
    "focus": {"dynamics": "steady"},
    "relax": {},
    "calm": {},
}


def _item_matches_avoid(rel, avoid_list):
    if not avoid_list:
        return False
    meta = sound_catalog.get_item(rel)
    avoid_text = " ".join(str(a) for a in avoid_list)
    if "雷" in avoid_text and "雷" in rel:
        return True
    if not meta:
        return False
    for tag in meta.get("avoid_tags", []):
        if tag and tag in avoid_text:
            return True
    if meta.get("name") and meta["name"] in avoid_text:
        return True
    return False


def pick(intent, allowed=None):
    # 根据意图与 sound_catalog 标签挑素材和权重，返回 [(路径, 权重), ...]
    # allowed 传 rel_path 集合时，只在集合内挑（免费用户只给免费层）
    scene = intent.get("scene", "rain")
    if scene not in LIBRARY:
        scene = "rain"
    items = list(LIBRARY[scene])
    detail = str(intent.get("scene_detail") or "")
    avoid = intent.get("avoid", [])

    # 1. 按禁忌标签与名称过滤（如不要雷、不要噼啪、不要音乐垫、不要鸟等）
    cleaned = [(rel, w) for rel, w in items if not _item_matches_avoid(rel, avoid)]
    if cleaned:
        items = cleaned

    # 2. 按场景细节与暖度/动态偏好，从已入库 41 段中精细落位
    warmth = intent.get("warmth", "neutral")
    dynamics = intent.get("dynamics", "natural")

    if scene == "rain":
        if "帐篷" in detail and any("592996" in rel for rel, _ in items):
            items = [("scene_assets/帐篷雨_小帐篷大雨_592996.hq.mp3", 1.0)]
        elif warmth == "warm":
            items = [
                ("product_assets/母带_城市夜雨_CC0.mp3", 0.6),
                ("scene_assets/柔和雨.hq.mp3", 0.4),
            ]
    elif scene == "fire":
        if any("766127" in rel for rel, _ in items) and ("夜营" in detail or "柔" in detail or dynamics == "steady"):
            # 若明确要壁炉低燃选 836535，否则稳/柔偏好可选夜营余烬 766127
            if "壁炉" in detail and any("836535" in rel for rel, _ in items):
                items = [("scene_assets/炉火_壁炉低燃_836535.hq.mp3", 1.0)]
            else:
                items = [("scene_assets/炉火_夜营氛围_766127.hq.mp3", 1.0)]
        elif "篝火" in detail and any("62487" in rel for rel, _ in items):
            items = [("scene_assets/炉火_营地篝火_62487.hq.mp3", 1.0)]
    elif scene == "stream" and (warmth == "warm" or dynamics == "steady"):
        if any("707576" in rel for rel, _ in items):
            items = [("scene_assets/溪流_柔和河水_707576.hq.mp3", 1.0)]
    elif scene == "ocean" and (warmth == "warm" or dynamics == "steady"):
        if any("451532" in rel for rel, _ in items):
            items = [("scene_assets/海浪_湖海柔浪_451532.hq.mp3", 1.0)]
    elif scene == "forest" and ("鸟" in detail or "夜莺" in detail):
        if any("853566" in rel for rel, _ in items):
            items = [
                ("scene_assets/林风_Akacie_73708.hq.mp3", 0.65),
                ("scene_assets/鸟鸣_夜莺鸣叫_853566.hq.mp3", 0.35),
            ]
    elif scene == "asmr":
        if "羽毛" in detail and "采耳" in detail:
            items = [
                ("scene_assets/ASMR_采耳_690078.hq.mp3", 0.62),
                ("scene_assets/ASMR_羽毛轻拂_708086.hq.mp3", 0.38),
            ]
        elif "翻书" in detail:
            items = [("scene_assets/ASMR_翻书多人_575764.hq.mp3", 1.0)]
        elif "写字" in detail:
            items = [("scene_assets/ASMR_铅笔写字柔_336381.hq.mp3", 1.0)]

    # 3. 兜底再做一次禁忌检查，确保特殊覆盖分支也不会漏进禁忌轨
    final_items = [(rel, w) for rel, w in items if not _item_matches_avoid(rel, avoid)]
    if final_items:
        items = final_items

    # 4. 素材权限：免费用户只在免费层里挑，挑不到就退到该场景的免费默认首选
    if allowed is not None:
        items = _limit_to_allowed(items, set(allowed), scene, avoid)

    # 全部权重为 0 时，默认选第一个
    total = sum(w for _, w in items)
    if total <= 0 and items:
        items[0] = (items[0][0], 1.0)
    return items


def _limit_to_allowed(items, allowed, scene, avoid):
    # 先把越权的素材剔掉，剩下的权重要重新归一，别把整体音量弄小
    kept = [(rel, w) for rel, w in items if rel in allowed]
    if kept:
        total = sum(w for _, w in kept)
        if total > 0:
            kept = [(rel, w / total) for rel, w in kept]
        return kept

    # 原本挑的全是付费素材：退到这个场景里免费的那几段
    fallback = [(rel, w) for rel, w in LIBRARY.get(scene, []) if rel in allowed]
    fallback = [(rel, w) for rel, w in fallback if not _item_matches_avoid(rel, avoid)]
    if fallback:
        fallback.sort(key=lambda pair: -pair[1])
        picked = [(rel, w) for rel, w in fallback[:2] if w > 0]
        if not picked:
            picked = [(fallback[0][0], 1.0)]
        total = sum(w for _, w in picked)
        if total > 0:
            return [(rel, w / total) for rel, w in picked]
    # 兜底：宁可给出原本的结果，也不要让用户拿到空音频
    return items


def load_loop(path, target_frames, sr):
    # 读取素材，循环到目标长度；只做声道对齐、采样率对齐与接缝等功率交叉淡化，不改音色
    data, file_sr = read_audio(path)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]

    # 按目标采样率重采样（采样率对齐是拼接必需，不属于音质加工）
    if file_sr != sr:
        old_len = len(data)
        new_len = max(1, int(old_len * sr / file_sr))
        x_old = np.linspace(0, old_len - 1, old_len)
        x_new = np.linspace(0, old_len - 1, new_len)
        left = np.interp(x_new, x_old, data[:, 0])
        right = np.interp(x_new, x_old, data[:, 1])
        data = np.stack([left, right], axis=1).astype("float32")

    if len(data) >= target_frames:
        return data[:target_frames]

    # 循环拼接，接缝使用最高 0.8s 等功率余弦交叉淡化（避免短素材接缝听出电平凹陷）
    fade = min(int(sr * 0.8), len(data) // 6)
    out = data.copy()
    while len(out) < target_frames:
        need = target_frames - len(out)
        seg = data[:need] if need <= len(data) else data
        if fade > 0 and fade < len(out) and fade < len(seg):
            n = min(fade, len(seg), len(out))
            tail = out[-n:].copy()
            head = seg[:n].copy()
            theta = np.linspace(0.0, np.pi * 0.5, n, dtype="float32")[:, None]
            seg = seg.copy()
            seg[:n] = tail * np.cos(theta) + head * np.sin(theta)
            out = out[:-n]
        out = np.concatenate([out, seg], axis=0)
    return out[:target_frames]


def render(intent, out_path, minutes=30):
    items = pick(intent)
    sr = 44100
    frames = int(sr * 60 * minutes)

    # 逐段读取并循环，按权重混合
    mix = np.zeros((frames, 2), dtype="float32")
    for rel, w in items:
        path = os.path.join(BASE, rel)
        if w <= 0:
            continue
        if not os.path.exists(path):
            print("跳过缺失素材：" + rel)
            continue
        seg = load_loop(path, frames, sr)
        mix += seg * w

    # 归一化到安全峰值（避免削波失真，属于电平保护，不是音质加工）
    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix = mix * (0.95 / peak)

    # 首尾 1 秒淡入淡出，避免开头结尾爆音
    fi = int(sr * 1.0)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    mix[-fi:] *= np.linspace(1, 0, fi)[:, None]

    write_wav(out_path, mix, sr)
    return items


if os.environ.get("EXEC_SELFTEST") == "1":
    test = {
        "scene": "rain", "scene_detail": "窗外大雨", "mood": "sleep",
        "warmth": "warm", "dynamics": "steady", "avoid": ["雷声"],
        "duration_minutes": 30, "confidence": 0.9
    }
    items = pick(test)
    print("挑选结果：")
    for p, w in items:
        print("  %.1f  %s" % (w, p))
