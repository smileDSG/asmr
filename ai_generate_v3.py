# AI 生成 v3：按"稳"和"暖"重做，从频段叠加改成角色分层
#
# v2 的错：把每条素材 RMS 归一化到同一个值，再按百分比叠加。
# 教程原话："所有声音一样大，听起来像噪音——要像调鸡尾酒，每种声音有自己的角色。"
#
# v3 的四层角色（来自 B站/抖音高播放视频的声音结构 + 用户自己的描述）：
#   1. 底层毯子：粉红噪音做的连绵雨幕，温暖、连续、负责掩蔽环境噪音
#   2. 中层闷响：雨声素材低通到 3kHz，模拟帆布/树叶吸收冲击后的"闷响"，有厚度
#   3. 顶层沙沙：很轻的高频细节，像一层薄纱，不能抢戏
#   4. 空间感：小房间混响，Wet 15-25%，让声音"从远处传来，不贴脸"
#
# 另外两件事：
#   - 慢速随机起伏（周期 20-60 秒叠加），替代机械循环
#   - 轻压缩把峰均比从 8 倍压到约 4 倍，对应"稳、动态范围小"

import soundfile as sf
import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve
from scipy import ndimage
import os

RATE = 48000
DURATION = 30
SOURCE_DIR = "real_sounds"
OUT_DIR = "ai_samples_v3"
CROSSFADE = 0.25
TARGET_RMS = 0.050     # 约 -26 dBFS，比 v2 更响一点但峰值更低 = 动态范围更小
MAX_PEAK = 0.22        # 约 -13 dBFS


def resample_stereo(data, sr):
    if sr == RATE:
        return data.astype(np.float64)
    old_n = data.shape[0]
    new_n = int(old_n * RATE / sr)
    x_old = np.linspace(0, old_n - 1, old_n)
    x_new = np.linspace(0, old_n - 1, new_n)
    return np.stack([np.interp(x_new, x_old, data[:, 0]),
                     np.interp(x_new, x_old, data[:, 1])], axis=1)


def load_source(name):
    data, sr = sf.read(os.path.join(SOURCE_DIR, name + ".ogg"))
    return resample_stereo(data, sr)


def filter_stereo(data, highpass=None, lowpass=None):
    out = np.zeros_like(data)
    for ch in range(2):
        x = data[:, ch]
        if highpass:
            sos = butter(2, highpass, btype="highpass", fs=RATE, output="sos")
            x = sosfiltfilt(sos, x)
        if lowpass:
            sos = butter(4, lowpass, btype="lowpass", fs=RATE, output="sos")
            x = sosfiltfilt(sos, x)
        out[:, ch] = x
    return out


def normalize_rms(data, target):
    rms = np.sqrt(np.mean(data ** 2))
    if rms > 0:
        return data * (target / rms)
    return data


def seamless_take(data, seconds):
    need = int(seconds * RATE)
    fade_n = int(CROSSFADE * RATE)
    src_len = len(data)
    out = data[:min(src_len, need)].copy()
    ramp = np.linspace(0, 1, fade_n)

    while len(out) < need + fade_n:
        start = len(out) - fade_n
        head = data[:fade_n]
        for ch in range(2):
            out[start:start + fade_n, ch] = (
                out[start:start + fade_n, ch] * (1 - ramp) + head[:, ch] * ramp
            )
        out = np.concatenate([out, data[fade_n:]], axis=0)
    return out[:need]


