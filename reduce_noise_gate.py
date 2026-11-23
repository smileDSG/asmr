# 只压真实感这段的底噪，保住雨滴颗粒
# 方法：频谱门 spectral gate
# 每个频率单独估计"稳态底噪"(=第20百分位)，只衰减贴近底噪的部分
# 雨滴是瞬间高峰值，会超过阈值，所以原样保留
#
# 关键参数：
#   N_FLOOR：底噪压多少 dB（太小没效果，太大有水声伪影）
#   只用温和的 4-6 dB，宁可底噪剩一点，也不能毁掉真实感

import soundfile as sf
import numpy as np

PATH = "E:/03_Projects/asmr/rain_candidates_v2/新候选4_窗边雨3_真实感.wav"
OUT = "E:/03_Projects/asmr/rain_candidates_v2/新候选4_真实感_去底噪.wav"

data, sr = sf.read(PATH, dtype="float64")
if len(data.shape) > 1:
    mono = data.mean(axis=1)
else:
    mono = data

win = 2048
hop = 512
N_FLOOR = 5.0      # dB，最多压 5 dB，保守
FLOOR_PERCENTILE = 25

# 第一遍：估计每个频率的稳态底噪
mags = []
for i in range(0, len(mono) - win, hop):
    seg = mono[i:i + win] * np.hanning(win)
    mags.append(np.abs(np.fft.rfft(seg)))
mags = np.array(mags)
noise_profile = np.percentile(mags, FLOOR_PERCENTILE, axis=0)

# 第二遍：逐帧处理
out = np.zeros(len(mono))
weight = np.zeros(len(mono))
window = np.hanning(win)

for i in range(0, len(mono) - win, hop):
    seg = mono[i:i + win]
    spec = np.fft.rfft(seg * window)
    mag = np.abs(spec)

    # 这一帧比底噪高多少 dB
    excess_db = 20 * np.log10(mag + 1e-10) - 20 * np.log10(noise_profile + 1e-10)

    # 增益：贴近底噪(<3dB)的压 N_FLOOR dB；超过 12dB 的(雨滴)完全不动
    gain = np.clip((excess_db - 3.0) / 9.0, 0.0, 1.0)
    gain = 1.0 - (1.0 - gain) * (1.0 - 10 ** (-N_FLOOR / 20.0))

    spec = spec * gain
    reconstructed = np.fft.irfft(spec, n=win) * window
    out[i:i + win] += reconstructed
    weight[i:i + win] += window ** 2

# 重叠相加归一化
mask = weight > 1e-8
out[mask] = out[mask] / weight[mask]
out = out[:len(mono)]

if len(data.shape) > 1:
    # 左右声道用同一个增益曲线，保持立体声结构
    stereo = np.zeros_like(data)
    for ch in range(data.shape[1]):
        scale = np.sqrt(np.mean(data[:, ch] ** 2)) / (np.sqrt(np.mean(mono ** 2)) + 1e-9)
        stereo[:, ch] = out * scale
    result = stereo
else:
    result = out

# 电平对齐到原来
rms_before = np.sqrt(np.mean(mono ** 2))
rms_after = np.sqrt(np.mean(result ** 2))
if rms_after > 0:
    result = result * (rms_before / rms_after)

sf.write(OUT, result, sr, subtype="PCM_24")
print("导出：" + OUT)
print("底噪最多压 " + str(N_FLOOR) + " dB，雨滴峰值保留")

# 验证：底噪占比变化
def noise_ratio(x):
    if len(x.shape) > 1:
        x = x.mean(axis=1)
    m = np.array([np.abs(np.fft.rfft(x[i:i + win] * np.hanning(win)))
                  for i in range(0, len(x) - win, hop)])
    nf = np.percentile(m, 20, axis=0)
    return nf.sum() / np.mean(m, axis=0).sum() * 100

print("底噪占比：%.1f%% -> %.1f%%" % (noise_ratio(mono), noise_ratio(result)))
