# AI 生成验证脚本
# 思路：用户说一句话 -> AI 翻译成配方 -> 用真音效合成
# 我现在扮演"AI 脑子"，把几句话翻译成下面的配方，验证这条路成不成立
# 用 default 环境运行，保留立体声、直接叠加、不加工（昨晚验证过最不挫的方式）

import soundfile as sf
import numpy as np
import os

RATE = 48000
DURATION = 30
SOUND_DIR = "real_sounds"
OUT_DIR = "ai_samples"

NAMES = ["sleep_rain", "soft_fireplace", "ocean_waves",
         "night_crickets", "gentle_wind", "morning_forest"]
LABELS = ["夜雨", "壁炉", "海浪", "虫鸣", "微风", "晨林"]


def load(name):
    data, sr = sf.read(os.path.join(SOUND_DIR, name + ".ogg"))
    if sr != RATE:
        n = int(data.shape[0] * RATE / sr)
        xo = np.linspace(0, data.shape[0] - 1, data.shape[0])
        xn = np.linspace(0, data.shape[0] - 1, n)
        left = np.interp(xn, xo, data[:, 0])
        right = np.interp(xn, xo, data[:, 1])
        data = np.stack([left, right], axis=1)
    return data


def take(data, seconds):
    need = int(seconds * RATE)
    long = np.tile(data, (int(need / len(data)) + 2, 1))
    return long[:need]


def fade(audio, fi, fo):
    n = len(audio)
    ci, co = int(RATE * fi), int(RATE * fo)
    out = audio.copy()
    for i in range(ci):
        out[i] = out[i] * i / ci
    for i in range(co):
        out[n - 1 - i] = out[n - 1 - i] * i / co
    return out


def make(recipe, fi, fo, path):
    size = int(DURATION * RATE)
    mix = np.zeros((size, 2))
    for k in range(len(NAMES)):
        if recipe[k] <= 0:
            continue
        seg = take(load(NAMES[k]), DURATION)
        mix += seg * (recipe[k] / 100.0)
    mix = fade(mix, fi, fo)
    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix * 0.85 / peak
    sf.write(path, mix, RATE)


# === 下面是"AI 把一句话翻译成配方"的结果 ===
# 每条：配方6个数字（夜雨/壁炉/海浪/虫鸣/微风/晨林），渐入秒数，渐弱秒数
CASES = [
    {
        "say": "我睡不着，脑子停不下来，想慢慢安静下来",
        "why": "均匀雨声盖住杂念，没有突兀声音；慢慢淡出把人带睡",
        "recipe": [55, 0, 0, 0, 12, 0], "fi": 4, "fo": 10,
        "file": "case1_睡不着.wav"
    },
    {
        "say": "太累了，想彻底放空，什么都不想",
        "why": "海浪起伏像呼吸，带一点微风，让人跟着慢下来",
        "recipe": [10, 0, 60, 0, 18, 0], "fi": 3, "fo": 6,
        "file": "case2_放空.wav"
    },
    {
        "say": "凌晨三点还很清醒，有点焦虑",
        "why": "夜雨打底很轻，一点虫鸣带出深夜感，音量压低不刺激",
        "recipe": [45, 0, 0, 15, 10, 0], "fi": 5, "fo": 8,
        "file": "case3_凌晨焦虑.wav"
    },
    {
        "say": "想专注学习，别打扰我",
        "why": "稳定雨声做背景掩蔽噪音，壁炉很弱只添一点温度，不抢注意力",
        "recipe": [40, 12, 0, 0, 0, 0], "fi": 2, "fo": 2,
        "file": "case4_专注.wav"
    },
]

for c in CASES:
    print("说：" + c["say"])
    print("  AI 理解：" + c["why"])
    parts = []
    for i in range(len(NAMES)):
        if c["recipe"][i] > 0:
            parts.append(LABELS[i] + str(c["recipe"][i]))
    print("  配方：" + " + ".join(parts))
    make(c["recipe"], c["fi"], c["fo"], os.path.join(OUT_DIR, c["file"]))
    print("  -> " + c["file"] + "\n")

print("完成，4 段都在 ai_samples/ 里")
