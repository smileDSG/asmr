# ASMR 混音器 · 最小可运行版本
# 只用 Python 自带模块，不需要 pip install 任何东西
# 运行方法：在终端里输入  python asmr_mixer.py
# 跑完会生成 5 个 wav 文件，戴上耳机听 output_head_therapy.wav

import wave
import array
import math
import random

# 采样率和时长（想听长一点就把 SECONDS 改大，比如 60）
RATE = 22050
SECONDS = 20


# ============ 第 1 部分：合成 4 个测试音效 ============
# 这一步是临时替代"去网上找素材"。等你有真实 wav 了，
# 用下一节的 load_mono 读进来，把这 4 行换掉就行。

def make_rain(seconds):
    # 雨声：白噪声做平滑处理，听着像沙沙的下雨声
    out = []
    last = 0.0
    for i in range(seconds * RATE):
        white = random.uniform(-1, 1)
        last = last * 0.96 + white * 0.04
        out.append(last * 3)
    return out


def make_tapping(seconds):
    # 轻敲：每隔 0.6 秒来一下，快速衰减的短音
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
    # 颂钵：几个低频正弦叠在一起，慢慢起伏
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
    # 翻书/摩擦：一阵一阵的噪声
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


# ============ 第 2 部分：读写 wav 文件 ============

def save_mono(path, samples):
    # 把一串数字存成单声道 wav
    pcm = array.array('h')
    for value in samples:
        x = int(max(-1, min(1, value)) * 32767)
        pcm.append(x)
    w = wave.open(path, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(pcm.tobytes())
    w.close()


def save_stereo(path, left, right):
    # 把左右两个声道存成立体声 wav
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


def load_mono(path):
    # 以后读你自己下载的 wav 用这个函数（目前没用到）
    w = wave.open(path, 'rb')
    data = w.readframes(w.getnframes())
    w.close()
    raw = array.array('h')
    raw.frombytes(data)
    out = []
    for value in raw:
        out.append(value / 32768)
    return out


# ============ 第 3 部分：混音 + 3D 效果 ============

def mix_to_stereo(tracks, weights, pans, seconds):
    # tracks：音效列表；weights：各占多少比例；pans：左右位置(-1最左, 0中间, 1最右)
    size = seconds * RATE
    left = [0.0] * size
    right = [0.0] * size
    for k in range(len(tracks)):
        samples = tracks[k]
        weight = weights[k]
        pan = pans[k]
        left_gain = math.sqrt((1 - pan) / 2) * 1.414
        right_gain = math.sqrt((1 + pan) / 2) * 1.414
        delay = int((1 - pan) * 8)
        for i in range(size):
            value = samples[i] * weight
            left[i] = left[i] + value * left_gain
            if i + delay < size:
                right[i + delay] = right[i + delay] + value * right_gain
    return left, right


def add_space(left, right, amount):
    # 制造空间感：把对方声道延迟一点再叠回来，像在小房间里
    delay = int(RATE * 0.02)
    new_left = list(left)
    new_right = list(right)
    for i in range(delay, len(left)):
        new_left[i] = new_left[i] + right[i - delay] * amount
        new_right[i] = new_right[i] + left[i - delay] * amount
    return new_left, new_right


def fade(audio, seconds, fade_in, fade_out):
    # 淡入淡出：开头慢慢变大，结尾慢慢变小
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
    # 统一音量，防止声音爆掉或太小
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

print("正在生成测试音效...")
rain = make_rain(SECONDS)
tapping = make_tapping(SECONDS)
bowl = make_bowl(SECONDS)
pages = make_pages(SECONDS)

# 把 4 个素材单独存一份，方便你逐个听
save_mono("sound_rain.wav", rain)
save_mono("sound_tapping.wav", tapping)
save_mono("sound_bowl.wav", bowl)
save_mono("sound_pages.wav", pages)

# 这就是从 B站视频拆出来的"头疗助眠"配方
# 想改配方就改下面三行：比例加起来约等于 1，位置在 -1 到 1 之间
tracks = [rain, tapping, bowl, pages]
weights = [0.30, 0.35, 0.20, 0.15]
pans = [-0.4, -0.7, 0.0, 0.6]

print("正在混音并加上 3D 效果...")
left, right = mix_to_stereo(tracks, weights, pans, SECONDS)
left, right = add_space(left, right, 0.25)
left = fade(left, RATE, 1.5, 2.0)
right = fade(right, RATE, 1.5, 2.0)
left = normalize(left, 0.9)
right = normalize(right, 0.9)

save_stereo("output_head_therapy.wav", left, right)
print("完成！戴上耳机听 output_head_therapy.wav")
