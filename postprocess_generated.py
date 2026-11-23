# 对生成好的母带做助眠后处理
# 输入：ElevenLabs 生成的 30 秒音频（mp3 或 wav）
# 输出：暖、稳、能听一整晚的成品 wav
#
# 思路来自学到的分层原则：不再从现成素材拼，而是把生成结果本身拆层再平衡
# 1. 高通去隆隆 + 低通去嘶声（暖）
# 2. 从母带里复制一条低通版本叠回去，补"闷响厚度"（不是加新素材）
# 3. 从母带里取 2-6kHz 窄带做极轻沙沙点缀
# 4. 小房间混响 + 慢起伏 + 压缩软限幅（稳）

import soundfile as sf
import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve
from scipy import ndimage

RATE = 48000
CROSSFADE = 0.25
MAX_PEAK = 0.22


def read_any(path):
    # soundfile 能直接读 mp3 和 wav
    data, sr = sf.read(path, dtype="float64")
    return data, sr


def resample_stereo(data, sr):
    if sr == RATE:
        if len(data.shape) == 1:
            return np.stack([data, data], axis=1)
        return data
    if len(data.shape) == 1:
        data = np.stack([data, data], axis=1)
    old_n = data.shape[0]
    new_n = int(old_n * RATE / sr)
    x_old = np.linspace(0, old_n - 1, old_n)
    x_new = np.linspace(0, old_n - 1, new_n)
    left = np.interp(x_new, x_old, data[:, 0])
    right = np.interp(x_new, x_old, data[:, 1])
    return np.stack([left, right], axis=1)


def fit_length(data, seconds):
    need = int(seconds * RATE)
    if len(data) >= need:
        return data[:need].copy()
    # 不够长就循环补，接缝做短交叉淡化
    out = data.copy()
    fade_n = min(int(CROSSFADE * RATE), len(data) // 4)
    ramp = np.linspace(0, 1, fade_n)
    while len(out) < need:
        start = len(out) - fade_n
        head = data[:fade_n]
        for ch in range(2):
            out[start:start + fade_n, ch] = (
                out[start:start + fade_n, ch] * (1 - ramp) + head[:, ch] * ramp
            )
        out = np.concatenate([out, data[fade_n:]], axis=0)
    return out[:need]


def filt(data, highpass=None, lowpass=None, order=4):
    out = np.zeros_like(data)
    for ch in range(2):
        x = data[:, ch]
        if highpass:
            sos = butter(2, highpass, btype="highpass", fs=RATE, output="sos")
            x = sosfiltfilt(sos, x)
        if lowpass:
            sos = butter(order, lowpass, btype="lowpass", fs=RATE, output="sos")
            x = sosfiltfilt(sos, x)
        out[:, ch] = x
    return out


def norm_rms(data, target):
    rms = np.sqrt(np.mean(data ** 2))
    if rms > 0:
        return data * (target / rms)
    return data


def make_reverb(seconds, decay):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    return np.random.randn(n) * np.exp(-t * decay)


def apply_reverb(data, wet, pre_delay_ms):
    ir = make_reverb(1.0, 5.5)
    delay = int(pre_delay_ms * RATE / 1000)
    out = np.zeros_like(data)
    for ch in range(2):
        dry = data[:, ch]
        tail = fftconvolve(dry, ir)[:len(dry)]
        tail = np.concatenate([np.zeros(delay), tail[:len(dry) - delay]])
        tail = norm_rms(tail, np.sqrt(np.mean(dry ** 2)))
        out[:, ch] = dry * (1 - wet) + tail * wet
    return out


def slow_wander(n, depth):
    t = np.arange(n) / RATE
    w = (0.50 * np.sin(2 * np.pi * t / 23.0 + 0.3)
         + 0.30 * np.sin(2 * np.pi * t / 37.0 + 1.7)
         + 0.20 * np.sin(2 * np.pi * t / 61.0 + 2.5))
    return 1.0 + depth * w


def compress(data, threshold, ratio):
    out = np.zeros_like(data)
    for ch in range(2):
        x = data[:, ch]
        env = ndimage.uniform_filter1d(x ** 2, int(0.1 * RATE), mode="nearest") ** 0.5
        gain = np.ones_like(env)
        above = env > threshold
        gain[above] = (threshold / env[above]) ** (1 - 1.0 / ratio)
        out[:, ch] = x * gain
    return out


def fade_edges(audio, fi, fo):
    n = len(audio)
    ci, co = int(RATE * fi), int(RATE * fo)
    out = audio.copy()
    for i in range(ci):
        out[i] *= i / ci
    for i in range(co):
        out[n - 1 - i] *= i / co
    return out


def process(input_path, output_path, config, seconds=30):
    p = config["post"]
    raw, sr = read_any(input_path)
    data = fit_length(resample_stereo(raw, sr), seconds)

    # 第 1 步：暖化，砍掉刺耳高频和隆隆低频
    base = filt(data, highpass=65, lowpass=p["lowpass"])

    # 第 2 步：闷响厚度，从母带本身取低频再叠回去
    thud = filt(data, highpass=110, lowpass=1800)
    thud = norm_rms(thud, np.sqrt(np.mean(base ** 2)))
    base = base + thud * p["thud"]

    # 第 3 步：极轻沙沙点缀，只取一条很窄的高频带
    if p["sand"] > 0:
        sand = filt(data, highpass=2200, lowpass=min(6000, p["lowpass"]), order=2)
        sand = norm_rms(sand, np.sqrt(np.mean(base ** 2)))
        base = base + sand * p["sand"]

    # 第 4 步：空间感
    if p["reverb"] > 0:
        base = apply_reverb(base, wet=p["reverb"], pre_delay_ms=30)

    # 第 5 步：自然起伏
    base = base * slow_wander(len(base), p["wander"])[:, None]

    # 第 6 步：稳，压缩 + 软限幅
    base = compress(base, threshold=0.030, ratio=p["compress"])
    base = np.tanh(base / 0.075) * 0.075
    base = fade_edges(base, fi=4, fo=8)

    # 第 7 步：最终电平
    base = norm_rms(base, config["target_rms"])
    peak = np.max(np.abs(base))
    if peak > MAX_PEAK:
        base = base * (MAX_PEAK / peak)

    sf.write(output_path, base, RATE, subtype="PCM_24")
    rms = np.sqrt(np.mean(base ** 2))
    peak = np.max(np.abs(base))
    print("  成品：" + output_path)
    print("  RMS=%.4f 峰值=%.4f 峰均比=%.1f" % (rms, peak, peak / rms))
    return output_path
