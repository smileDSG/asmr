# ASMR 混音器 · V3 降噪版
# 针对 V2 "底噪太大"的问题：雨声改成柔和低通 + 噪声门 + 去掉翻书
# 只用 Python 自带模块
# 运行：python asmr_mixer_v3.py
# 成品：output_calm_v3.wav

import wave
import array
import math
import random

RATE = 22050
SECONDS = 20


# ============ 第 1 部分：合成音效 ============

def make_rain(seconds):
    # 关键改动：低通从 0.96 加强到 0.99，把刺耳的高频沙沙滤掉
    # 只留下柔和的低频"呼呼"声，底噪感会小很多
    out = []
    last = 0.0
    for i in range(seconds * RATE):
        white = random.uniform(-1, 1)
        last = last * 0.99 + white * 0.01
        out.append(last * 5)
    return out


def make_tapping(seconds):
    out = []
    period = int(RATE * 0.6)
    for i in range(seconds * RATE):
        t = i % period
        if t < 300:
            env = math.exp(-t / 60)
            value = math.sin(2 * math.pi * 180 * t / RATE) * env
        else:
            value = 0
        out.append(value * 0.7)
    return out


def make_bowl(seconds):
    out = []
    for i in range(seconds * RATE):
        t = i / RATE
        env = 0.6 + 0.4 * math.sin(2 * math.pi * 0.1 * t)
        value = math.sin(2 * math.pi * 110 * t) * 0.5
        value = value + math.sin(2 * math.pi * 165 * t) * 0.3
        value = value + math.sin(2 * math.pi * 220 * t) * 0.2
        out.append(value * env * 0.4)
    return out


# ============ 第 2 部分：读写 wav ============

def save_stereo(path, left, right):
    pcm = array.array('h')
    for i in range(len(left)):
        lv = int(max(-1, min(1, left[i])) * 32767)
        rv = int(max(-1, min(1, right[i])) * 32767)
        pcm.append(lv)
        pcm.append(rv)
    w = wave.open(path, 'wb')
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(pcm.tobytes())
    w.close()


# ============ 第 3 部分：降噪 + 分段配方 ============

def noise_gate(audio, threshold):
    # 噪声门：比阈值还小的声音直接变成 0
    # 敲击和颂钵之间的那些细微底噪，就被清掉了
    out = []
    for value in audio:
        if abs(value) < threshold:
            out.append(0.0)
        else:
            out.append(value)
    return out


# 每段各音效音量，顺序：雨声、轻敲、颂钵（翻书已去掉）
def stage_weights(t):
    if t < 0.2:
        return [0.05, 0.0, 0.50]
    elif t < 0.8:
        return [0.04, 0.55, 0.03]
    else:
        return [0.04, 0.0, 0.45]


def smooth_weights(t, seconds):
    # 段落交界处 1.5 秒平滑过渡
    w = stage_weights(t)
    fade = 1.5 / seconds
    for border in [0.2, 0.8]:
        if border - fade < t < border + fade:
            before = stage_weights(border - fade)
            after = stage_weights(border + fade)
            r = (t - (border - fade)) / (2 * fade)
            for k in range(3):
                w[k] = before[k] * (1 - r) + after[k] * r
    return w


def mix_segmented(tracks, seconds):
    # 三个声音放不同位置，空间上分开
    pans = [-0.3, -0.5, 0.0]
    gains = []
    for k in range(len(tracks)):
        p = pans[k]
        gains.append([math.sqrt((1 - p) / 2) * 1.414, math.sqrt((1 + p) / 2) * 1.414])

    size = seconds * RATE
    left = [0.0] * size
    right = [0.0] * size
    for i in range(size):
        t = i / size
        weights = smooth_weights(t, seconds)
        for k in range(len(tracks)):
            value = tracks[k][i] * weights[k]
            left[i] = left[i] + value * gains[k][0]
            right[i] = right[i] + value * gains[k][1]
    return left, right


def add_space(left, right, amount):
    # 空间混响，从 V2 的 0.10 降到 0.05，避免底噪被复制
    delay = int(RATE * 0.02)
    new_left = list(left)
    new_right = list(right)
    for i in range(delay, len(left)):
        new_left[i] = new_left[i] + right[i - delay] * amount
        new_right[i] = new_right[i] + left[i - delay] * amount
    return new_left, new_right


def fade(audio, seconds, fade_in, fade_out):
    n = len(audio)
    in_count = int(RATE * fade_in)
    out_count = int(RATE * fade_out)
    out = list(audio)
    for i in range(in_count):
        out[i] = out[i] * i / in_count
    for i in range(out_count):
        out[n - 1 - i] = out[n - 1 - i] * i / out_count
    return out


def normalize(audio, target):
    peak = 0.0
    for value in audio:
        if abs(value) > peak:
            peak = abs(value)
    if peak == 0:
        return audio
    scale = target / peak
    out = []
    for value in audio:
        out.append(value * scale)
    return out


# ============ 第 4 部分：按顺序执行 ============

print("正在生成音效...")
rain = make_rain(SECONDS)
tapping = make_tapping(SECONDS)
bowl = make_bowl(SECONDS)

tracks = [rain, tapping, bowl]

print("正在混音并降噪...")
left, right = mix_segmented(tracks, SECONDS)
left, right = add_space(left, right, 0.05)
left = fade(left, RATE, 1.5, 3.0)
right = fade(right, RATE, 1.5, 3.0)
left = normalize(left, 0.75)
right = normalize(right, 0.75)
# 最后一道噪声门，把混音后残留的细微底噪归零
left = noise_gate(left, 0.012)
right = noise_gate(right, 0.012)

save_stereo("output_calm_v3.wav", left, right)
print("完成！戴上耳机听 output_calm_v3.wav")
