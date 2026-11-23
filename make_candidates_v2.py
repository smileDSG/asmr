# 按 Rainy Mood 的发现重做候选
# 关键改变：不再追求"瞬态少"，而是要有雨滴颗粒（15-50个/秒）
# 不再砍掉 8k 以上（那是雨滴的细碎声，砍了就成了白噪声）
# 只做：砍 20-90Hz 隆隆 + 降到睡前音量

import soundfile as sf
import numpy as np
from scipy.signal import butter, sosfiltfilt
import os

OUT = "rain_candidates_v2"
TARGET_RMS = 0.025
SOFT_LIMIT = 0.07

# 按瞬态密度挑的，接近 Rainy Mood 的 19.6/秒
PICKS = [
    ("freesound_previews/heavyrain_4.mp3", "新候选1_大雨4_颗粒多"),
    ("freesound_previews/heavyrain_5.mp3", "新候选2_大雨5_颗粒适中"),
    ("freesound_previews/rain_1.mp3", "新候选3_雨1_颗粒密"),
    ("freesound_previews/windowrain_3.mp3", "新候选4_窗边雨3_真实感"),
]


def process(src, dst):
    d, sr = sf.read(src, dtype="float64")
    if len(d.shape) > 1:
        m = d.mean(axis=1)
    else:
        m = d
    # 取中间20秒
    start = int(len(m) * 0.2)
    seg = m[start:start + int(sr * 20)]
    if sr != 48000:
        new_n = int(len(seg) * 48000 / sr)
        seg = np.interp(np.linspace(0, len(seg) - 1, new_n),
                        np.arange(len(seg)), seg)
        sr = 48000

    # 只砍隆隆，高频保留（Rainy Mood 有20%在8k+，那是雨滴）
    hp = butter(2, 85, btype="highpass", fs=sr, output="sos")
    x = sosfiltfilt(hp, seg)
    x = np.stack([x, x], axis=1)

    # 淡入淡出
    n = int(sr * 2)
    for i in range(n):
        x[i] *= i / n
        x[len(x) - 1 - i] *= i / n

    rms = np.sqrt(np.mean(x ** 2))
    if rms > 0:
        x = x * (TARGET_RMS / rms)
    x = np.tanh(x / SOFT_LIMIT) * SOFT_LIMIT

    sf.write(dst, x, sr, subtype="PCM_24")
    print("导出：" + os.path.basename(dst) + "  RMS=%.4f 峰值=%.3f"
          % (np.sqrt(np.mean(x ** 2)), np.max(np.abs(x))))


os.makedirs(OUT, exist_ok=True)
for src, name in PICKS:
    if os.path.exists(src):
        process(src, os.path.join(OUT, name + ".wav"))
