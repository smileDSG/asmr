# 反馈翻译表：把用户的大白话反馈，翻译成"素材配比怎么改"
# 这是 agent 的产品壁垒：用户说"太吵了""不真实"，他不会描述声音，
# agent 负责翻译成具体的配比动作。
# 铁律：只调配比和素材取舍，不做任何音质处理（不滤波、不降噪、不压缩）

import os


def normalize(items):
    # 把权重归一到加起来等于 1，避免叠加后削波
    total = 0.0
    for path, w in items:
        total = total + w
    out = []
    if total <= 0:
        for path, w in items:
            out.append((path, 0.0))
        if len(out) > 0:
            out[0] = (out[0][0], 1.0)
        return out
    for path, w in items:
        out.append((path, w / total))
    return out


def apply_feedback(feedback, items):
    # 输入：用户一句话反馈 + 当前配比
    # 输出：新配比 + 改了什么的说明
    new_items = []
    for path, w in items:
        new_items.append((path, w))
    notes = []

    # 太吵 / 刺耳 / 尖锐 → 优先切到柔和雨/乡村小雨（用户验收过最柔的两段）
    if "吵" in feedback or "刺耳" in feedback or "尖锐" in feedback or "太尖" in feedback:
        # 先看有没有柔和素材，有就把权重全给它
        soft_indexes = []
        for i in range(len(new_items)):
            if "柔和雨" in new_items[i][0] or "乡村小雨" in new_items[i][0]:
                soft_indexes.append(i)
        if len(soft_indexes) > 0:
            for i in range(len(new_items)):
                if i in soft_indexes:
                    new_items[i] = (new_items[i][0], 1.0)
                else:
                    new_items[i] = (new_items[i][0], 0.0)
            notes.append("太吵 → 只用柔和雨/乡村小雨（最柔的素材）")
        else:
            for i in range(len(new_items)):
                if "大雨打树叶" in new_items[i][0] or "远雷" in new_items[i][0]:
                    new_items[i] = (new_items[i][0], 0.0)
            notes.append("太吵 → 去掉雨滴颗粒层和远雷")

    # 声音杂 / 好几层 / 乱 → 只留权重最高的一个主素材
    if "杂" in feedback or "好几层" in feedback or "乱" in feedback:
        best_i = 0
        best_w = -1.0
        for i in range(len(new_items)):
            if new_items[i][1] > best_w:
                best_w = new_items[i][1]
                best_i = i
        for i in range(len(new_items)):
            if i == best_i:
                new_items[i] = (new_items[i][0], 1.0)
            else:
                new_items[i] = (new_items[i][0], 0.0)
        notes.append("声音杂 → 只保留一个主素材")

    # 太闷 / 没细节 / 听不清 / 雨声没了 → 加入大雨打树叶补颗粒
    if "闷" in feedback or "没细节" in feedback or "听不清" in feedback or "雨声没" in feedback:
        for i in range(len(new_items)):
            if "大雨打树叶" in new_items[i][0]:
                new_items[i] = (new_items[i][0], 0.35)
        notes.append("太闷 → 加入大雨打树叶，补回雨滴颗粒")

    # 太假 / 电子味 / 不真实 → 只用母带单段（真实录音基准）
    if "假" in feedback or "电子" in feedback or "不真实" in feedback:
        for i in range(len(new_items)):
            if "母带_城市夜雨" in new_items[i][0]:
                new_items[i] = (new_items[i][0], 1.0)
            else:
                new_items[i] = (new_items[i][0], 0.0)
        notes.append("不真实 → 只用城市夜雨母带单段")

    # 雨声太小 / 雨声没了 → 提高雨声素材，压低音乐垫
    if "雨声小" in feedback or "雨太小" in feedback or "雨声没" in feedback:
        for i in range(len(new_items)):
            if "雨中低鸣" in new_items[i][0] or "氛围" in new_items[i][0]:
                new_items[i] = (new_items[i][0], 0.0)
        notes.append("雨声太小 → 去掉音乐垫，突出雨声")

    # 想要暖 / 温柔 / 柔和
    if "暖" in feedback or "温柔" in feedback or "柔" in feedback:
        notes.append("更暖 → 倾向母带 + 柔和雨（若当前不是这样）")

    # 想要稳 / 别突然 / 别炸 → 去掉远雷
    if "稳" in feedback or "别突然" in feedback or "别炸" in feedback:
        for i in range(len(new_items)):
            if "远雷" in new_items[i][0]:
                new_items[i] = (new_items[i][0], 0.0)
        notes.append("要稳 → 去掉远雷，避免突然响")

    if len(notes) == 0:
        notes.append("没识别到明确反馈，配比保持不变")

    return normalize(new_items), notes


if os.environ.get("FEEDBACK_SELFTEST") == "1":
    base = [
        ("母带_城市夜雨.mp3", 0.6),
        ("大雨打树叶.mp3", 0.2),
        ("柔和雨.mp3", 0.2)
    ]
    tests = ["太吵了", "声音杂", "太闷没细节", "不真实", "再暖一点", "别突然炸"]
    for f in tests:
        new, notes = apply_feedback(f, base)
        print("反馈：" + f)
        for note in notes:
            print("  -> " + note)
        shown = []
        for p, w in new:
            if w > 0:
                shown.append(p + "=" + str(round(w, 2)))
        print("  配比：" + "  ".join(shown))
