# Qwen3.8-Flash 调用层（阿里云百炼，OpenAI 兼容接口）
# 只做一件事：把用户的话抽成固定结构的 JSON 意图
# 用标准库 urllib + json，不装任何第三方包

import json
import os
import ssl
import urllib.request
import urllib.error

URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3.8-flash"

# 严格 JSON Schema：锁死字段和类型，模型不能多给字段、不能改类型
# 这就是选 3.8-Flash 的原因——官方支持 strict:true
INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "scene": {
            "type": "string",
            "enum": ["rain", "ocean", "forest", "stream", "thunder", "wind", "fire", "mix"]
        },
        "scene_detail": {
            "type": "string",
            "description": "用一句话描述用户想要的画面，比如窗外夜雨、远海潮汐"
        },
        "mood": {
            "type": "string",
            "enum": ["sleep", "calm", "focus", "relax"]
        },
        "warmth": {
            "type": "string",
            "enum": ["warm", "neutral", "cool"],
            "description": "用户说暖/温柔/不刺耳就是 warm；说清爽/凉就是 cool"
        },
        "dynamics": {
            "type": "string",
            "enum": ["steady", "natural", "gentle_swell"],
            "description": "用户说稳/别突然炸就是 steady；说自然起伏就是 natural"
        },
        "avoid": {
            "type": "array",
            "items": {"type": "string"},
            "description": "用户明确不要的东西，比如尖锐、白噪音、循环感、雷声"
        },
        "duration_minutes": {"type": "integer"},
        "confidence": {"type": "number", "description": "0到1，对这次判断的把握"}
    },
    "required": ["scene", "scene_detail", "mood", "warmth", "dynamics",
                 "avoid", "duration_minutes", "confidence"],
    "additionalProperties": False
}

ALLOWED_TRACK_FILES = [
    "母带_城市夜雨_CC0.mp3",
    "柔和雨.hq.mp3",
    "乡村小雨.hq.mp3",
    "海浪_远海.hq.mp3",
    "海浪_黑海.hq.mp3",
    "溪流.hq.mp3",
    "备选_大雨打树叶_CC0.mp3",
    "夜风.hq.mp3",
    "雨中低鸣.hq.mp3",
    "远雷.hq.mp3",
    "虫鸣.hq.mp3",
]

AGENT_DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["ask", "compose"],
            "description": "ask=信息不够先问1个关键问题（此时tracks为空数组）；compose=信息够了或用户要求出稿（此时tracks为1-4条）"
        },
        "question": {
            "type": "string",
            "description": "action为ask时填1句温暖具体的中文追问；compose时填空字符串"
        },
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "action为ask时给3-4个4-16字一键回答选项；compose时为空数组"
        },
        "collected": {
            "type": "object",
            "properties": {
                "state": {"type": "string"},
                "scene": {"type": "string"},
                "texture": {"type": "string"},
                "spatial_rhythm": {"type": "string"},
                "avoid": {"type": "string"}
            },
            "required": ["state", "scene", "texture", "spatial_rhythm", "avoid"],
            "additionalProperties": False,
            "description": "实时收集到的5维意图摘要，尚未确认的维度填空字符串"
        },
        "final_prompt": {
            "type": "string",
            "description": "action为compose时融合初始提示词与问答确认的最终声音描述；ask时填空字符串"
        },
        "title": {
            "type": "string",
            "description": "4-12字诗意中文标题，如 阁楼暖雨、星夜远海；ask时可填草稿名"
        },
        "reply": {
            "type": "string",
            "description": "1-2句温暖自然的AI调音师中文回复，解释听懂了什么及为何追问或怎么选配/改的"
        },
        "intent": {
            "type": "object",
            "properties": {
                "scene": {
                    "type": "string",
                    "enum": ["rain", "ocean", "forest", "stream", "thunder", "wind", "fire", "mix"]
                },
                "scene_detail": {"type": "string"},
                "mood": {
                    "type": "string",
                    "enum": ["sleep", "calm", "focus", "relax"]
                },
                "warmth": {
                    "type": "string",
                    "enum": ["warm", "neutral", "cool"]
                },
                "dynamics": {
                    "type": "string",
                    "enum": ["steady", "natural", "gentle_swell"]
                },
                "avoid": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["scene", "scene_detail", "mood", "warmth", "dynamics", "avoid"],
            "additionalProperties": False
        },
        "reasoning": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-3条简短编排或意图识别思路说明"
        },
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "enum": ALLOWED_TRACK_FILES
                    },
                    "weight": {"type": "number"},
                    "pan": {"type": "number"},
                    "mode": {
                        "type": "string",
                        "enum": ["loop", "intermittent"]
                    },
                    "density": {"type": "number"},
                    "role_note": {
                        "type": "string",
                        "description": "4-12字中文说明该层作用，如 暖厚主底幕、左窗枝叶细节、远处偶尔轻响"
                    }
                },
                "required": ["path", "weight", "pan", "mode", "density", "role_note"],
                "additionalProperties": False
            }
        },
        "followups": {
            "type": "array",
            "items": {"type": "string"},
            "description": "action为compose时给3条4-10字下一步微调建议；ask时可为空数组"
        }
    },
    "required": [
        "action", "question", "options", "collected", "final_prompt",
        "title", "reply", "intent", "reasoning", "tracks", "followups"
    ],
    "additionalProperties": False
}

