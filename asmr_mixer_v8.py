# ASMR 混音器 · V8 时域平滑版
# 关键改变：放弃"削峰"（抓不到渐变型突发），改用全局轻微时域平滑
# 任何形状的突发（雨滴、噼啪、接缝）都会被抹圆，且保立体声、不引入直流偏移
# 需要 soundfile + numpy，用 default 环境运行

import soundfile as sf
import numpy as np
import os

RATE = 48000
DURATION = 30
SOUND_DIR = "real_sounds"


def resample(data, sr):
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
    return np.interp(x_new, x_old, data)


def load_sound(name):
    data, sr = sf.read(os.path.join(SOUND_DIR, name + ".ogg"))
    return resample(data, sr)


def take_segment(data, start, seconds):
    need = int(seconds * RATE)
    start_pos = int(start * RATE)
    if len(data.shape) > 1:
        long = np.tile(data, (int(need / len(data)) + 2, 1))
    else:
        long = np.tile(data, int(need / len(data)) + 2)
    seg = long[start_pos:start_pos + need]
    return seg


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
        w[:, j] = (cs[k:] - cs[:-k]) / k
    return w


def smooth_audio(audio, window_ms):
    # 时域滑动平均：中心化窗口，抹圆所有突发，不引入直流偏移
    # 用积分图实现，双声道各自处理，速度快
    k = int(RATE * window_ms / 1000)
    if k % 2 == 0:
        k += 1
    half = k // 2
    out = np.empty_like(audio)
    for ch in range(audio.shape[1]):
        sig = audio[:, ch]
        padded = np.concatenate([np.full(half, sig[0]), sig, np.full(half + 1, sig[-1])])
        cs = np.cumsum(padded)
        smooth = (cs[k:] - cs[:-k]) / k
        out[:, ch] = smooth[:len(sig)]
    return out


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

print("正在读取真实音效（立体声）...")
names = ["sleep_rain", "soft_fireplace", "ocean_waves",
         "night_crickets", "gentle_wind", "morning_forest"]
sounds = []
for name in names:
    sounds.append(load_sound(name))

starts = [0, 5, 10, 3, 8, 12]
segments = []
for i in range(len(sounds)):
    segments.append(take_segment(sounds[i], starts[i], DURATION))

print("正在按配方混音...")
weights = mix_weights(DURATION)
size = int(DURATION * RATE)
mix = np.zeros((size, 2), dtype=float)
for k in range(len(segments)):
    mix += segments[k] * weights[:, k][:, None]

print("正在时域平滑，抹圆突发声...")
mix = smooth_audio(mix, 8)  # 8毫秒窗口，足够抹掉"嗒"声，又不糊

mix = fade_in_out(mix, 2.0, 4.0)
peak = np.max(np.abs(mix))
if peak > 0:
    mix = mix * 0.85 / peak

diff = np.abs(np.diff(mix[:, 0]))
print("最大跳变:", round(float(diff.max()), 4), "（V7 是 0.2421）")
print("直流偏移:", round(float(mix[:int(6*RATE), 0].mean()), 5))
print("左右差异:", round(float(np.abs(mix[:, 0] - mix[:, 1]).mean()), 5))

sf.write("output_real_v8.wav", mix, RATE)
print("完成！戴上耳机听 output_real_v8.wav")
