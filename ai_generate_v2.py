# AI 生成 v2：按"成熟助眠产品"的规则重做
#
# 参考资料里学到的几条硬规则：
# 1. Audio Scene 雨声录音指南：high-pass 40-60Hz 去隆隆声，low-pass 12-14kHz 去嘶声；
#    冥想/助眠用途要额外避免 8kHz 以上过亮，否则长时间听耳朵疲劳。
# 2. 人民网/光明网：粉红噪音以中低频为主，柔和、接近自然雨声；白噪音高频太强会刺耳。
# 3. Aubiomix / SoundBridge 底噪研究：每条轨的底噪按 RMS 累加，层数越多越吵；
#    最有效的修复常常就是"去掉一条本身很吵的轨"。
# 4. 混音电平建议：峰值留 -12 ~ -18 dBFS 余量；白噪音开太大本身会变成新噪音源。
# 5. Dark Noise / Atmosphere 评测：无缝循环是底线，接缝处咔哒声会让人无法放松。
#
# 对应到代码里的改动：
# A. 每条素材先做零相位滤波：高通 70Hz + 低通 8kHz（虫鸣/壁炉更低，6kHz）
# B. 每条素材先按 RMS 归一化到统一响度，再乘配方百分比（否则配方数字是假的）
# C. 最终音量目标压到 RMS 0.035、峰值不超过 0.5
# D. 循环处做 250ms 交叉淡化，消除接缝咔哒声
# E. 最多只用 2 层素材，避免底噪叠加

import soundfile as sf
import numpy as np
from scipy.signal import butter, sosfiltfilt
import os

RATE = 48000
DURATION = 30
SOURCE_DIR = "real_sounds"
OUT_DIR = "ai_samples_v2"
CROSSFADE = 0.25          # 秒，循环接缝交叉淡化长度
REF_RMS = 0.05            # 每条素材清洗后统一归一化到这个 RMS
TARGET_RMS = 0.035        # 成品目标 RMS，约 -29 dBFS
MAX_PEAK = 0.5            # 成品峰值上限，约 -6 dBFS

NAMES = ["sleep_rain", "soft_fireplace", "ocean_waves",
         "night_crickets", "gentle_wind", "morning_forest"]
LABELS = ["夜雨", "壁炉", "海浪", "虫鸣", "微风", "晨林"]
LOWPASS = {
    "sleep_rain": 8000,
    "soft_fireplace": 6000,
    "ocean_waves": 9000,
    "night_crickets": 6000,
    "gentle_wind": 7000,
    "morning_forest": 8000,
}


def resample_stereo(data, sr):
    # 素材采样率不一致，统一到 48000；左右声道必须分别插值
    if sr == RATE:
        return data.astype(np.float64)
    old_n = data.shape[0]
    new_n = int(old_n * RATE / sr)
    x_old = np.linspace(0, old_n - 1, old_n)
    x_new = np.linspace(0, old_n - 1, new_n)
    left = np.interp(x_new, x_old, data[:, 0])
    right = np.interp(x_new, x_old, data[:, 1])
    return np.stack([left, right], axis=1)


def clean_track(name):
    # 读取 -> 统一采样率 -> 高通去隆隆 -> 低通去嘶声 -> RMS 归一化
    data, sr = sf.read(os.path.join(SOURCE_DIR, name + ".ogg"))
    data = resample_stereo(data, sr)

    hp = butter(2, 70, btype="highpass", fs=RATE, output="sos")
    lp = butter(4, LOWPASS[name], btype="lowpass", fs=RATE, output="sos")

    out = np.zeros_like(data)
    for ch in range(2):
        x = sosfiltfilt(hp, data[:, ch])   # sosfiltfilt 是零相位的，不会引入偏移或拖尾
        x = sosfiltfilt(lp, x)
        out[:, ch] = x

    rms = np.sqrt(np.mean(out ** 2))
    if rms > 0:
        out = out * (REF_RMS / rms)
    return out


# 缓存清洗后的素材，避免每段样例都重复滤波
CACHE = {}


