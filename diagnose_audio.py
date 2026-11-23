# 音频诊断：把"噪音"变成能看的数字
# 用 default 环境运行
# 目的：找出每个素材的能量都堆在哪些频段，以及循环接缝有没有爆音

import soundfile as sf
import numpy as np
import os

RATE = 48000
SOURCE_DIR = "real_sounds"
SAMPLE_DIR = "ai_samples"

# 频段划分。助眠音频的经验目标：
# 20-80Hz 是隆隆声/空调震动，多了会"闷、震"
# 80-250Hz 是低频厚度
# 250-1k 是声音主体
# 1k-4k 是雨滴/细节，少量才有真实感
# 4k-8k 开始刺耳
# 8k 以上基本是嘶声(hiss)，多了就是"电视雪花"
BANDS = [
    ("20-80Hz  隆隆", 20, 80),
    ("80-250   厚度", 80, 250),
    ("250-1k   主体", 250, 1000),
    ("1k-4k    细节", 1000, 4000),
    ("4k-8k    偏亮", 4000, 8000),
    ("8k-16k   嘶声", 8000, 16000),
    ("16k+     极高频", 16000, 24000),
]


def band_spectrum(data, sr):
    # 取单声道，分帧做 FFT 再平均，避免某一瞬间不准
    if len(data.shape) > 1:
        mono = data.mean(axis=1)
    else:
        mono = data
    mono = mono - mono.mean()

    win = 4096
    step = 2048
    n_frame = min(40, max(1, (len(mono) - win) // step))
    acc = np.zeros(win // 2 + 1)
    for i in range(n_frame):
        seg = mono[i * step: i * step + win]
        spec = np.abs(np.fft.rfft(seg * np.hanning(win)))
        acc += spec
    acc /= n_frame
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    return freqs, acc


def report(path, label):
    data, sr = sf.read(path)
    if len(data.shape) > 1:
        mono = data.mean(axis=1)
        channels = 2
    else:
        mono = data
        channels = 1

    rms = float(np.sqrt(np.mean(mono ** 2)))
    peak = float(np.max(np.abs(mono)))
    dc = float(mono.mean())
    freqs, spec = band_spectrum(data, sr)

    total = spec.sum() + 1e-12
    parts = []
    for name, lo, hi in BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        pct = spec[mask].sum() / total * 100
        parts.append((name, pct))

    # 循环接缝：素材首尾直接接起来时的跳变
    joint = float(np.max(np.abs(data[0] - data[-1])))
    typical = float(np.mean(np.abs(np.diff(mono[:min(len(mono), sr * 5)]))))

    print("=" * 66)
    print(label + "   [" + str(channels) + "ch, " + str(sr) + "Hz]")
    print("  RMS=" + fmt(rms) + "  峰值=" + fmt(peak) + "  直流偏移=" + fmt(dc))
    print("  循环接缝跳变=" + fmt(joint) + "  普通相邻采样=" + fmt(typical)
          + "  倍数=" + str(round(joint / (typical + 1e-9), 1)))
    print("  各频段能量占比：")
    for name, pct in parts:
        bar = "#" * int(pct / 1.2)
        print("    " + name + "  " + ("%5.1f%%" % pct) + "  " + bar)


def fmt(v):
    return ("%+.6f" % v)


print("### 原始素材 ###")
for name in ["sleep_rain", "soft_fireplace", "ocean_waves",
             "night_crickets", "gentle_wind", "morning_forest"]:
    p = os.path.join(SOURCE_DIR, name + ".ogg")
    if os.path.exists(p):
        report(p, name)

print("\n### 当前 AI 生成样例 ###")
if os.path.isdir(SAMPLE_DIR):
    for name in sorted(os.listdir(SAMPLE_DIR)):
        if name.endswith(".wav"):
            report(os.path.join(SAMPLE_DIR, name), "生成/" + name)

print("\n### 新版 AI 生成样例 ###")
if os.path.isdir("ai_samples_v2"):
    for name in sorted(os.listdir("ai_samples_v2")):
        if name.endswith(".wav") and not name.startswith("AB_"):
            report(os.path.join("ai_samples_v2", name), "新版/" + name)

print("\n### v3 分层版 AI 生成样例 ###")
if os.path.isdir("ai_samples_v3"):
    for name in sorted(os.listdir("ai_samples_v3")):
        if name.endswith(".wav"):
            report(os.path.join("ai_samples_v3", name), "v3/" + name)

print("\n### 基准：未加工原始雨声 ###")
if os.path.exists("raw_rain_30s.wav"):
    report("raw_rain_30s.wav", "raw_rain_30s")
