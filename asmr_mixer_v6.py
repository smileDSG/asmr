# ASMR 混音器 · V5 去爆裂声版
# 修复"意味不明的敲击声"：真凶是壁炉音效自带的柴火噼啪爆裂（幅度0.46）
# 两招：1) 壁炉移出主体  2) 对所有音效削峰，压平突发爆裂
# 需要 soundfile + numpy，用 default 环境运行

import soundfile as sf
import numpy as np
import os

RATE = 22050
DURATION = 30
SOUND_DIR = "real_sounds"


def load_sound(name):
    path = os.path.join(SOUND_DIR, name + ".ogg")
    data, sr = sf.read(path)
    if len(data.shape) > 1:
        data = data.mean(axis=1)
    if sr != RATE:
        old_len = len(data)
        new_len = int(old_len * RATE / sr)
        x_old = np.linspace(0, old_len - 1, old_len)
        x_new = np.linspace(0, new_len - 1, new_len)
        data = np.interp(x_new, x_old, data)
    return data


def de_crack(data, threshold):
    # 削峰：只修补突发爆裂，别处原样保留
    # 关键：不用 cumsum（会累积漂移），而是找到真正的突变点，
    # 在突变前后极短的窗口内用线性插值填平，其余样本完全不动
    out = data.copy()
    diff = np.abs(np.diff(data, prepend=data[0]))
    # 找出超过阈值的突变点
    spikes = np.where(diff > threshold)[0]
    # 把相邻的突变点聚成一段段爆裂
    groups = []
    for p in spikes:
        if groups and p - groups[-1][-1] <= 200:
            groups[-1].append(p)
        else:
            groups.append([p])
    # 每段爆裂：用窗口两端的好样本线性插值覆盖
    for g in groups:
        a = max(0, g[0] - 50)
        b = min(len(data), g[-1] + 50)
        left_val = data[a]
        right_val = data[b - 1]
        out[a:b] = np.linspace(left_val, right_val, b - a)
    return out


def take_segment(data, start, seconds):
    # 截取一段，不够就直接从头取（简单可靠，不玩复杂拼接）
    need = int(seconds * RATE)
    start_pos = int(start * RATE)
    long = np.tile(data, int(need / len(data)) + 2)
    return long[start_pos:start_pos + need]


def mix_weights(seconds):
    size = int(seconds * RATE)
    w = np.zeros((size, 6), dtype=float)
    for i in range(size):
        t = i / size
        if t < 0.2:
            w[i] = [0.60, 0, 0, 0, 0.10, 0]
        elif t < 0.8:
            # 主体：雨 + 微风 + 虫鸣，壁炉权重降到 0.08
            w[i] = [0.50, 0.08, 0, 0.10, 0.12, 0]
        else:
            w[i] = [0, 0, 0.55, 0, 0, 0.12]
    k = int(1.5 * RATE)
    half = k // 2
    # 用积分图做滑动平均，比 convolve 快几百倍
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

print("正在读取真实音效...")
names = ["sleep_rain", "soft_fireplace", "ocean_waves",
         "night_crickets", "gentle_wind", "morning_forest"]
sounds = []
for name in names:
    s = load_sound(name)
    s = de_crack(s, 0.08)  # 削峰，压平爆裂
    sounds.append(s)

starts = [0, 5, 10, 3, 8, 12]
segments = []
for i in range(len(sounds)):
    segments.append(take_segment(sounds[i], starts[i], DURATION))

print("正在按配方混音...")
weights = mix_weights(DURATION)
size = int(DURATION * RATE)
left = np.zeros(size)
right = np.zeros(size)
for k in range(len(segments)):
    left += segments[k] * weights[:, k]
    right += segments[k] * weights[:, k]

for i in range(1, size):
    right[i] = right[i] * 0.98 + left[i - 1] * 0.02

left = fade_in_out(left, 2.0, 4.0)
right = fade_in_out(right, 2.0, 4.0)

peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
if peak > 0:
    left = left * 0.85 / peak
    right = right * 0.85 / peak

diff = np.abs(np.diff(left))
print("最大跳变:", round(float(diff.max()), 4), "（V4 是 0.4531）")
print("前6秒直流偏移:", round(float(left[:int(6*RATE)].mean()), 5), "（V5 是 -0.040，应接近0）")

out = np.empty((size, 2), dtype=np.float32)
out[:, 0] = left
out[:, 1] = right
sf.write("output_real_v6.wav", out, RATE)
print("完成！戴上耳机听 output_real_v6.wav")
