# 执行层：意图 → 从 13 段 CC0 素材挑 + 配 → 零处理拼接
# 铁律：不滤波、不降噪、不压缩、不加混响、不调音
# 唯一允许的处理：循环补时长 + 接缝短交叉淡化（避免 click，不属于音质加工）

import os
import numpy as np

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

# 素材库：场景 → 候选文件 + 默认权重
LIBRARY = {
    "rain": [
        ("product_assets/母带_城市夜雨_CC0.mp3", 1.0),
        ("product_assets/备选_大雨打树叶_CC0.mp3", 0.0),
        ("scene_assets/柔和雨.hq.mp3", 0.0),
        ("scene_assets/乡村小雨.hq.mp3", 0.0),
    ],
    "ocean": [
        ("scene_assets/海浪_远海.hq.mp3", 1.0),
        ("scene_assets/海浪_黑海.hq.mp3", 0.0),
    ],
    "stream": [
        ("scene_assets/溪流.hq.mp3", 1.0),
    ],
    "thunder": [
        ("product_assets/母带_城市夜雨_CC0.mp3", 0.7),
        ("scene_assets/远雷.hq.mp3", 0.3),
    ],
    "wind": [
        ("scene_assets/夜风.hq.mp3", 1.0),
    ],
    "forest": [
        ("scene_assets/虫鸣.hq.mp3", 0.5),
        ("scene_assets/夜风.hq.mp3", 0.5),
    ],
    "mix": [
        ("product_assets/母带_城市夜雨_CC0.mp3", 0.7),
        ("scene_assets/雨中低鸣.hq.mp3", 0.3),
    ],
    "fire": [
        ("scene_assets/雨中低鸣.hq.mp3", 1.0),
    ],
}

# 心情 → 微调权重（只动配比，不动音质）
MOOD_TWEAK = {
    "sleep": {"dynamics": "steady"},
    "focus": {"dynamics": "steady"},
    "relax": {},
    "calm": {},
}


def pick(intent):
    # 根据意图挑素材和权重，返回 [(路径, 权重), ...]
    scene = intent["scene"]
    if scene not in LIBRARY:
        scene = "rain"
    items = list(LIBRARY[scene])

    # 用户明确不要雷 → 去掉远雷
    avoid = intent.get("avoid", [])
    cleaned = []
    for path, w in items:
        if "雷" in path and any("雷" in str(a) for a in avoid):
            continue
        cleaned.append((path, w))
    if cleaned:
        items = cleaned

    # 暖/柔 → 雨声偏向柔和雨/乡村小雨（都经用户验收，非音质加工）
    if intent.get("warmth") == "warm" and scene == "rain":
        items = [
            ("product_assets/母带_城市夜雨_CC0.mp3", 0.6),
            ("scene_assets/柔和雨.hq.mp3", 0.4),
        ]

    # 全部权重为 0 时，默认选第一个
    total = sum(w for _, w in items)
    if total <= 0:
        items[0] = (items[0][0], 1.0)
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
