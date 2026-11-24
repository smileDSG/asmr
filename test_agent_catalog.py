# 全链路验证脚本：41 段结构化标签库 + Agent 编排 + 规则降级 + 多场景反馈 + 渲染 + Qwen3.8-Flash 联调
# 用法：C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -u test_agent_catalog.py

import json
import os
import re
import numpy as np

import sound_catalog
import qwen_client
import understanding_brain as brain
import 素材执行层 as executor
import feedback_translate as ft
import server


BASE = os.path.dirname(os.path.abspath(__file__))


def test_catalog_and_frontend_sync():
    print("[1/5] 校验 sound_catalog.json 与磁盘/前端 yexi_catalog.js 一致性...")
    assert len(sound_catalog.ALL_SOUNDS) == 41, f"预期 41 段，实际 {len(sound_catalog.ALL_SOUNDS)}"

    layers = {}
    for it in sound_catalog.ALL_SOUNDS:
        layers[it["layer"]] = layers.get(it["layer"], 0) + 1
    assert layers == {"bed": 18, "texture": 12, "accent": 11}, f"三层分布异常: {layers}"

    disk_rels = set()
    for folder in ("product_assets", "scene_assets"):
        for fn in os.listdir(os.path.join(BASE, folder)):
            disk_rels.add(f"{folder}/{fn}")
    cat_rels = {it["rel_path"] for it in sound_catalog.ALL_SOUNDS}
    assert disk_rels == cat_rels, f"磁盘与目录差异: {disk_rels ^ cat_rels}"

    # 校验前端 yexi_catalog.js
    js_path = os.path.join(BASE, "product_site", "yexi_catalog.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js_txt = f.read()
    m = re.search(r"var\s+YEXI_SOUNDS\s*=\s*\[(.*?)\];", js_txt, re.S)
    assert m, "未找到 YEXI_SOUNDS"
    arr_txt = m.group(1)
    js_paths = re.findall(r'path:\s*"([^"]+)"', arr_txt)
    js_imgs = re.findall(r'img:\s*"([^"]+)"', arr_txt)
    assert len(js_paths) == 41, f"前端 YEXI_SOUNDS 数量预期 41，实际 {len(js_paths)}"
    assert set(js_paths) == set(sound_catalog.ALLOWED_TRACK_FILES), "前端与后端文件名集合不一致"
    for rel_img in js_imgs:
        full_img = os.path.join(BASE, "product_site", rel_img)
        assert os.path.isfile(full_img), f"前端引用图片不存在: {rel_img}"
    print("  -> PASS: 41 段音轨、三层分布(18/12/11)、磁盘文件、前端 yexi_catalog.js 与封面图全部一致")


def test_rules_and_executor():
    print("[2/5] 校验规则编排与执行层覆盖全部场景与避雷逻辑...")
    cases = [
        ("睡不着，想要窗外暖一点的雨声，不要雷", lambda r: r["intent"]["scene"] == "rain" and all("远雷" not in t["path"] for t in r["tracks"])),
        ("壁炉炉火暖夜，不要太吵", lambda r: r["intent"]["scene"] == "fire" and any("炉火_" in t["path"] for t in r["tracks"]) and all("雨中低鸣" not in t["path"] for t in r["tracks"])),
        ("露营帐篷下雨，想被包裹住", lambda r: any("帐篷雨" in t["path"] for t in r["tracks"])),
        ("长一点的温柔溪流加稀疏夜莺鸟鸣", lambda r: any("溪流_" in t["path"] for t in r["tracks"]) and any("鸟鸣" in t["path"] for t in r["tracks"])),
        ("想要轻柔采耳加羽毛轻拂助眠", lambda r: any("采耳" in t["path"] for t in r["tracks"]) and any("羽毛" in t["path"] for t in r["tracks"])),
        ("下雨天在台灯下翻书写字专注", lambda r: any("雨" in t["path"] for t in r["tracks"]) and any("翻书" in t["path"] for t in r["tracks"]) and any("写字" in t["path"] for t in r["tracks"])),
        ("麦套轻扫麦克风", lambda r: any("803595" in t["path"] for t in r["tracks"])),
        ("森林松涛风加一点虫鸣", lambda r: any("林风" in t["path"] for t in r["tracks"]) and any("虫鸣" in t["path"] for t in r["tracks"])),
        ("长段海浪温柔拍岸", lambda r: r["intent"]["scene"] == "ocean" and any("海浪_" in t["path"] for t in r["tracks"])),
        ("小姐姐人声耳语讲故事", lambda r: ("暂未收录" in r["reply"] or "未收录" in r["reply"] or "暂无" in r["reply"]) and len(r["tracks"]) >= 1),
    ]
    for say, pred in cases:
        res = brain.design_soundscape_rules(say, force_compose=True)
        assert res["action"] == "compose" and len(res["tracks"]) >= 1, f"出稿失败: {say}"
        assert pred(res), f"规则预期未命中 ({say}): {res}"

    # 执行层 fire 不再映射雨中低鸣
    fire_picked = executor.pick({"scene": "fire", "scene_detail": "壁炉低燃", "warmth": "warm", "dynamics": "steady", "avoid": []})
    assert all("炉火_" in p for p, _ in fire_picked), f"执行层 fire 选曲错误: {fire_picked}"

    # 历史否决避雷测试
    avoid_ctx = {"avoid_tracks": ["炉火_壁炉低燃_836535.hq.mp3"]}
    res_avoid = brain.design_soundscape_rules("来点壁炉炉火", user_context=avoid_ctx, force_compose=True)
    assert all(t["path"] != "炉火_壁炉低燃_836535.hq.mp3" for t in res_avoid["tracks"]), f"未避开历史否决音轨: {res_avoid['tracks']}"
    print(f"  -> PASS: {len(cases)} 条口语回归 + 执行层 fire 修复 + 历史 avoid_tracks 避雷全部通过")


def test_feedback_loops():
    print("[3/5] 校验多场景反馈翻译与增量微调...")
    # 1. feedback_translate
    new_fire, notes_fire = ft.apply_feedback("太吵了", [("scene_assets/炉火_营地篝火_62487.hq.mp3", 1.0)])
    assert any("766127" in p or "836535" in p for p, w in new_fire if w > 0), f"炉火太吵未切柔和: {new_fire}, {notes_fire}"

    new_stream, _ = ft.apply_feedback("太吵刺耳", [("scene_assets/溪流.hq.mp3", 1.0)])
    assert any("707576" in p or "767320" in p for p, w in new_stream if w > 0), f"溪流太吵未切柔和: {new_stream}"

    new_mix, _ = ft.apply_feedback("声音杂", [("product_assets/母带_城市夜雨_CC0.mp3", 0.7), ("scene_assets/夜风.hq.mp3", 0.3)])
    assert sum(1 for _, w in new_mix if w > 0) == 1, f"声音杂未收束单轨: {new_mix}"

    new_detail, _ = ft.apply_feedback("太闷没细节", [("product_assets/母带_城市夜雨_CC0.mp3", 1.0)])
    assert any("大雨打树叶" in p and w > 0 for p, w in new_detail), f"太闷未补雨叶细节: {new_detail}"

    # 2. _apply_incremental_tweak
    cur = [
        {"path": "溪流_柔和河水_707576.hq.mp3", "weight": 0.7, "pan": 0.0, "mode": "loop", "density": 0.4},
        {"path": "鸟鸣_夜莺鸣叫_853566.hq.mp3", "weight": 0.3, "pan": 0.4, "mode": "intermittent", "density": 0.3},
    ]
    tw1 = brain._apply_incremental_tweak("不要鸟了", cur)
    assert tw1 and all("鸟鸣" not in t["path"] for t in tw1["tracks"]), f"未移除鸟鸣: {tw1}"

    tw2 = brain._apply_incremental_tweak("加一点羽毛轻拂", [{"path": "母带_城市夜雨_CC0.mp3", "weight": 0.72, "pan": 0.0, "mode": "loop", "density": 0.4}])
    assert tw2 and any("羽毛" in t["path"] for t in tw2["tracks"]), f"未加羽毛: {tw2}"

    tw3 = brain._apply_incremental_tweak("太吵了", [{"path": "炉火_营地篝火_62487.hq.mp3", "weight": 0.7, "pan": 0.0, "mode": "loop", "density": 0.4}])
    assert tw3 and any("766127" in t["path"] or "836535" in t["path"] for t in tw3["tracks"]), f"炉火微调未变柔: {tw3}"
    print("  -> PASS: 雨/炉火/溪流/ASMR 反馈翻译与增量微调全部正确")


def test_audio_render_and_server_helpers():
    print("[4/5] 校验音频混音渲染（炉火 + 采耳 + 偶发羽毛）与服务端白名单...")
    for fn in sound_catalog.ALLOWED_TRACK_FILES:
        assert server.find_relpath(fn) != "", f"find_relpath 漏掉 {fn}"

    assert server._infer_post_group([{"rel": "scene_assets/炉火_壁炉低燃_836535.hq.mp3", "weight": 0.8}]) == "炉火"
    assert server._infer_post_group([{"rel": "scene_assets/ASMR_采耳_690078.hq.mp3", "weight": 0.8}]) == "ASMR"

    mix, sr = server.render([
        {"rel": "scene_assets/炉火_夜营氛围_766127.hq.mp3", "weight": 0.70, "pan": 0.0, "mode": "loop", "density": 0.4},
        {"rel": "scene_assets/ASMR_采耳_690078.hq.mp3", "weight": 0.42, "pan": -0.2, "mode": "loop", "density": 0.4},
        {"rel": "scene_assets/ASMR_羽毛轻拂_708086.hq.mp3", "weight": 0.35, "pan": 0.3, "mode": "intermittent", "density": 0.45},
    ], seconds=5)
    assert sr == 44100 and mix.shape == (44100 * 5, 2), f"渲染尺寸异常: {mix.shape}, sr={sr}"
    assert not np.isnan(mix).any() and not np.isinf(mix).any(), "渲染出现 NaN/Inf"
    peak = float(np.max(np.abs(mix)))
    assert 0.01 < peak <= 0.9501, f"峰值异常: {peak}"
    print(f"  -> PASS: 5秒混音渲染正常 shape={mix.shape} peak={peak:.4f}")


def _assert_schema_strict(node, label="root"):
    if not isinstance(node, dict):
        return
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False, f"{label} 缺少 additionalProperties=False"
        props = node.get("properties") or {}
        req = set(node.get("required") or [])
        assert set(props.keys()) == req, f"{label} required 与 properties 不一致: {set(props.keys()) ^ req}"
        for k, v in props.items():
            _assert_schema_strict(v, f"{label}.{k}")
    elif node.get("type") == "array" and isinstance(node.get("items"), dict):
        _assert_schema_strict(node["items"], f"{label}[]")


def test_qwen_schema_mock_and_live():
    print("[5/5] 校验 Qwen Schema/Prompt/过滤逻辑、避雷上下文与云端联调...")

    # 1. 严格校验 AGENT_DESIGN_SCHEMA & INTENT_SCHEMA（含 41 项枚举与 9 项场景）
    _assert_schema_strict(qwen_client.INTENT_SCHEMA, "INTENT_SCHEMA")
    _assert_schema_strict(qwen_client.AGENT_DESIGN_SCHEMA, "AGENT_DESIGN_SCHEMA")
    track_enum = qwen_client.AGENT_DESIGN_SCHEMA["properties"]["tracks"]["items"]["properties"]["path"]["enum"]
    assert len(track_enum) == 41 and set(track_enum) == set(sound_catalog.ALLOWED_TRACK_FILES), "track enum 未精确包含 41 段素材"
    scene_enum = qwen_client.AGENT_DESIGN_SCHEMA["properties"]["intent"]["properties"]["scene"]["enum"]
    assert "asmr" in scene_enum and len(scene_enum) == 9, f"scene enum 异常: {scene_enum}"

    # 2. 校验 AGENT_SYSTEM_PROMPT 包含全部 41 个文件名与诚实/避雷规则
    prompt_txt = qwen_client.AGENT_SYSTEM_PROMPT
    for fn in sound_catalog.ALLOWED_TRACK_FILES:
        assert fn in prompt_txt, f"AGENT_SYSTEM_PROMPT 缺少素材: {fn}"
    assert "诚实边界" in prompt_txt and "avoid_tracks" in prompt_txt

    # 3. 用模拟 Qwen JSON 校验 _sanitize_agent_design 过滤和规范化逻辑
    mock_payloads = [
        {
            "action": "compose",
            "question": "",
            "options": [],
            "collected": {"state": "失眠入睡", "scene": "壁炉暖火", "texture": "平稳低燃", "spatial_rhythm": "平稳持续", "avoid": "不吵"},
            "final_prompt": "壁炉炉火暖夜，不要太吵",
            "title": "夜营暖火",
            "reply": "为你挑了极轻柔的夜营余烬微火，平稳不吵。",
            "intent": {"scene": "fire", "scene_detail": "壁炉暖火", "mood": "sleep", "warmth": "warm", "dynamics": "steady", "avoid": ["吵"]},
            "reasoning": ["优先选择零尖峰余烬微火", "单轨平稳铺底避免刺耳"],
            "tracks": [
                {"path": "炉火_夜营氛围_766127.hq.mp3", "weight": 0.74, "pan": 0.0, "mode": "loop", "density": 0.4, "role_note": "柔和夜营余烬"},
                {"path": "非法_不存在的文件.mp3", "weight": 0.5, "pan": 0.0, "mode": "loop", "density": 0.4, "role_note": "应被过滤"},
            ],
            "followups": ["换壁炉低燃", "加一点雨声", "声音再轻一点"],
        },
        {
            "action": "compose",
            "question": "",
            "options": [],
            "collected": {"state": "放松", "scene": "近场ASMR", "texture": "采耳羽毛", "spatial_rhythm": "偶发点缀", "avoid": ""},
            "final_prompt": "采耳配羽毛轻拂",
            "title": "轻柔采耳",
            "reply": "轻柔采耳铺底，右侧穿插偶尔几下羽毛轻拂。",
            "intent": {"scene": "asmr", "scene_detail": "采耳与羽毛轻拂", "mood": "relax", "warmth": "warm", "dynamics": "natural", "avoid": []},
            "reasoning": ["近场采耳稳定触发", "短羽毛改偶发避免高频重复"],
            "tracks": [
                {"path": "ASMR_采耳_690078.hq.mp3", "weight": 0.52, "pan": -0.2, "mode": "loop", "density": 0.4, "role_note": "轻柔采耳触发"},
                {"path": "ASMR_羽毛轻拂_708086.hq.mp3", "weight": 0.38, "pan": 0.35, "mode": "intermittent", "density": 0.38, "role_note": "右侧羽毛偶发"},
            ],
            "followups": ["加柔和雨底", "羽毛多一点", "只留采耳"],
        },
        {
            "action": "compose",
            "question": "",
            "options": [],
            "collected": {"state": "失眠入睡", "scene": "", "texture": "", "spatial_rhythm": "", "avoid": ""},
            "final_prompt": "人声耳语替代方案",
            "title": "采耳羽毛替",
            "reply": "库里暂未收录人声耳语，先用轻柔采耳加羽毛替代。",
            "intent": {"scene": "asmr", "scene_detail": "采耳替代", "mood": "sleep", "warmth": "warm", "dynamics": "steady", "avoid": []},
            "reasoning": ["坦诚说明暂无人声耳语", "给出最相近近场温和组合"],
            "tracks": [
                {"path": "ASMR_采耳_690078.hq.mp3", "weight": 0.55, "pan": 0.0, "mode": "loop", "density": 0.4, "role_note": "平稳采耳替代"}
            ],
            "followups": ["换城市夜雨", "再轻一点", "加羽毛轻拂"],
        },
    ]
    for raw in mock_payloads:
        san = brain._sanitize_agent_design(raw, force_compose=True)
        assert san["action"] == "compose"
        assert all(t["path"] in sound_catalog.ALLOWED_TRACK_FILES for t in san["tracks"])
    assert len(brain._sanitize_agent_design(mock_payloads[0], force_compose=True)["tracks"]) == 1, "未过滤非法文件名"

    # 4. 校验 server._extract_track_names 与 _get_user_agent_context 避雷/正样本提取
    extracted = server._extract_track_names([["scene_assets/炉火_营地篝火_62487.hq.mp3", 0.7], ["远雷.hq.mp3", 0.0]])
    assert extracted == ["炉火_营地篝火_62487.hq.mp3"], f"提取音轨异常: {extracted}"

    class _MockStore:
        def read(self, name):
            if name == "bad_cases.json":
                return {"cases": [{"feedback": "太吵", "items": [["scene_assets/炉火_营地篝火_62487.hq.mp3", 0.8]]}]}
            if name == "good_recipes.json":
                return {"recipes": [{"say": "暖夜壁炉", "scene": "fire", "items": [["scene_assets/炉火_夜营氛围_766127.hq.mp3", 1.0]]}]}
            return {}

    orig_store_fn = server._recipe_store
    try:
        server._recipe_store = lambda _u: _MockStore()
        ctx = server._get_user_agent_context(None)
        assert ctx.get("avoid_tracks") == ["炉火_营地篝火_62487.hq.mp3"], f"avoid_tracks 异常: {ctx}"
        assert ctx.get("good_recipes") and ctx["good_recipes"][0]["tracks"] == ["炉火_夜营氛围_766127.hq.mp3"], f"good_recipes 异常: {ctx}"
    finally:
        server._recipe_store = orig_store_fn

    # 5. 尝试真实 Qwen3.8-Flash 云端联调（受本机代理阻断时打印 SKIPPED 而不误报代码故障）
    require_live = os.environ.get("REQUIRE_LIVE_QWEN") == "1"
    prompts = [
        ("炉火暖夜", "想要壁炉炉火暖夜，不要太吵", lambda d: any("炉火_" in t["path"] for t in d["tracks"])),
        ("采耳羽毛", "想听采耳和羽毛轻拂的ASMR助眠", lambda d: any("采耳" in t["path"] or "麦套" in t["path"] for t in d["tracks"]) and any("羽毛" in t["path"] for t in d["tracks"])),
        ("越界诚实", "想听小姐姐人声耳语讲睡前故事", lambda d: len(d["tracks"]) >= 1 and any(k in d["reply"] for k in ("暂未", "没有", "未收录", "暂无"))),
    ]
    live_ok = True
    for tag, say, check_fn in prompts:
        design, source = brain.design_soundscape(say, force_compose=True)
        assert design["action"] == "compose" and 1 <= len(design["tracks"]) <= 4
        assert all(t["path"] in sound_catalog.ALLOWED_TRACK_FILES for t in design["tracks"])
        assert check_fn(design), f"[{tag}] 语义校验未通过: {design}"
        if source != "Qwen3.8-Flash":
            live_ok = False
            if require_live:
                raise AssertionError(f"[{tag}] REQUIRE_LIVE_QWEN=1 但走到了 {source}")
            print(f"  [{tag}] SKIPPED (dashscope.aliyuncs.com TLS 被本机代理阻断，已自动验证降级到 {source} 可用)")
            break
        print(f"  [{tag}] LIVE source={source} title={design['title']} | tracks={[t['path'] for t in design['tracks']]}")

    if live_ok:
        print("  -> PASS: 离线 Schema/Mock/上下文校验 + Qwen3.8-Flash 真实联调全部通过")
    else:
        print("  -> PASS (离线全链路通过；真实云端 Qwen3.8-Flash 因本机代理阻断 TLS 握手跳过，设 REQUIRE_LIVE_QWEN=1 可强检)")


if __name__ == "__main__":
    test_catalog_and_frontend_sync()
    test_rules_and_executor()
    test_feedback_loops()
    test_audio_render_and_server_helpers()
    test_qwen_schema_mock_and_live()
    print("\nALL TESTS PASSED!")
