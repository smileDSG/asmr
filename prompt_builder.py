# 文本 → 结构化提示词
# 输入：用户一句大白话
# 输出：①给 ElevenLabs 的英文提示词 ②给助眠后处理的参数
#
# 英文提示词按官方推荐的四段式写：声源 + 声学环境 + 动态/时长 + 质感形容词
# 官方明确说不要写"敲4下"这种精确次数，也不要写没有声学依据的情绪词（比如只写 scary）
# 现在先用关键词规则匹配，不依赖大模型；以后接 LLM 只需要换掉 detect_scene 一个函数

SCENES = [
    {
        "id": "rain_window",
        "name": "窗外夜雨",
        "keywords": ["睡不着", "失眠", "脑子", "安静", "雨", "入睡", "睡前", "雨声"],
        "prompt": (
            "Heavy rain at night heard from inside a quiet bedroom, close muted raindrops "
            "hitting window glass and roof eaves, layered with a soft continuous distant "
            "rain curtain, low frequency weighted, warm and rounded, no sharp high frequencies, "
            "gentle natural swells in intensity, steady and non-arousing, seamless ambient loop"
        ),
        "post": {"lowpass": 5200, "thud": 0.45, "sand": 0.10,
                 "reverb": 0.18, "wander": 0.16, "compress": 3.0}
    },
    {
        "id": "rain_far",
        "name": "凌晨远雨",
        "keywords": ["凌晨", "焦虑", "心事", "清醒", "深夜", "三点", "静"],
        "prompt": (
            "Distant steady rain in the small hours, softened by distance and walls, "
            "low muffled patter with a wide even wash behind it, no individual sharp drops, "
            "dark warm tone, very slow gentle breathing swells, sparse and unchanging, "
            "seamless ambient loop"
        ),
        "post": {"lowpass": 4200, "thud": 0.50, "sand": 0.04,
                 "reverb": 0.24, "wander": 0.12, "compress": 3.2}
    },
    {
        "id": "ocean",
        "name": "远海潮汐",
        "keywords": ["放空", "太累", "累", "海", "海浪", "潮汐", "什么都不想"],
        "prompt": (
            "Slow ocean swells against a distant shore, heard from a quiet room, "
            "soft low rolling water with a thin layer of fine foam, warm dark tone, "
            "long natural breathing rhythm, no sharp peaks, seamless ambient loop"
        ),
        "post": {"lowpass": 6000, "thud": 0.30, "sand": 0.12,
                 "reverb": 0.20, "wander": 0.22, "compress": 2.6}
    },
    {
        "id": "forest",
        "name": "雨中树林",
        "keywords": ["森林", "树叶", "树林", "自然", "林", "虫"],
        "prompt": (
            "Rain falling through dense tree leaves in a quiet forest at night, "
            "muted drops landing on leaves and soft ground, far away rain curtain, "
            "warm low weighted tone, gentle irregular swells, no bright sharp ticks, "
            "seamless ambient loop"
        ),
        "post": {"lowpass": 5600, "thud": 0.38, "sand": 0.22,
                 "reverb": 0.22, "wander": 0.20, "compress": 2.8}
    },
    {
        "id": "fire",
        "name": "壁炉暖夜",
        "keywords": ["壁炉", "温暖", "暖", "火", "柴"],
        "prompt": (
            "Soft fireplace crackle in a quiet cabin at night, low warm bed of burning wood "
            "with occasional gentle pops, distant rain on the roof behind it, "
            "dark rounded tone, no loud sudden cracks, steady and slow, seamless ambient loop"
        ),
        "post": {"lowpass": 5000, "thud": 0.35, "sand": 0.08,
                 "reverb": 0.16, "wander": 0.14, "compress": 3.5}
    },
    {
        "id": "focus",
        "name": "稳定专注",
        "keywords": ["专注", "学习", "工作", "别打扰", "自习", "写作"],
        "prompt": (
            "Steady even rainfall on a roof at a distance, flat consistent texture "
            "with no distinct events, low warm masking wash, minimal variation, "
            "no sharp transients, seamless ambient loop"
        ),
        "post": {"lowpass": 6000, "thud": 0.32, "sand": 0.16,
                 "reverb": 0.10, "wander": 0.05, "compress": 3.0}
    },
]

# 用户追加要求 → 提示词补丁 + 后处理补丁
ADDONS = [
    {
        "keywords": ["闷雷", "雷声", "雷"],
        "prompt_add": ", with very distant low rolling thunder far away, never close or sharp",
        "post": {"thud": 0.60, "lowpass": 4600, "compress": 3.4}
    },
    {
        "keywords": ["树叶", "窸窣", "风吹", "风声"],
        "prompt_add": ", with faint wind moving through leaves",
        "post": {"sand": 0.26}
    },
    {
        "keywords": ["动态范围小", "稳", "不要突然", "别炸"],
        "prompt_add": ", level and dynamics highly consistent",
        "post": {"compress": 4.0, "wander": 0.06}
    },
    {
        "keywords": ["起伏", "自然", "不要循环"],
        "prompt_add": ", with organic slow variations that never repeat obviously",
        "post": {"wander": 0.22}
    },
]


def detect_scene(say):
    # 哪一场景命中的关键词最多就用哪个；全没命中就用窗外夜雨兜底
    best = SCENES[0]
    best_score = 0
    for scene in SCENES:
        score = 0
        for word in scene["keywords"]:
            if word in say:
                score = score + 1
        if score > best_score:
            best = scene
            best_score = score
    return best


def apply_addons(say, prompt, post):
    for addon in ADDONS:
        hit = False
        for word in addon["keywords"]:
            if word in say:
                hit = True
        if hit:
            prompt = prompt + addon["prompt_add"]
            for key in addon["post"]:
                post[key] = addon["post"][key]
    return prompt, post


def build(say):
    # 主函数：一句话 → 完整配置
    scene = detect_scene(say)
    post = {}
    for key in scene["post"]:
        post[key] = scene["post"][key]

    prompt = scene["prompt"]
    prompt, post = apply_addons(say, prompt, post)

    # 用户说 -20dB 就按这个来，默认也差不多
    target_rms = 0.050
    if "-20" in say:
        target_rms = 0.055

    return {
        "say": say,
        "scene": scene["name"],
        "prompt": prompt,
        "duration": 30,
        "loop": True,
        "prompt_influence": 0.65,
        "post": post,
        "target_rms": target_rms
    }


