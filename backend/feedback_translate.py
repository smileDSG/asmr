# 反馈翻译表：把用户的大白话反馈，翻译成"素材配比与选曲怎么改"
# 这是 agent 的产品壁垒：用户说"太吵了""不真实"，他不会描述声音，
# agent 负责翻译成具体的配比与标签替换动作。
# 铁律：只调配比和素材取舍，不做任何音质处理（不滤波、不降噪、不压缩）

import os

import sound_catalog


def _format_ref_like(sample_path, meta):
    if "/" in sample_path or "\\" in sample_path:
        return meta["rel_path"]
    return meta["filename"]


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
    new_items = [(path, float(w)) for path, w in items]
    notes = []
    current_files = {os.path.basename(p) for p, _ in new_items}

    # 太吵 / 刺耳 / 尖锐 → 先尝试已有的柔和雨/乡村小雨，否则按 sound_catalog 找同场景最柔替代
    if "吵" in feedback or "刺耳" in feedback or "尖锐" in feedback or "太尖" in feedback:
        soft_indexes = [
            i for i, (p, _) in enumerate(new_items)
            if "柔和雨" in p or "乡村小雨" in p
        ]
        if soft_indexes:
            for i in range(len(new_items)):
                new_items[i] = (new_items[i][0], 1.0 if i in soft_indexes else 0.0)
            notes.append("太吵 → 只用柔和雨/乡村小雨（最柔的素材）")
        else:
            dropped_accents = False
            for i, (p, w) in enumerate(new_items):
                meta = sound_catalog.get_item(p)
                is_harsh = (
                    "大雨打树叶" in p or "远雷" in p
                    or (meta and (meta.get("dynamics") == "spiky" or "吵" in meta.get("avoid_tags", [])))
                )
                if is_harsh and w > 0 and len(new_items) > 1:
                    new_items[i] = (p, 0.0)
                    dropped_accents = True

            swapped = False
            active_idx = [i for i, (_, w) in enumerate(new_items) if w > 0]
            if active_idx:
                lead_i = max(active_idx, key=lambda idx: new_items[idx][1])
                lead_p, lead_w = new_items[lead_i]
                lead_meta = sound_catalog.get_item(lead_p)
                if lead_meta and lead_meta.get("intensity") != "soft":
                    alts = sound_catalog.find_alternatives(
                        lead_p,
                        prefer_softer=True,
                        exclude_filenames=current_files,
                        avoid_tags=["吵", "尖锐", "削波", "噼啪"],
                    )
                    if alts:
                        alt = alts[0]
                        new_items[lead_i] = (_format_ref_like(lead_p, alt), lead_w)
                        swapped = True
                        notes.append(f"太吵 → 将「{lead_meta['name']}」换成更轻柔的「{alt['name']}」")
            if not swapped:
                notes.append("太吵 → 去掉高颗粒/尖锐层" if dropped_accents else "太吵 → 降轻刺激元素")

    # 声音杂 / 好几层 / 乱 → 只留权重最高的一个主素材
    if "杂" in feedback or "好几层" in feedback or "乱" in feedback:
        best_i = 0
        best_w = -1.0
        for i, (_, w) in enumerate(new_items):
            if w > best_w:
                best_w = w
                best_i = i
        for i in range(len(new_items)):
            new_items[i] = (new_items[i][0], 1.0 if i == best_i else 0.0)
        notes.append("声音杂 → 只保留一个主素材")

    # 太闷 / 没细节 / 听不清 / 雨声没了 → 补雨滴颗粒或切同场景细节更丰富版本
    if "闷" in feedback or "没细节" in feedback or "听不清" in feedback or "雨声没" in feedback:
        leaf_found = False
        for i, (p, _) in enumerate(new_items):
            if "大雨打树叶" in p:
                new_items[i] = (p, 0.35)
                leaf_found = True
        if leaf_found:
            notes.append("太闷 → 加入大雨打树叶，补回雨滴颗粒")
        elif new_items:
            lead_i = max(range(len(new_items)), key=lambda idx: new_items[idx][1])
            lead_p, lead_w = new_items[lead_i]
            lead_meta = sound_catalog.get_item(lead_p)
            if lead_meta and lead_meta["scene"] == "rain" and "备选_大雨打树叶_CC0.mp3" not in current_files:
                leaf_meta = sound_catalog.get_item("备选_大雨打树叶_CC0.mp3")
                if leaf_meta:
                    new_items.append((_format_ref_like(lead_p, leaf_meta), 0.35))
                    notes.append("太闷 → 加入大雨打树叶，补回雨滴颗粒")
            elif lead_meta:
                alts = sound_catalog.find_alternatives(
                    lead_p, prefer_more_detail=True, exclude_filenames=current_files
                )
                if alts:
                    new_items[lead_i] = (_format_ref_like(lead_p, alts[0]), lead_w)
                    notes.append(f"太闷 → 换成细节更清晰的「{alts[0]['name']}」")

    # 太假 / 电子味 / 不真实 → 只用真实母带单段
    if "假" in feedback or "电子" in feedback or "不真实" in feedback:
        master_found = False
        for i, (p, _) in enumerate(new_items):
            if "母带_城市夜雨" in p:
                new_items[i] = (p, 1.0)
                master_found = True
            else:
                new_items[i] = (p, 0.0)
        if not master_found:
            new_items = [("product_assets/母带_城市夜雨_CC0.mp3", 1.0)]
        notes.append("不真实 → 只用城市夜雨母带单段")

    # 雨声太小 / 雨声没了 → 提高雨声素材，压低音乐垫
    if "雨声小" in feedback or "雨太小" in feedback or "雨声没" in feedback:
        for i, (p, _) in enumerate(new_items):
            if "雨中低鸣" in p or "氛围" in p:
                new_items[i] = (p, 0.0)
        notes.append("雨声太小 → 去掉音乐垫，突出雨声")

    # 想要暖 / 温柔 / 柔和
    if "暖" in feedback or "温柔" in feedback or "柔" in feedback:
        warmer_done = False
        active_idx = [i for i, (_, w) in enumerate(new_items) if w > 0]
        if active_idx:
            lead_i = max(active_idx, key=lambda idx: new_items[idx][1])
            lead_p, lead_w = new_items[lead_i]
            lead_meta = sound_catalog.get_item(lead_p)
            if lead_meta and lead_meta.get("warmth") != "warm":
                alts = sound_catalog.find_alternatives(
                    lead_p, prefer_warmer=True, exclude_filenames=current_files
                )
                if alts:
                    new_items[lead_i] = (_format_ref_like(lead_p, alts[0]), lead_w)
                    warmer_done = True
                    notes.append(f"更暖 → 将「{lead_meta['name']}」换成更暖柔的「{alts[0]['name']}」")
        if not warmer_done:
            notes.append("更暖 → 倾向母带 + 柔和雨或暖厚底幕")

    # 想要稳 / 别突然 / 别炸 → 去掉远雷及突兀尖峰音轨
    if "稳" in feedback or "别突然" in feedback or "别炸" in feedback:
        for i, (p, _) in enumerate(new_items):
            meta = sound_catalog.get_item(p)
            if "远雷" in p or (meta and ("突然响" in meta.get("avoid_tags", []) or meta.get("dynamics") == "spiky")):
                new_items[i] = (p, 0.0)
        notes.append("要稳 → 去掉远雷及突兀瞬态音轨，避免突然响")

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
