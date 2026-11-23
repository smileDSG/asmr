# 雨声安静版：只做三件事
# 1. 砍掉 20-80Hz 隆隆（人耳听不清但让人烦躁的"底噪"）
# 2. 砍掉 8kHz 以上嘶声（磁带感/雪花感）
# 3. 把音量降到真正适合睡前听的水平
# 中间频段（雨声本体）一个字不改，不加混响、不加压缩、不加起伏

import soundfile as sf
import numpy as np
from scipy.signal import butter, sosfiltfilt
import glob
import os

SRC = "rain_candidates"
OUT = "rain_quiet"
DURATION = 20

# 目标电平：约 -34 dBFS。之前 0.12 是 -18 dBFS，差了 16 dB
TARGET_RMS = 0.020
MAX_PEAK = 0.10
# 峰值上限改用软限幅，避免个别尖峰把整体电平占死
SOFT_LIMIT = 0.055

# 高通去隆隆，低通去嘶声
HIGH_PASS = 90
LOW_PASS = 6500


def clean(data, sr):
    # 先统一到 48000
    if sr != 48000:
        old_n = data.shape[0]
        new_n = int(old_n * 48000 / sr)
        xo = np.linspace(0, old_n - 1, old_n)
        xn = np.linspace(0, old_n - 1, new_n)
        if len(data.shape) > 1:
            data = np.stack([np.interp(xn, xo, data[:, 0]),
                             np.interp(xn, xo, data[:, 1])], axis=1)
        else:
            data = np.interp(xn, xo, data)
            data = np.stack([data, data], axis=1)
    if len(data.shape) == 1:
        data = np.stack([data, data], axis=1)

    out = np.zeros_like(data)
    hp = butter(2, HIGH_PASS, btype="highpass", fs=48000, output="sos")
    lp = butter(4, LOW_PASS, btype="lowpass", fs=48000, output="sos")
    for ch in range(2):
        x = sosfiltfilt(hp, data[:, ch])
        x = sosfiltfilt(lp, x)
        out[:, ch] = x
    return out


def fade(data, seconds):
    out = data.copy()
    n = int(48000 * seconds)
    for i in range(n):
        out[i] *= i / n
        out[len(out) - 1 - i] *= i / n
    return out


os.makedirs(OUT, exist_ok=True)

for path in sorted(glob.glob(os.path.join(SRC, "*.wav"))):
    name = os.path.basename(path)
    data, sr = sf.read(path, dtype="float64")
    data = clean(data, sr)

    data = fade(data, 2.0)

    rms = np.sqrt(np.mean(data ** 2))
    if rms > 0:
        data = data * (TARGET_RMS / rms)
    # 软限幅：只压特别尖的那几个点，不把整体音量拉下来
    data = np.tanh(data / SOFT_LIMIT) * SOFT_LIMIT
    peak = np.max(np.abs(data))
    if peak > MAX_PEAK:
        data = data * (MAX_PEAK / peak)

    out_path = os.path.join(OUT, name.replace(".wav", "_安静版.wav"))
    sf.write(out_path, data, 48000, subtype="PCM_24")

    rms2 = np.sqrt(np.mean(data ** 2))
    peak2 = np.max(np.abs(data))
    print("导出：" + os.path.basename(out_path))
    print("   RMS=%.4f 峰值=%.4f（原来峰值约 0.9，现在降到 0.1 以下）"
          % (rms2, peak2))

print("\n完成，安静版在 " + OUT + "/")