def pink_noise(n):
    # 标准粉红噪音：白噪音频谱乘 1/sqrt(f)，能量随频率升高而下降
    white = np.random.randn(n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    gain = np.ones_like(freqs)
    gain[1:] = 1.0 / np.sqrt(freqs[1:])
    spec = spec * gain
    out = np.fft.irfft(spec, n)
    return out


def make_reverb(seconds, decay):
    # 用指数衰减的噪声当脉冲响应，做出小房间的柔和混响
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    ir = np.random.randn(n) * np.exp(-t * decay)
    return ir


def apply_reverb(data, wet, pre_delay_ms):
    ir = make_reverb(1.2, 5.0)
    delay = int(pre_delay_ms * RATE / 1000)
    out = np.zeros_like(data)
    for ch in range(2):
        dry = data[:, ch]
        tail = fftconvolve(dry, ir)[:len(dry)]
        tail = np.concatenate([np.zeros(delay), tail[:len(dry) - delay]])
        out[:, ch] = dry * (1 - wet) + normalize_rms(tail, np.sqrt(np.mean(dry ** 2))) * wet
    return out


def slow_wander(n, depth):
    # 三个互质的慢周期叠加，听起来像自然起伏而不是机械循环
    t = np.arange(n) / RATE
    w = (0.50 * np.sin(2 * np.pi * t / 23.0 + 0.3)
         + 0.30 * np.sin(2 * np.pi * t / 37.0 + 1.7)
         + 0.20 * np.sin(2 * np.pi * t / 61.0 + 2.5))
    return 1.0 + depth * w


def gentle_compress(data, threshold, ratio):
    # 100ms 滑动 RMS 当包络，超过阈值的地方按 ratio 压下去
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


# 素材只加载一次
RAW_RAIN = load_source("sleep_rain")
RAW_WIND = load_source("gentle_wind")
RAW_OCEAN = load_source("ocean_waves")

# 三层角色：各自的滤波和响度都不同，不再是"所有声音一样大"
# 底层毯子：粉红噪音，做成双声道略微不同，宽一点
bed_l = normalize_rms(filter_stereo(
    np.stack([pink_noise(int(DURATION * RATE)), pink_noise(int(DURATION * RATE))], axis=1),
    highpass=60, lowpass=1800), 0.030)

# 中层闷响：雨声砍到 3kHz 以下，帆布/树叶吸掉尖锐冲击
thud = normalize_rms(seamless_take(filter_stereo(RAW_RAIN, highpass=70, lowpass=3000),
                                   DURATION), 0.045)

# 顶层沙沙：雨声 2-6kHz 的一小条，只做点缀
sand_full = filter_stereo(RAW_RAIN, highpass=2000, lowpass=6000)
sand = normalize_rms(seamless_take(sand_full, DURATION), 0.012)

# 微风：极低频厚度，只给一点点
wind = normalize_rms(seamless_take(filter_stereo(RAW_WIND, highpass=60, lowpass=500),
                                   DURATION), 0.010)


def make(recipe, fi, fo, path):
    # recipe 顺序：毯子, 闷响, 沙沙, 微风, 空间, 起伏
    bed_a, thud_a, sand_a, wind_a, space, wander = recipe
    size = int(DURATION * RATE)

    mix = np.zeros((size, 2))
    mix += bed_l * bed_a
    mix += thud * thud_a
    mix += sand * sand_a
    mix += wind * wind_a

    # 空间感：wet 按配方给，pre-delay 30ms 让声音往后退
    if space > 0:
        mix = apply_reverb(mix, wet=space, pre_delay_ms=30)

    # 自然起伏：只调制整体音量，不改变音色
    mix = mix * slow_wander(size, wander)[:, None]

    # "稳"：轻压缩管慢起伏，软限幅管单个雨滴尖峰
    mix = gentle_compress(mix, threshold=0.030, ratio=3.0)
    mix = np.tanh(mix / 0.075) * 0.075
    mix = fade_edges(mix, fi, fo)

    # 最终电平：先定 RMS，再压峰值
    rms = np.sqrt(np.mean(mix ** 2))
    if rms > 0:
        mix = mix * (TARGET_RMS / rms)
    peak = np.max(np.abs(mix))
    if peak > MAX_PEAK:
        mix = mix * (MAX_PEAK / peak)

    sf.write(path, mix, RATE, subtype="PCM_24")
    return np.sqrt(np.mean(mix ** 2)), np.max(np.abs(mix))


# 和前两版同样的四句话，方便横着比
CASES = [
    {
        "say": "我睡不着，脑子停不下来，想慢慢安静下来",
        "why": "厚毯子 + 闷响雨声，沙沙只留一点，空间感中等，起伏明显",
        "recipe": [1.0, 1.0, 0.5, 0.4, 0.18, 0.16], "fi": 5, "fo": 10,
        "file": "case1_睡不着.wav"
    },
    {
        "say": "太累了，想彻底放空，什么都不想",
        "why": "毯子为主，闷响减半，海浪的低频慢慢托着，起伏更缓",
        "recipe": [1.2, 0.6, 0.3, 0.5, 0.22, 0.20], "fi": 4, "fo": 8,
        "file": "case2_放空.wav"
    },
    {
        "say": "凌晨三点还很清醒，有点焦虑",
        "why": "整体压暗，沙沙几乎去掉，空间更深，起伏更慢",
        "recipe": [1.0, 0.8, 0.2, 0.3, 0.25, 0.12], "fi": 6, "fo": 10,
        "file": "case3_凌晨焦虑.wav"
    },
    {
        "say": "想专注学习，别打扰我",
        "why": "平坦稳定优先，起伏和空间都调小，闷响做底",
        "recipe": [0.9, 1.0, 0.6, 0.2, 0.10, 0.06], "fi": 2, "fo": 2,
        "file": "case4_专注.wav"
    },
]

os.makedirs(OUT_DIR, exist_ok=True)

for c in CASES:
    r, p = make(c["recipe"], c["fi"], c["fo"], os.path.join(OUT_DIR, c["file"]))
    print("说：" + c["say"])
    print("  " + c["why"])
    print("  成品 RMS=%.4f 峰值=%.4f 峰均比=%.1f  -> %s"
          % (r, p, p / r, c["file"]))

print("\n完成，新样例在 " + OUT_DIR + "/")
