# 记忆系统："越用越懂你"靠本地 JSON / 用户数据库，不靠训练模型
# 三类数据：
#   preferences.json  - 用户长期口味画像
#   good_recipes.json - 验证过满意的"需求 → 配方"
#   bad_cases.json    - 被否决的配方和原因
# 存储可注入：默认读写本地 JSON（游客）；登录用户传入 store，改存数据库按人隔离。
# 用最朴素的 json 读写，用户能直接打开看懂和改。

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
MEM_DIR = os.path.join(BASE, "memory")


class FileStore:
    # 游客：存本地 JSON 文件
    def read(self, name):
        if not os.path.isdir(MEM_DIR):
            os.makedirs(MEM_DIR)
        path = os.path.join(MEM_DIR, name)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write(self, name, data):
        if not os.path.isdir(MEM_DIR):
            os.makedirs(MEM_DIR)
        path = os.path.join(MEM_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class DbStore:
    # 登录用户：存 SQLite，按 user_id 隔离
    def __init__(self, user_id):
        self.user_id = user_id

    def read(self, name):
        import auth_db
        return auth_db.load_memory(self.user_id, name)

    def write(self, name, data):
        import auth_db
        auth_db.save_memory(self.user_id, name, data)


def read_file(name):
    return FileStore().read(name)


def write_file(name, data):
    FileStore().write(name, data)


def save_preferences(intent, store=None):
    s = store or FileStore()
    pref = s.read("preferences.json")
    if "counts" not in pref:
        pref["counts"] = {}

    def bump(key, value):
        field = key + "_" + str(value)
        counts = pref["counts"]
        if field not in counts:
            counts[field] = 0
        counts[field] = counts[field] + 1

    bump("scene", intent.get("scene"))
    bump("mood", intent.get("mood"))
    bump("warmth", intent.get("warmth"))
    bump("dynamics", intent.get("dynamics"))
    s.write("preferences.json", pref)
    return pref


def save_good_recipe(say, intent, items, store=None):
    s = store or FileStore()
    data = s.read("good_recipes.json")
    if "recipes" not in data:
        data["recipes"] = []
    recipe = {
        "say": say,
        "scene": intent.get("scene"),
        "warmth": intent.get("warmth"),
        "dynamics": intent.get("dynamics"),
        "avoid": intent.get("avoid", []),
        "items": items
    }
    data["recipes"].append(recipe)
    s.write("good_recipes.json", data)
    return recipe


def save_bad_case(say, feedback, items, store=None):
    s = store or FileStore()
    data = s.read("bad_cases.json")
    if "cases" not in data:
        data["cases"] = []
    case = {"say": say, "feedback": feedback, "items": items}
    data["cases"].append(case)
    s.write("bad_cases.json", data)
    return case


def recall_recipe(intent, store=None):
    s = store or FileStore()
    data = s.read("good_recipes.json")
    recipes = data.get("recipes", [])
    for r in recipes:
        if r.get("scene") == intent.get("scene") and r.get("warmth") == intent.get("warmth"):
            return r
    return None


def summary():
    pref = read_file("preferences.json")
    good = read_file("good_recipes.json")
    bad = read_file("bad_cases.json")
    print("== 记忆摘要 ==")
    counts = pref.get("counts", {})
    if counts:
        for k in counts:
            print("  " + k + " : " + str(counts[k]))
    else:
        print("  （口味画像为空）")
    print("  满意配方：" + str(len(good.get("recipes", []))) + " 条")
    print("  否决记录：" + str(len(bad.get("cases", []))) + " 条")


if os.environ.get("MEMORY_SELFTEST") == "1":
    test_intent = {"scene": "rain", "mood": "sleep", "warmth": "warm", "dynamics": "steady"}
    save_preferences(test_intent)
    save_good_recipe("暖一点的雨声", test_intent, [["母带", 0.6], ["柔和雨", 0.4]])
    save_bad_case("太吵的雨", "吵", [["大雨打树叶", 1.0]])
    found = recall_recipe(test_intent)
    print("召回配方：" + str(found is not None))
    summary()