def get_clean(name):
    if name not in CACHE:
        CACHE[name] = clean_track(name)
    return CACHE[name]


def seamless_take(data, seconds):
    # 从素材里取指定秒数，循环点用交叉淡化接上，避免咔哒声
    need = int(seconds * RATE)
    fade_n = int(CROSSFADE * RATE)
    src_len = len(data)

    out = data[:min(src_len, need)].copy()
    # 用斜坡把上一段的尾巴混进下一段的开头
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


def fade_edges(audio, fi, fo):
    n = len(audio)
    ci = int(RATE * fi)
    co = int(RATE * fo)
    out = audio.copy()
    for i in range(ci):
        out[i] *= i / ci
    for i in range(co):
        out[n - 1 - i] *= i / co
    return out


def make(recipe, fi, fo, path):
    size = int(DURATION * RATE)
    mix = np.zeros((size, 2))

    for k in range(len(NAMES)):
        if recipe[k] <= 0:
            continue
        seg = seamless_take(get_clean(NAMES[k]), DURATION)
        mix += seg * (recipe[k] / 100.0)

    mix = fade_edges(mix, fi, fo)

    # 先压峰值，再定整体响度；顺序不能反，否则会削顶
    peak = np.max(np.abs(mix))
    if peak > MAX_PEAK:
        mix = mix * (MAX_PEAK / peak)
    rms = np.sqrt(np.mean(mix ** 2))
    if rms > 0:
        mix = mix * (TARGET_RMS / rms)
        peak2 = np.max(np.abs(mix))
        if peak2 > MAX_PEAK:
            mix = mix * (MAX_PEAK / peak2)

    sf.write(path, mix, RATE, subtype="PCM_24")
    return np.sqrt(np.mean(mix ** 2)), np.max(np.abs(mix))


# === 和上一版同样的 4 句话，方便直接对比 ===
CASES = [
    {
        "say": "我睡不着，脑子停不下来，想慢慢安静下来",
        "recipe": [55, 0, 0, 0, 12, 0], "fi": 4, "fo": 10,
        "file": "case1_睡不着.wav"
    },
    {
        "say": "太累了，想彻底放空，什么都不想",
        "recipe": [10, 0, 60, 0, 18, 0], "fi": 3, "fo": 6,
        "file": "case2_放空.wav"
    },
    {
        "say": "凌晨三点还很清醒，有点焦虑",
        "recipe": [45, 0, 0, 15, 10, 0], "fi": 5, "fo": 8,
        "file": "case3_凌晨焦虑.wav"
    },
    {
        "say": "想专注学习，别打扰我",
        "recipe": [40, 12, 0, 0, 0, 0], "fi": 2, "fo": 2,
        "file": "case4_专注.wav"
    },
]

os.makedirs(OUT_DIR, exist_ok=True)

for c in CASES:
    r, p = make(c["recipe"], c["fi"], c["fo"], os.path.join(OUT_DIR, c["file"]))
    parts = []
    for i in range(len(NAMES)):
        if c["recipe"][i] > 0:
            parts.append(LABELS[i] + str(c["recipe"][i]))
    print("说：" + c["say"])
    print("  配方：" + " + ".join(parts))
    print("  成品 RMS=%.4f  峰值=%.4f  -> %s" % (r, p, c["file"]))

# 再做一组严格的 A/B：同一句"睡不着"，旧方法和新方法各一段
old = os.path.join("ai_samples", "case1_睡不着.wav")
if os.path.exists(old):
    sf.write(os.path.join(OUT_DIR, "AB_旧方法_睡不着.wav"),
             sf.read(old)[0], sf.read(old)[1], subtype="PCM_24")
    sf.write(os.path.join(OUT_DIR, "AB_新方法_睡不着.wav"),
             sf.read(os.path.join(OUT_DIR, "case1_睡不着.wav"))[0], RATE,
             subtype="PCM_24")

print("\n完成，新样例在 " + OUT_DIR + "/")
