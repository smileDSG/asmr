# 分析"真实感"这段的底噪分布
# 核心：把声音分成"持续底噪"和"瞬间雨滴"
# 方法：STFT 后，每个频率算低分位数(=稳态底噪) 和 高分位数(=雨滴峰值)
# 哪里的低分位数高，哪里就是底噪重灾区

import soundfile as sf
import numpy as np

PATH = "E:/03_Projects/asmr/rain_candidates_v2/新候选4_窗边雨3_真实感.wav"

data, sr = sf.read(PATH, dtype="float64")
if len(data.shape) > 1:
    mono = data.mean(axis=1)
else:
    mono = data

# STFT 参数：46ms 一帧
win = 2048
hop = 1024
frames = []
for i in range(0, len(mono) - win, hop):
    seg = mono[i:i + win] * np.hanning(win)
    frames.append(np.abs(np.fft.rfft(seg)))
frames = np.array(frames)
freqs = np.fft.rfftfreq(win, 1.0 / sr)

# 每个频率的低分位(底噪) 和 高分位(雨滴)
floor_db = 20 * np.log10(np.percentile(frames, 20, axis=0) + 1e-10)
peak_db = 20 * np.log10(np.percentile(frames, 90, axis=0) + 1e-10)

print("频段".ljust(16) + "底噪(dB)".ljust(12) + "峰值(dB)".ljust(12) + "动态余量".ljust(10) + "判断")
print("-" * 68)
bands = [
    ("0-90Hz", 0, 90),
    ("90-250", 90, 250),
    ("250-500", 250, 500),
    ("500-1k", 500, 1000),
    ("1k-2k", 1000, 2000),
    ("2k-4k", 2000, 4000),
    ("4k-8k", 4000, 8000),
    ("8k-16k", 8000, 16000),
    ("16k+", 16000, 24000),
]
for name, lo, hi in bands:
    mask = (freqs >= lo) & (freqs < hi)
    if not mask.any():
        continue
    f = np.median(floor_db[mask])
    p = np.median(peak_db[mask])
    gap = p - f
    verdict = "底噪重" if gap < 12 else ("正常" if gap < 20 else "雨滴明显")
    print(name.ljust(16) + ("%.1f" % f).ljust(12) + ("%.1f" % p).ljust(12)
          + ("%.1f dB" % gap).ljust(10) + verdict)

# 整体：底噪占总能量的比例
noise_energy = np.percentile(frames, 20, axis=0)
total_energy = np.mean(frames, axis=0)
print("\n稳态底噪占总能量约 %.1f%%"
      % (noise_energy.sum() / total_energy.sum() * 100))
