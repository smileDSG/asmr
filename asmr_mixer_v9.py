# ASMR 混音器 · V9 零加工版
# 回到根本：不削峰、不平滑、不搞任何修复
# 只用原始立体声素材做分段混音 + 淡入淡出
# 目的：确认问题到底出在"素材"还是"我的处理"

import soundfile as sf
import numpy as np
import os

RATE = 48000
DURATION = 30
SOUND_DIR = "real_sounds"


def resample(data, sr):
    if sr == RATE:
        return data
    n = int(data.shape[0] * RATE / sr)
    xo = np.linspace(0, data.shape[0] - 1, data.shape[0])
    xn = np.linspace(0, data.shape[0] - 1, n)
    left = np.interp(xn, xo, data[:, 0])
    right = np.interp(xn, xo, data[:, 1])
    return np.stack([left, right], axis=1)


def load(name):
    data, sr = sf.read(os.path.join(SOUND_DIR, name + ".ogg"))
    return resample(data, sr)


def take(data, start, seconds):
    need = int(seconds * RATE)
    pos = int(start * RATE)
    long = np.tile(data, (int(need / len(data)) + 2, 1))
    return long[pos:pos + need]


def weights(seconds):
    size = int(seconds * RATE)
    w = np.zeros((size, 6))
    for i in range(size):
        t = i / size
        if t < 0.2:
            w[i] = [0.6, 0, 0, 0, 0.1, 0]
        elif t < 0.8:
            w[i] = [0.5, 0.08, 0, 0.1, 0.12, 0]
        else:
            w[i] = [0, 0, 0.55, 0, 0, 0.12]
    k = int(1.5 * RATE)
    half = k // 2
    for j in range(6):
        p = np.concatenate([np.zeros(half), w[:, j], np.zeros(k - half)])
        cs = np.cumsum(p)
        w[:, j] = (cs[k:] - cs[:-k]) / k
    return w


def fade(audio, fi, fo):
    n = len(audio)
    ci, co = int(RATE * fi), int(RATE * fo)
    out = audio.copy()
    for i in range(ci):
        out[i] *= i / ci
    for i in range(co):
        out[n - 1 - i] *= i / co
    return out


print("读取原始立体声素材，不做任何修复...")
names = ["sleep_rain", "soft_fireplace", "ocean_waves",
         "night_crickets", "gentle_wind", "morning_forest"]
starts = [0, 5, 10, 3, 8, 12]
segs = []
for name, start in zip(names, starts):
    segs.append(take(load(name), start, DURATION))

w = weights(DURATION)
size = int(DURATION * RATE)
mix = np.zeros((size, 2))
for k in range(len(segs)):
    mix += segs[k] * w[:, k][:, None]

mix = fade(mix, 2.0, 4.0)
peak = np.max(np.abs(mix))
mix = mix * 0.85 / peak if peak > 0 else mix

sf.write("output_raw_v9.wav", mix, RATE)
print("完成！听 output_raw_v9.wav —— 这是零加工版")
