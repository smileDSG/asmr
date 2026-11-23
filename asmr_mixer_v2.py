# ASMR 混音器 · V2 分段主次版
# 改掉了 V1 "四种声音全程齐鸣"的毛病，改成像真视频一样分三段
# 只用 Python 自带模块，不需要安装任何东西
# 运行：python asmr_mixer_v2.py
# 成品：output_calm_v2.wav（建议和 V1 的成品对比着听）

import wave
import array
import math
import random

RATE = 22050
SECONDS = 20


# ============ 第 1 部分：合成 4 个测试音效（和 V1 一样）============

def make_rain(seconds):
    out = []
    last = 0.0
    for i in range(seconds * RATE):
        white = random.uniform(-1, 1)
        last = last * 0.96 + white * 0.04
        out.append(last * 3)
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


def make_pages(seconds):
    out = []
    last = 0.0
    period = int(RATE * 1.3)
    for i in range(seconds * RATE):
        t = i % period
        white = random.uniform(-1, 1)
        last = last * 0.7 + white * 0.3
        if t < 2000:
            env = math.sin(math.pi * t / 2000)
        else:
            env = 0
        out.append(last * env * 0.8)
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


# ============ 第 3 部分：分段配方（这次的核心改动）============

# 每一段各音效的音量比例，顺序是：雨声、轻敲、颂钵、翻书
# 同一时刻只让一个声音当主角，其余压得很低或干脆没有
def stage_weights(t):
    if t < 0.2:
        # 引导段 0-20%：颂钵为主，雨声轻轻垫底
        return [0.12, 0.0, 0.50, 0.0]
    elif t < 0.8:
        # 主体段 20-80%：轻敲为主，雨声垫底，翻书几乎听不见
        return [0.12, 0.50, 0.05, 0.05]
    else:
        # 收尾段 80-100%：颂钵为主，雨声垫底
        return [0.10, 0.0, 0.45, 0.0]


def smooth_weights(t, seconds):
    # 段落交界处做 1.5 秒平滑过渡，避免声音突然跳变
    w = stage_weights(t)
    fade = 1.5 / seconds
    for border in [0.2, 0.8]:
        if border - fade < t < border + fade:
            before = stage_weights(border - fade)
            after = stage_weights(border + fade)
            r = (t - (border - fade)) / (2 * fade)
            for k in range(4):
                w[k] = before[k] * (1 - r) + after[k] * r
    return w


def mix_segmented(tracks, seconds):
    # 四个声音放在不同位置：雨声偏左、轻敲偏左、颂钵居中、翻书偏右
    # 空间上分开，耳朵就容易分辨，不会挤成一团
    pans = [-0.3, -0.5, 0.0, 0.5]
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
    # 轻微空间感，V1 用了 0.25 太糊，这次降到 0.10
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
pages = make_pages(SECONDS)

tracks = [rain, tapping, bowl, pages]

print("正在按分段配方混音...")
left, right = mix_segmented(tracks, SECONDS)
left, right = add_space(left, right, 0.10)
left = fade(left, RATE, 1.5, 3.0)
right = fade(right, RATE, 1.5, 3.0)
left = normalize(left, 0.9)
right = normalize(right, 0.9)

save_stereo("output_calm_v2.wav", left, right)
print("完成！戴上耳机听 output_calm_v2.wav")
