# 温和降低「城市夜雨」母带里的警笛音量（不消除，只调小）。
#
# 原理：警笛是 480~1300Hz 之间来回扫动的窄带峰，雨声是宽频噪声。
# 用 STFT 找出"某频率比周围背景高很多"的窄峰，只压这些峰，雨声不动。
# 只跑一遍、最多压 60%（FACTOR=0.6），警笛还听得出，但不再刺耳。
#
# 用法：把要处理的音频放到 SRC，重跑本脚本即可。
# 需要 numpy + scipy + soundfile + 项目里的 素材执行层.py（写 MP3）。

import os

import numpy as np
from scipy import ndimage, signal
import soundfile as sf

import 素材执行层 as executor

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "product_assets", "母带_城市夜雨_CC0.mp3")
DST = SRC  # 直接覆盖母带；原版备份在 _tmp/母带_城市夜雨_原始备份.mp3

FACTOR = 0.6      # 最大压制幅度 60%，调大更安静、调小警笛更明显
BAND = (480, 1300)  # 警笛所在频段（Hz）
N_FFT = 4096

data, sr = sf.read(SRC, dtype="float32")
if data.ndim == 1:
    data = data[:, None]
length = len(data)
out = np.zeros_like(data)

for ch in range(data.shape[1]):
    freq, times, Z = signal.stft(data[:, ch], sr, nperseg=N_FFT, noverlap=N_FFT // 2)
    mag = np.abs(Z)
    # 频率方向的中位数 = 雨声背景；峰高出背景 3 倍以上才开始压
    bg = ndimage.median_filter(mag, size=(19, 1), mode="nearest")
    ratio = mag / (bg + 1e-9)
    band = (freq >= BAND[0]) & (freq <= BAND[1])
    over = np.clip((ratio - 3) / 8, 0, 1)
    atten = np.ones_like(mag)
    atten[band, :] = 1 - FACTOR * over[band, :]
    out[:, ch] = signal.istft(Z * atten, sr, nperseg=N_FFT, noverlap=N_FFT // 2)[1][:length]

out = np.clip(out, -1, 1)
fmt = executor.write_mp3(DST, out, sr)
print("已处理：%s  格式=%s  体积=%d B" % (DST, fmt, os.path.getsize(DST)))
