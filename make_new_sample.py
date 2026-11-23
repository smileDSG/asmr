# 用新下的 Freesound CC0 素材做一版对比样品
# 挑逻辑：从诊断结果里选瞬态密度低、高频嘶声少、有低频厚度的
# 目标：证明"换素材"比"调参数"更有效

import soundfile as sf
import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve
from scipy import ndimage
import os

RATE = 48000
OUT = "freesound_previews"
DURATION = 30

# 从诊断结果挑的：
# rain_0: 瞬态 1.2/秒（很低），厚度 16.5%，嘶声 6.4%
# heavyrain_1: 瞬态 0.1/秒（极低），暖度 25.1%，嘶声 6.5%
# rain_3: 瞬态 1.1/秒，厚度 6.6%
# windowrain 待诊断后补充
PICKS = ["rain_0.mp3", "heavyrain_1.mp3", "rain_3.mp3"]


def read_any(path):
    data, sr = sf.read(path, dtype="float64")
    if len(data.shape) == 1:
        data = np.stack([data, data], axis=1)
    if sr != RATE:
        old_n = data.shape[0]
        new_n = int(old_n * RATE / sr)
        xo = np.linspace(0, old_n - 1, old_n)
        xn = np.linspace(0, old_n - 1, new_n)
        data = np.stack([np.interp(xn, xo, data[:, 0]),
                         np.interp(xn, xo, data[:, 1])], axis=1)
    return data


def filt(data, hp=None, lp=None):
    out = np.zeros_like(data)
    for ch in range(2):
        x = data[:, ch]
        if hp:
            x = sosfiltfilt(butter(2, hp, btype="highpass", fs=RATE, output="sos"), x)
        if lp:
            x = sosfiltfilt(butter(4, lp, btype="lowpass", fs=RATE, output="sos"), x)
        out[:, ch] = x
    return out


def norm(data, target):
    rms = np.sqrt(np.mean(data ** 2))
    return data * (target / rms) if rms > 0 else data


def process():
    size = int(DURATION * RATE)
    mix = np.zeros((size, 2))

    # 角色分层：一个做厚底，一个做主体沙沙，一个补细节
    roles = [
        ("rain_0.mp3", 5000, 0.030),        # 厚底
        ("heavyrain_1.mp3", 6000, 0.022),   # 主体
        ("rain_3.mp3", 4500, 0.012),        # 细节
    ]
    for name, lp, level in roles:
        path = os.path.join(OUT, name)
        if not os.path.exists(path):
            continue
        data = read_any(path)[:size]
        layer = filt(data, hp=65, lp=lp)
        layer = norm(layer, level)
        mix = mix + layer
        print("  加入 " + name + "  低通 " + str(lp) + "Hz  电平 " + str(level))

    # 空间感
    n = int(RATE * 1.0)
    t = np.arange(n) / RATE
    ir = np.random.randn(n) * np.exp(-t * 5.5)
    for ch in range(2):
        dry = mix[:, ch]
        tail = fftconvolve(dry, ir)[:len(dry)]
        tail = norm(tail, np.sqrt(np.mean(dry ** 2)))
        mix[:, ch] = dry * 0.82 + tail * 0.18

    # 慢起伏 + 压缩 + 软限幅
    tt = np.arange(size) / RATE
    wander = (1.0 + 0.16 * (0.5 * np.sin(2 * np.pi * tt / 23 + 0.3)
                            + 0.3 * np.sin(2 * np.pi * tt / 37 + 1.7)
                            + 0.2 * np.sin(2 * np.pi * tt / 61 + 2.5)))
    mix = mix * wander[:, None]

    for ch in range(2):
        x = mix[:, ch]
        env = ndimage.uniform_filter1d(x ** 2, int(0.1 * RATE), mode="nearest") ** 0.5
        gain = np.ones_like(env)
        above = env > 0.030
        gain[above] = (0.030 / env[above]) ** (1 - 1.0 / 3.0)
        mix[:, ch] = x * gain

    mix = np.tanh(mix / 0.075) * 0.075

    # 淡入淡出
    fi, fo = int(RATE * 4), int(RATE * 8)
    for i in range(fi):
        mix[i] *= i / fi
    for i in range(fo):
        mix[size - 1 - i] *= i / fo

    mix = norm(mix, 0.050)
    peak = np.max(np.abs(mix))
    if peak > 0.22:
        mix = mix * (0.22 / peak)

    path = "freesound_previews/sample_new_sources.wav"
    sf.write(path, mix, RATE, subtype="PCM_24")
    rms = np.sqrt(np.mean(mix ** 2))
    peak = np.max(np.abs(mix))
    print("\n成品：" + path)
    print("RMS=%.4f 峰值=%.4f 峰均比=%.1f" % (rms, peak, peak / rms))


print("用 Freesound CC0 新素材制作样品")
process()
