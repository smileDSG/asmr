# 解剖 Rainy Mood：几百万人听的雨声到底和我下载的差在哪
# 这是真正的"参照"，不再闭门造车

import soundfile as sf
import numpy as np
import os

RATE = 48000

BANDS = [
    ("20-80Hz 隆隆", 20, 80),
    ("80-250 厚度", 80, 250),
    ("250-1k 主体", 250, 1000),
    ("1k-4k 细节", 1000, 4000),
    ("4k-8k 偏亮", 4000, 8000),
    ("8k-16k 嘶声", 8000, 16000),
    ("16k+", 16000, 24000),
]


def analyze(path, label, seconds=60):
    info = sf.info(path)
    sr = info.samplerate
    # 从中间取一段分析，避开开头
    skip = int(min(info.frames * 0.2, sr * seconds))
    data, sr2 = sf.read(path, start=skip, frames=int(sr * seconds), dtype="float64")
    if len(data.shape) > 1:
        mono = data.mean(axis=1)
        ch = data.shape[1]
    else:
        mono = data
        ch = 1

    rms = float(np.sqrt(np.mean(mono ** 2)))
    peak = float(np.max(np.abs(mono)))

    win = 4096
    step = 2048
    n = min(60, (len(mono) - win) // step)
    acc = np.zeros(win // 2 + 1)
    for i in range(n):
        seg = mono[i * step:i * step + win]
        acc += np.abs(np.fft.rfft(seg * np.hanning(win)))
    acc /= n
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    total = acc.sum() + 1e-12

    pcts = []
    for name, lo, hi in BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        pcts.append(acc[mask].sum() / total * 100)

    # 瞬态密度：相邻采样跳变超过中位数8倍
    jump = np.abs(np.diff(mono[:sr * 10]))
    med = np.median(jump) + 1e-9
    clicks = np.sum(jump > med * 8) / 10.0

    # 波动性：1秒一帧的RMS变化，看是否有自然起伏
    frame = sr
    rms_series = []
    for i in range(0, len(mono) - frame, frame):
        seg = mono[i:i + frame]
        rms_series.append(np.sqrt(np.mean(seg ** 2)))
    rms_series = np.array(rms_series)
    variation = float(np.std(rms_series) / (np.mean(rms_series) + 1e-9))

    print("=" * 70)
    print(label + "   [" + str(ch) + "声道 " + str(sr) + "Hz]")
    print("  时长样本 " + str(seconds) + "秒  RMS=%.4f 峰值=%.4f 峰均比=%.1f"
          % (rms, peak, peak / (rms + 1e-9)))
    print("  瞬态密度=%.1f个/秒  音量起伏=%.1f%%" % (clicks, variation * 100))
    print("  频段分布：")
    for i, b in enumerate(BANDS):
        print("    " + b[0].ljust(14) + ("%5.1f%%" % pcts[i]) + "  " + "#" * int(pcts[i] / 1.5))
    return pcts, clicks, variation


# 参照：Rainy Mood
rm_pct, rm_click, rm_var = analyze(
    "reference_audio/rainymood.mp3", "【参照】Rainy Mood 几百万人在听", seconds=60)

# 对照：我下载的最像样的几个素材
for name, label in [
    ("rain_0.mp3", "【我的】rain_0 绵密型"),
    ("heavyrain_5.mp3", "【我的】heavyrain_5 厚实型"),
    ("windowrain_3.mp3", "【我的】windowrain_3 有雨滴"),
]:
    p = os.path.join("freesound_previews", name)
    if os.path.exists(p):
        analyze(p, label, seconds=20)