SYSTEM_PROMPT = (
    "你是助眠声音设计师。把用户一句中文大白话，抽成声音意图。\n"
    "规则：\n"
    "1. 场景 scene 从枚举里选最贴近的；雨声默认是 rain。\n"
    "2. scene_detail 用一句中文复述用户想要的画面。\n"
    "3. 用户提到睡不着/失眠=sleep；专注/学习=focus；放松/放空=relax；平静=calm。\n"
    "4. 暖/温柔/柔和/不刺耳=warm；清爽/凉=cool；没说=neutral。\n"
    "5. 稳/别突然/不要炸=steady；自然起伏=gentle_swell；没说=natural。\n"
    "6. avoid 列出用户明确不要的东西，没有就空数组。\n"
    "7. duration_minutes 用户说了就算，没说就 30。\n"
    "8. 严格按 JSON Schema 输出，不要多余字段。"
)

AGENT_SYSTEM_PROMPT = (
    "你是「夜息」AI 助眠调音师。用户会先写下或拼装自己的初始声音提示词，"
    "你通过最多 1~2 轮轻量问答帮对方补全关键画面/质感/节奏/避雷细节，再从以下 11 段经真人验收的 CC0 真实自然录音中编排 1~4 轨组合。\n\n"
    "可用素材库（仅限这 11 个精确文件名）：\n"
    "【底幕层（建议每次主选 1 个铺底，避免多个全频雨声/海浪叠加发糊）】\n"
    "- 母带_城市夜雨_CC0.mp3：城市夜雨（窗外闷响与沙沙雨幕，暖厚稳重，适合助眠打底）\n"
    "- 柔和雨.hq.mp3：柔和雨幕（绵密轻柔，最不刺耳，适合怕吵的人）\n"
    "- 乡村小雨.hq.mp3：乡村小雨（轻缓疏落的檐下小雨，自然留白多）\n"
    "- 海浪_远海.hq.mp3：远海潮汐（远处推来的海浪，适合放空发呆）\n"
    "- 海浪_黑海.hq.mp3：深沉黑海（更厚重低沉的夜海潮声）\n"
    "- 溪流.hq.mp3：山涧溪流（清亮舒缓的流水，适合专注或喜欢清透感的人）\n"
    "【纹理层（可叠加 0~2 个增加层次与方向）】\n"
    "- 备选_大雨打树叶_CC0.mp3：雨打树叶（细碎雨滴落在枝叶间，补颗粒感，太吵时慎用）\n"
    "- 夜风.hq.mp3：林间夜风（轻轻拂过树梢的晚风，常放偏左或偏右做空间流动）\n"
    "- 雨中低鸣.hq.mp3：暖夜低鸣（柔和低频包裹感；注意：该素材自带柔和细雨氛围垫）\n"
    "【点缀层（可设为 intermittent 偶发模式，留出呼吸感）】\n"
    "- 远雷.hq.mp3：远处闷雷（天际低沉闷雷，怕突然响/求稳/不要雷时严禁选用，适合作偏右偶发低密度）\n"
    "- 虫鸣.hq.mp3：夏夜虫鸣（夏夜院落虫鸣，适合偏左/偏右或偶发点缀）\n\n"
    "问答共创与出稿双模式规则：\n"
    "A. 当处于问答前期（qa_round < 2 且 force_compose 为 false 且 current_tracks 为空）：\n"
    "   - 先把用户已经确认的信息填入 collected（state/scene/texture/spatial_rhythm/avoid，未确认的填空字符串）。\n"
    "   - 若还缺少影响选曲的关键维度（比如只说了失眠没选画面、或选了画面但质感/点缀陪伴/避雷不明确），请输出 action=\"ask\"：\n"
    "     * reply：1 句温暖肯定已经听懂的部分；\n"
    "     * question：只提 1 个最关键的澄清问题；\n"
    "     * options：给 3~4 个好选的一键短选项（严禁推荐用户已明确避雷的元素，严禁重复问用户说过的维度）；\n"
    "     * tracks 必须为空数组 []，final_prompt 填空字符串。\n"
    "   - 若初始提示词已经非常完整（画面+质感+节奏/禁忌都清楚），也可以直接输出 action=\"compose\"。\n"
    "B. 当 qa_round >= 2、或 force_compose 为 true、或已有 current_tracks（对已生成版本继续微调）：\n"
    "   - 必须输出 action=\"compose\"，question 为空字符串，options 为空数组 []；\n"
    "   - final_prompt 必须总结初始提示词 + 问答答案成 1 句精炼的最终声音描述；\n"
    "   - 若有 current_tracks 且用户在做局部修改（加风/太吵/改偶发/不要雷等），保留未要求改动的好轨道做增量微调。\n\n"
    "编排与表达铁律：\n"
    "1. 只能调整选曲、强弱 weight(0.1~1.0)、左右声像 pan(-0.8~0.8，负左正右)、模式 mode(loop/intermittent)、偶发密度 density(0.15~0.85)。\n"
    "2. 绝不提及滤波、均衡器(EQ)、降噪、混响、压缩等任何音频后处理词，也不得声称“我听过音质很好”。\n"
    "3. 严格尊重 user_context 中的耳朵档案偏好与历史避雷记录。\n"
    "4. 文案必须极简：reply 不超过 30 字，question 不超过 18 字，options 每项 4~10 字。\n"
    "5. reasoning 给 2 条简短步骤（每条不超过 18 字）；tracks 输出 1~4 条（compose 时），role_note 4~10 字；followups 给 3 条 4~8 字追问。严格按 JSON Schema 输出。"
)


