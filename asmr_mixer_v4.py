# ASMR 混音器 · V4 真实素材版
# 这次用真实录音（CC0 助眠音效），彻底告别合成白噪声的"电视雪花声"
# 需要 soundfile 和 numpy（已装在 default 环境里）
# 运行方法见文件末尾说明

import soundfile as sf
import numpy as np
import os

RATE = 22050
DURATION = 30  # 成品时长（秒）

SOUND_DIR = "real_sounds"

# 可用的真实音效（都在 real_sounds 文件夹里）
# sleep_rain 夜雨 / soft_fireplace 壁炉 / ocean_waves 海浪
# gentle_wind 微风 / night_crickets 虫鸣 / morning_forest 晨林


def load_sound(name):
    # 读进一个音效，统一转成单声道、目标采样率
    path = os.path.join(SOUND_DIR, name + ".ogg")
    data, sr = sf.read(path)
    if len(data.shape) > 1:
        data = data.mean(axis=1)  # 双声道合成单声道
    # 简单重采样到 RATE
    if sr != RATE:
        old_len = len(data)
        new_len = int(old_len * RATE / sr)
        x_old = np.linspace(0, old_len - 1, old_len)
        x_new = np.linspace(0, new_len - 1, new_len)
        data = np.interp(x_new, x_old, data)
    return data


def take_segment(data, start, seconds):
    # 从音效里截取一段，不够长就循环接上
    need = int(seconds * RATE)
    start_pos = int(start * RATE)
    out = []
    filled = 0
    while filled < need:
        piece = data[start_pos:start_pos + need - filled]
        if len(piece) == 0:
            start_pos = 0
            piece = data[:need - filled]
        out.append(piece)
        filled = filled + len(piece)
        start_pos = start_pos + len(piece)
    return np.concatenate(out)


def stage_weights(t):
    # 分段配方：雨声、壁炉、海浪、虫鸣、微风、晨林
    if t < 0.2:
        # 引导段：雨声为主
        return [0.55, 0.0, 0.0, 0.0, 0.12, 0.0]
    elif t < 0.8:
        # 主体段：雨声 + 壁炉为主
        return [0.45, 0.35, 0.0, 0.08, 0.0, 0.0]
    else:
        # 收尾段：海浪为主，渐渐淡出
        return [0.0, 0.1, 0.5, 0.0, 0.0, 0.12]


def smooth_weights(t, seconds):
    w = np.array(stage_weights(t), dtype=float)
    fade = 2.0 / seconds
    for border in [0.2, 0.8]:
        if border - fade < t < border + fade:
            before = np.array(stage_weights(border - fade), dtype=float)
            after = np.array(stage_weights(border + fade), dtype=float)
            r = (t - (border - fade)) / (2 * fade)
            w = before * (1 - r) + after * r
    return w


def fade_in_out(audio, seconds, fi, fo):
    n = len(audio)
    ci = int(RATE * fi)
    co = int(RATE * fo)
    out = audio.copy()
    for i in range(ci):
        out[i] = out[i] * i / ci
    for i in range(co):
        out[n - 1 - i] = out[n - 1 - i] * i / co
    return out


# ============ 按顺序执行 ============

print("正在读取真实音效...")
names = ["sleep_rain", "soft_fireplace", "ocean_waves",
         "night_crickets", "gentle_wind", "morning_forest"]
sounds = []
for name in names:
    s = load_sound(name)
    sounds.append(s)
    print("  " + name + "  " + str(round(len(s) / RATE)) + " 秒")

# 每个音效取不同起点，避免同时开头听起来重复
starts = [0, 5, 10, 3, 8, 12]
segments = []
for i in range(len(sounds)):
    seg = take_segment(sounds[i], starts[i], DURATION)
    segments.append(seg)

print("正在按配方混音...")
size = int(DURATION * RATE)
left = np.zeros(size)
right = np.zeros(size)
for i in range(size):
    t = i / size
    w = smooth_weights(t, DURATION)
    for k in range(len(segments)):
        value = segments[k][i] * w[k]
        left[i] = left[i] + value
        right[i] = right[i] + value

# 轻微左右差异，制造空间感（真音效本身已有立体感，这里只做一点点）
for i in range(1, size):
    right[i] = right[i] * 0.98 + left[i - 1] * 0.02

left = fade_in_out(left, RATE, 2.0, 4.0)
right = fade_in_out(right, RATE, 2.0, 4.0)

peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
if peak > 0:
    left = left * 0.85 / peak
    right = right * 0.85 / peak

# 存成立体声 wav
out = np.empty((size, 2), dtype=np.float32)
out[:, 0] = left
out[:, 1] = right
sf.write("output_real_v4.wav", out, RATE)
print("完成！戴上耳机听 output_real_v4.wav")
