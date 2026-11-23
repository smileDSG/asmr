# 极简导出：原始雨声素材，只做淡入淡出，不加任何处理
# 目的：让用户用耳朵挑出"真正像下雨"的那段，再由用户决定怎么处理
# 不做滤波、不做混响、不做压缩、不做叠加——之前就是做多了才变成噪音

import soundfile as sf
import numpy as np
import os

SRC = "freesound_previews"
OUT = "rain_candidates"
DURATION = 20

# 挑的候选：瞬态适中（有雨滴感）、嘶声不过分、不是纯噪声或隆隆声
CANDIDATES = [
    ("rain_0.mp3", "候选1_rain0_绵密型"),
    ("rain_3.mp3", "候选2_rain3_轻柔型"),
    ("windowrain_1.mp3", "候选3_窗边雨1_平稳型"),
    ("windowrain_3.mp3", "候选4_窗边雨3_有雨滴型"),
    ("heavyrain_5.mp3", "候选5_大雨5_厚实型"),
    ("windrain_3.mp3", "候选6_风雨3_低沉型"),
]


def simple_fade(data, sr, fade_sec):
    out = data.copy()
    n = int(sr * fade_sec)
    for i in range(min(n, len(out) // 4)):
        out[i] *= i / n
        out[len(out) - 1 - i] *= i / n
    return out


os.makedirs(OUT, exist_ok=True)

for filename, label in CANDIDATES:
    path = os.path.join(SRC, filename)
    if not os.path.exists(path):
        print("跳过（不存在）：" + filename)
        continue
    data, sr = sf.read(path, dtype="float64")
    # 取中间一段，避开开头可能的杂音
    start = int(len(data) * 0.2)
    take = data[start:start + int(DURATION * sr)]
    if len(take) < int(DURATION * sr):
        continue
    take = simple_fade(take, sr, 1.5)
    # 只做最基本的响度对齐，不改音色
    rms = np.sqrt(np.mean(take ** 2))
    if rms > 0:
        take = take * (0.12 / rms)
    out_path = os.path.join(OUT, label + ".wav")
    sf.write(out_path, take, sr, subtype="PCM_24")
    print("导出：" + label + ".wav（原始素材，仅淡入淡出）")

print("\n完成，文件在 " + OUT + "/")
