# ASMR 混音器 · V7 立体声版
# 关键修复：不再把立体声拍成单声道，保留真实左右耳差异（这是"身临其境"的来源）
# 需要 soundfile + numpy，用 default 环境运行

import soundfile as sf
import numpy as np
import os

RATE = 48000  # 直接用高采样率，保住音质（原始素材是 48k）
DURATION = 30
SOUND_DIR = "real_sounds"


def resample(data, sr):
    # 重采样，双声道要分左右各自处理
    if sr == RATE:
        return data
    old_len = data.shape[0]
    new_len = int(old_len * RATE / sr)
    x_old = np.linspace(0, old_len - 1, old_len)
    x_new = np.linspace(0, new_len - 1, new_len)
    if len(data.shape) > 1:
        left = np.interp(x_new, x_old, data[:, 0])
        right = np.interp(x_new, x_old, data[:, 1])
        return np.stack([left, right], axis=1)
    else:
        return np.interp(x_new, x_old, data)


def load_sound(name):
    path = os.path.join(SOUND_DIR, name + ".ogg")
    data, sr = sf.read(path)
    data = resample(data, sr)
    return data


def de_crack(data, threshold):
    # 削峰：只在爆裂点附近局部修补，双声道分别处理
    out = data.copy()
    channels = 1 if len(data.shape) == 1 else 2
    for ch in range(channels):
        sig = out[:, ch] if channels == 2 else out
        src = data[:, ch] if channels == 2 else data
        diff = np.abs(np.diff(sig, prepend=sig[0]))
        spikes = np.where(diff > threshold)[0]
        groups = []
        for p in spikes:
            if groups and p - groups[-1][-1] <= 200:
                groups[-1].append(p)
            else:
                groups.append([p])
        for g in groups:
            a = max(0, g[0] - 50)
            b = min(len(sig), g[-1] + 50)
            if len(src) > 0:
                lv, rv = src[a], src[b - 1]
                fix = np.linspace(lv, rv, b - a)
                if channels == 2:
                    out[a:b, ch] = fix
                else:
                    out[a:b] = fix
    return out


def take_segment(data, start, seconds):
    # 截取，不够就循环平铺。双声道一起切，保持左右对应
    need = int(seconds * RATE)
    start_pos = int(start * RATE)
    long = np.tile(data, (int(need / len(data)) + 2, 1))
    return long[start_pos:start_pos + need]


def mix_weights(seconds):
    size = int(seconds * RATE)
    w = np.zeros((size, 6), dtype=float)
    for i in range(size):
        t = i / size
        if t < 0.2:
            w[i] = [0.60, 0, 0, 0, 0.10, 0]
        elif t < 0.8:
            w[i] = [0.50, 0.08, 0, 0.10, 0.12, 0]
        else:
            w[i] = [0, 0, 0.55, 0, 0, 0.12]
    k = int(1.5 * RATE)
    half = k // 2
    for j in range(6):
        padded = np.concatenate([np.zeros(half), w[:, j], np.zeros(k - half)])
        cs = np.cumsum(padded)
        smooth = (cs[k:] - cs[:-k]) / k
        w[:, j] = smooth[:size]
    return w


def fade_in_out(audio, fi, fo):
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

print("正在读取真实音效（保留立体声）...")
names = ["sleep_rain", "soft_fireplace", "ocean_waves",
         "night_crickets", "gentle_wind", "morning_forest"]
sounds = []
for name in names:
    s = load_sound(name)
    s = de_crack(s, 0.08)
    sounds.append(s)

starts = [0, 5, 10, 3, 8, 12]
segments = []
for i in range(len(sounds)):
    segments.append(take_segment(sounds[i], starts[i], DURATION))

print("正在按配方混音...")
weights = mix_weights(DURATION)
size = int(DURATION * RATE)
mix = np.zeros((size, 2), dtype=float)
for k in range(len(segments)):
    # 左右声道各自独立叠加，真实空间信息完全保留
    mix += segments[k] * weights[:, k][:, None]

mix = fade_in_out(mix, 2.0, 4.0)

peak = np.max(np.abs(mix))
if peak > 0:
    mix = mix * 0.85 / peak

print("左声道直流偏移:", round(float(mix[:int(6*RATE), 0].mean()), 5))
print("左右声道差异:", round(float(np.abs(mix[:, 0] - mix[:, 1]).mean()), 5), "（V6 接近0，就是被拍平了）")

sf.write("output_real_v7.wav", mix, RATE)
print("完成！戴上耳机听 output_real_v7.wav")
