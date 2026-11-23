# 回退到真正的雨声
# 承认错误：频谱门把雨声变成了流水声，这次不用它
#
# 只做最保守的三件事：
# 1. 砍 90Hz 以下隆隆（这个不会改变雨声性质）
# 2. 音量降到睡前舒适水平
# 3. 完全不碰中频（250-1000Hz 是雨声主体，之前压它就是出错的根源）
#
# 素材本身：windowrain_3 = Freesound "Rain balcony window perspective"（阳台窗边雨）

import soundfile as sf
import numpy as np
from scipy.signal import butter, sosfiltfilt

SRC = "E:/03_Projects/asmr/rain_candidates_v2/新候选4_窗边雨3_真实感.wav"
OUT = "E:/03_Projects/asmr/rain_candidates_v2/真实感_回退_纯雨声.wav"

d, sr = sf.read(SRC, dtype="float64")
if len(d.shape) > 1:
    m = d.mean(axis=1)
else:
    m = d

# 只砍次声隆隆，不动别的
hp = butter(2, 85, btype="highpass", fs=sr, output="sos")
m = sosfiltfilt(hp, m)

# 淡入淡出
n = int(sr * 2)
for i in range(n):
    m[i] *= i / n
    m[len(m) - 1 - i] *= i / n

# 舒服的音量
rms = np.sqrt(np.mean(m ** 2))
if rms > 0:
    m = m * (0.020 / rms)
peak = np.max(np.abs(m))
if peak > 0.08:
    m = m * (0.08 / peak)

# 转成立体声（用极轻微的左右差异，不破坏雨声）
left = m.copy()
right = np.roll(m, int(sr * 0.003))  # 3毫秒差异，制造空间感
result = np.stack([left, right], axis=1)

sf.write(OUT, result, sr, subtype="PCM_24")
print("导出：" + OUT)
print("RMS=%.4f 峰值=%.3f" % (np.sqrt(np.mean(result ** 2)), np.max(np.abs(result))))

# 验证：瞬态和频段没被破坏
j = np.abs(np.diff(m[:sr * 10]))
med = np.median(j) + 1e-9
print("雨滴颗粒：%.1f 个/秒（Rainy Mood 是 19.6）" % (np.sum(j > med * 8) / 10))