def get_key():
    # 优先环境变量，其次项目里的 key 文件
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if key:
        return key.strip()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen_key.txt")
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return ""


def _make_ssl_context():
    ctx = ssl.create_default_context()
    if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
    return ctx


def _urlopen_dashscope(req, timeout=90):
    # 国内阿里云百炼优先绕过本机代理直连，避免代理拦截导致 SSL EOF；无直连条件再回退系统代理
    ctx = _make_ssl_context()
    direct_opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ctx),
    )
    try:
        return direct_opener.open(req, timeout=timeout)
    except Exception as direct_err:
        if not urllib.request.getproxies():
            raise direct_err
        proxy_opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
        )
        return proxy_opener.open(req, timeout=timeout)


def _call_qwen_json(messages, schema_name, schema, max_tokens=500):
    key = get_key()
    if not key:
        raise RuntimeError("没有 key")

    body = {
        "model": MODEL,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True}
        },
        "enable_thinking": False,
        "max_tokens": max_tokens
    }

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")

    resp = _urlopen_dashscope(req, timeout=90)
    result = json.loads(resp.read().decode("utf-8"))
    text = result["choices"][0]["message"]["content"]
    return json.loads(text)


def understand(say):
    # 返回 dict（意图）；失败抛异常让上层降级
    return _call_qwen_json(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": say}
        ],
        "sound_intent",
        INTENT_SCHEMA,
        max_tokens=500,
    )


def design_soundscape(
    say,
    current_tracks=None,
    history=None,
    user_context=None,
    qa_round=0,
    force_compose=False,
    initial_prompt="",
):
    # 多轮问答共创与声景编排：支持 ask 追问与 compose 出稿双模式
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    context_parts = [
        "【问答状态】\n" + json.dumps({
            "qa_round": int(qa_round or 0),
            "force_compose": bool(force_compose),
            "initial_prompt": str(initial_prompt or "")[:300],
            "has_current_tracks": bool(current_tracks),
        }, ensure_ascii=False)
    ]
    if user_context:
        context_parts.append("【用户耳朵档案与记忆】\n" + json.dumps(user_context, ensure_ascii=False))
    if current_tracks:
        context_parts.append("【当前正在听的声轨 current_tracks】\n" + json.dumps(current_tracks, ensure_ascii=False))
    messages.append({"role": "system", "content": "\n\n".join(context_parts)})

    if isinstance(history, list):
        for item in history[-6:]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content[:300]})

    messages.append({"role": "user", "content": say})
    return _call_qwen_json(messages, "agent_soundscape", AGENT_DESIGN_SCHEMA, max_tokens=900)


# 自测
if os.environ.get("QWEN_SELFTEST") == "1":
    test = "睡不着，想要窗外下大雨的声音，暖一点，别突然炸一下，不要雷声"
    print("测试输入：" + test)
    intent = understand(test)
    print(json.dumps(intent, ensure_ascii=False, indent=2))
