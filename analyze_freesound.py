# 给新下载的 Freesound 素材做体检
# 用和 diagnose_audio.py 一样的频段划分，挑出"暖、稳、没有嘶声"的素材

import soundfile as sf
import numpy as np
import os

RATE = 48000
DIR = "freesound_previews"

BANDS = [
    ("20-80Hz", 20, 80),
    ("80-250 ", 80, 250),
    ("250-1k ", 250, 1000),
    ("1k-4k  ", 1000, 4000),
    ("4k-8k  ", 4000, 8000),
    ("8k-16k ", 8000, 16000),
    ("16k+   ", 16000, 24000),
]


def analyze(path):
    data, sr = sf.read(path, dtype="float64")
    if len(data.shape) > 1:
        mono = data.mean(axis=1)
        ch = 2
    else:
        mono = data
        ch = 1
    # 只取前 30 秒分析
    take = mono[:min(len(mono), sr * 30)]
    rms = float(np.sqrt(np.mean(take ** 2)))

    win = 4096
    step = 2048
    n = min(30, max(1, (len(take) - win) // step))
    acc = np.zeros(win // 2 + 1)
    for i in range(n):
        seg = take[i * step:i * step + win]
        acc += np.abs(np.fft.rfft(seg * np.hanning(win)))
    acc /= n
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    total = acc.sum() + 1e-12

    pcts = []
    for name, lo, hi in BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        pcts.append(acc[mask].sum() / total * 100)

    # 峰均比：越小越稳
    peak = float(np.max(np.abs(take)))
    crest = peak / (rms + 1e-9)

    # 瞬态密度：相邻采样跳变超过中位数 8 倍的次数（每秒）
    jump = np.abs(np.diff(take[:sr * 10]))
    med = np.median(jump) + 1e-9
    clicks = int(np.sum(jump > med * 8)) / 10.0

    return {
        "name": os.path.basename(path),
        "ch": ch, "sr": sr, "rms": rms, "crest": crest, "clicks": clicks,
        "pcts": pcts
    }


results = []
for name in sorted(os.listdir(DIR)):
    if name.endswith(".mp3"):
        try:
            results.append(analyze(os.path.join(DIR, name)))
        except Exception as e:
            print("跳过 " + name + ": " + str(e)[:40])

print("素材名".ljust(22) + "声道 采样率  RMS    峰均比  瞬态/秒  暖度  嘶声  厚度")
print("-" * 84)
for r in results:
    warm = r["pcts"][1] + r["pcts"][2]      # 80-1k
    hiss = r["pcts"][5] + r["pcts"][6]      # 8k+
    body = r["pcts"][1]                      # 80-250
    print(r["name"].ljust(22)
          + str(r["ch"]).ljust(5)
          + str(r["sr"] // 1000).ljust(7)
          + ("%.4f" % r["rms"]).ljust(8)
          + ("%.1f" % r["crest"]).ljust(8)
          + ("%.1f" % r["clicks"]).ljust(9)
          + ("%4.1f%%" % warm).ljust(7)
          + ("%4.1f%%" % hiss).ljust(7)
          + ("%4.1f%%" % body))

print("\n详细频段（节选，按瞬态密度从低到高排序）：")
for r in sorted(results, key=lambda x: x["clicks"])[:8]:
    parts = []
    for i, b in enumerate(BANDS):
        parts.append(b[0] + "=" + ("%.1f" % r["pcts"][i]))
    print("  " + r["name"])
    print("    " + "  ".join(parts))
