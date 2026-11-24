# 用户账号与会话：SQLite 数据库 + 标准库密码哈希
# 安全做法依据 OWASP Password Storage Cheat Sheet（2026）：
#   - 密码绝不存明文，用慢哈希 PBKDF2-HMAC-SHA256
#   - 60 万次迭代，每个用户独立随机盐（16 字节）
#   - 全程参数化查询，防 SQL 注入
#   - 会话用随机 token，只存服务端，带过期时间
#   - 登录错误统一文案，防用户枚举；失败次数限制，防暴力破解
# 只用标准库，不装任何包。

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
DB_PATH = os.path.join(DATA_DIR, "users.db")

PBKDF2_ROUNDS = 600000      # OWASP 对 PBKDF2-HMAC-SHA256 的建议迭代数
SALT_BYTES = 16             # 每用户随机盐
TOKEN_BYTES = 32            # 会话 token 长度
SESSION_SECONDS = 7 * 24 * 3600   # 会话 7 天
MAX_FAILED = 5              # 连续失败 5 次锁定
LOCK_SECONDS = 15 * 60      # 锁定 15 分钟
MAX_PASSWORD_LEN = 128      # 限制过长密码，防 CPU 耗尽
MIN_PASSWORD_LEN = 8


def connect():
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")   # 并发读写更稳
    return conn


def init_db():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            user_id INTEGER NOT NULL,
            kind    TEXT NOT NULL,
            data    TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (user_id, kind),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            username   TEXT PRIMARY KEY,
            failed     INTEGER NOT NULL,
            locked_until REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS community_posts (
            id                TEXT PRIMARY KEY,
            user_id           INTEGER,
            author            TEXT NOT NULL,
            title             TEXT NOT NULL,
            story             TEXT NOT NULL DEFAULT '',
            grp               TEXT NOT NULL DEFAULT '自然',
            items_json        TEXT NOT NULL,
            remix_policy      TEXT NOT NULL DEFAULT 'star_to_fork',
            parent_post_id    TEXT NOT NULL DEFAULT '',
            root_post_id      TEXT NOT NULL DEFAULT '',
            remix_of_json     TEXT NOT NULL DEFAULT '',
            diff_summary_json TEXT NOT NULL DEFAULT '[]',
            recipe_hash       TEXT NOT NULL DEFAULT '',
            version           INTEGER NOT NULL DEFAULT 1,
            delete_token      TEXT NOT NULL DEFAULT '',
            created_at        REAL NOT NULL,
            updated_at        REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS community_vote_counts (
            post_id TEXT NOT NULL,
            tag     TEXT NOT NULL,
            count   INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (post_id, tag)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS community_user_votes (
            voter_key  TEXT NOT NULL,
            post_id    TEXT NOT NULL,
            tag        TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (voter_key, post_id, tag)
        )
    """)
    # 短评论：不建树、不盖楼、不支持回复，保持睡前安静
    conn.execute("""
        CREATE TABLE IF NOT EXISTS community_comments (
            id         TEXT PRIMARY KEY,
            post_id    TEXT NOT NULL,
            user_id    INTEGER NOT NULL,
            author     TEXT NOT NULL,
            body       TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY(post_id) REFERENCES community_posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_post
        ON community_comments(post_id, created_at)
    """)
    conn.commit()
    conn.close()


def hash_password(password):
    # 返回：迭代数$盐(hex)$哈希(hex)，参数随哈希一起存，方便以后升级
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS
    )
    return "pbkdf2_sha256$%d$%s$%s" % (
        PBKDF2_ROUNDS, salt.hex(), digest.hex()
    )


def verify_password(password, stored):
    # 用库里的 salt 和迭代数重算，constant-time 比较防时序攻击
    try:
        algo, rounds, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(rounds)
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def valid_username(username):
    if not isinstance(username, str):
        return False
    n = username.strip()
    return 2 <= len(n) <= 32 and all(c.isalnum() or c in "_-" for c in n)


def valid_password(password):
    if not isinstance(password, str):
        return False
    return MIN_PASSWORD_LEN <= len(password) <= MAX_PASSWORD_LEN


def register(username, password):
    # 返回 (ok, message)
    username = (username or "").strip()
    if not valid_username(username):
        return False, "用户名需 2-32 位，只能用字母数字下划线和短横线"
    if not valid_password(password):
        return False, "密码需 8-128 位"

    conn = connect()
    try:
        conn.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES(?,?,?)",
            (username, hash_password(password), time.time())
        )
        conn.commit()
        return True, "注册成功"
    except sqlite3.IntegrityError:
        return False, "这个用户名已被占用"
    finally:
        conn.close()


def is_locked(conn, username):
    row = conn.execute(
        "SELECT failed, locked_until FROM login_attempts WHERE username=?",
        (username,)
    ).fetchone()
    if not row:
        return False
    failed, locked_until = row
    if locked_until > time.time():
        return True
    if failed >= MAX_FAILED and locked_until <= time.time():
        # 锁定时间到了，清零重新开始
        conn.execute("DELETE FROM login_attempts WHERE username=?", (username,))
        conn.commit()
    return False


def note_failed(conn, username):
    row = conn.execute(
        "SELECT failed FROM login_attempts WHERE username=?", (username,)
    ).fetchone()
    failed = (row[0] if row else 0) + 1
    locked_until = time.time() + LOCK_SECONDS if failed >= MAX_FAILED else 0
    conn.execute("""
        INSERT INTO login_attempts(username, failed, locked_until) VALUES(?,?,?)
        ON CONFLICT(username) DO UPDATE SET failed=excluded.failed,
        locked_until=excluded.locked_until
    """, (username, failed, locked_until))
    conn.commit()


def login(username, password):
    # 返回 (user_dict 或 None, message)
    # 错误文案统一，避免告诉对方"用户名不存在"还是"密码错了"
    generic = "用户名或密码不对"
    username = (username or "").strip()
    conn = connect()
    try:
        if is_locked(conn, username):
            return None, "尝试次数太多，请 15 分钟后再试"
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username=?",
            (username,)
        ).fetchone()
        if not row or not verify_password(password or "", row[2]):
            note_failed(conn, username)
            return None, generic
        conn.execute("DELETE FROM login_attempts WHERE username=?", (username,))
        conn.commit()
        return {"id": row[0], "username": row[1]}, "登录成功"
    finally:
        conn.close()


def create_session(user_id):
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = time.time()
    conn = connect()
    conn.execute(
        "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES(?,?,?,?)",
        (token, user_id, now, now + SESSION_SECONDS)
    )
    conn.commit()
    conn.close()
    return token


def user_from_token(token):
    if not token:
        return None
    conn = connect()
    row = conn.execute("""
        SELECT u.id, u.username FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token=? AND s.expires_at > ?
    """, (token, time.time())).fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "username": row[1]}


def logout(token):
    if not token:
        return
    conn = connect()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()


def save_memory(user_id, kind, data):
    import json
    conn = connect()
    conn.execute("""
        INSERT INTO user_memory(user_id, kind, data, updated_at) VALUES(?,?,?,?)
        ON CONFLICT(user_id, kind) DO UPDATE SET data=excluded.data,
        updated_at=excluded.updated_at
    """, (user_id, kind, json.dumps(data, ensure_ascii=False), time.time()))
    conn.commit()
    conn.close()


def load_memory(user_id, kind):
    conn = connect()
    row = conn.execute(
        "SELECT data FROM user_memory WHERE user_id=? AND kind=?",
        (user_id, kind)
    ).fetchone()
    conn.close()
    if not row:
        return {}
    return json.loads(row[0])


VALID_REMIX_POLICIES = ("open", "star_to_fork", "listen_only")
ALLOWED_VOTE_TAGS = ("steady", "warm", "crisp", "deep", "borrow")


def _track_key(item):
    raw = str(item.get("path") or item.get("rel") or "").strip()
    return os.path.basename(raw)


def _round_step(val, step):
    return round(round(float(val or 0.0) / step) * step, 2)


def normalize_recipe_hash(items):
    """Build deterministic short fingerprint so near-identical remixes are detected."""
    normalized = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        key = _track_key(it)
        if not key:
            continue
        normalized.append({
            "path": key,
            "weight": _round_step(it.get("weight", 0.0), 0.05),
            "pan": round(float(it.get("pan", 0.0) or 0.0), 1),
            "mode": "intermittent" if it.get("mode") == "intermittent" else "loop",
            "density": round(float(it.get("density", 0.4) or 0.4), 1),
        })
    normalized.sort(key=lambda x: x["path"])
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_recipe_diff(parent_items, new_items, label_fn=None):
    """Compare parent vs new recipe items and return up to 5 concise Chinese diff strings."""
    def name_of(path_key):
        if callable(label_fn):
            lbl = label_fn(path_key)
            if lbl:
                return str(lbl)
        return os.path.splitext(path_key)[0]

    def to_map(items):
        out = {}
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            k = _track_key(it)
            if not k:
                continue
            out[k] = {
                "weight": float(it.get("weight", 0.0) or 0.0),
                "pan": float(it.get("pan", 0.0) or 0.0),
                "mode": "intermittent" if it.get("mode") == "intermittent" else "loop",
                "density": float(it.get("density", 0.4) or 0.4),
            }
        return out

    old_map = to_map(parent_items)
    new_map = to_map(new_items)
    diffs = []

    for k, n_it in new_map.items():
        if k not in old_map:
            pct = int(round(n_it["weight"] * 100))
            diffs.append(f"+ {name_of(k)} {pct}%")
            continue
        o_it = old_map[k]
        lbl = name_of(k)
        if abs(n_it["weight"] - o_it["weight"]) >= 0.05:
            old_pct = int(round(o_it["weight"] * 100))
            new_pct = int(round(n_it["weight"] * 100))
            diffs.append(f"{lbl} {old_pct}% → {new_pct}%")
        if n_it["mode"] != o_it["mode"]:
            mode_txt = "偶发" if n_it["mode"] == "intermittent" else "持续"
            diffs.append(f"{lbl} 切换为{mode_txt}")
        if abs(n_it["pan"] - o_it["pan"]) >= 0.15:
            diffs.append(f"{lbl} 声像调整")
        elif n_it["mode"] == "intermittent" and abs(n_it["density"] - o_it["density"]) >= 0.15:
            diffs.append(f"{lbl} 偶发频率调整")

    for k in old_map:
        if k not in new_map:
            diffs.append(f"- {name_of(k)}")

    return diffs[:5]


def _row_to_post(row):
    if not row:
        return None
    try:
        items = json.loads(row[6] or "[]")
    except Exception:
        items = []
    try:
        remix_of = json.loads(row[10]) if row[10] else None
    except Exception:
        remix_of = None
    try:
        diff_summary = json.loads(row[11] or "[]")
    except Exception:
        diff_summary = []
    return {
        "id": row[0],
        "user_id": row[1],
        "author": row[2],
        "title": row[3],
        "story": row[4] or "",
        "group": row[5] or "自然",
        "items": items if isinstance(items, list) else [],
        "remix_policy": row[7] if row[7] in VALID_REMIX_POLICIES else "star_to_fork",
        "parent_post_id": row[8] or "",
        "root_post_id": row[9] or "",
        "remix_of": remix_of if isinstance(remix_of, dict) else None,
        "diff_summary": diff_summary if isinstance(diff_summary, list) else [],
        "recipe_hash": row[12] or "",
        "version": int(row[13] or 1),
        "delete_token": row[14] or "",
        "created_at": float(row[15] or 0),
        "updated_at": float(row[16] or 0),
    }


_POST_COLS = (
    "id, user_id, author, title, story, grp, items_json, remix_policy, "
    "parent_post_id, root_post_id, remix_of_json, diff_summary_json, "
    "recipe_hash, version, delete_token, created_at, updated_at"
)


def create_community_post(post_dict):
    now = float(post_dict.get("created_at") or time.time())
    updated = float(post_dict.get("updated_at") or now)
    items = post_dict.get("items") or []
    policy = post_dict.get("remix_policy") or "star_to_fork"
    if policy not in VALID_REMIX_POLICIES:
        policy = "star_to_fork"
    remix_of = post_dict.get("remix_of")
    diff_summary = post_dict.get("diff_summary") or []
    recipe_hash = post_dict.get("recipe_hash") or normalize_recipe_hash(items)

    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO community_posts(
                id, user_id, author, title, story, grp, items_json, remix_policy,
                parent_post_id, root_post_id, remix_of_json, diff_summary_json,
                recipe_hash, version, delete_token, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                post_dict["id"],
                post_dict.get("user_id"),
                post_dict.get("author") or "深夜旅人",
                post_dict.get("title") or "我的夜息声景",
                post_dict.get("story") or "",
                post_dict.get("group") or post_dict.get("grp") or "自然",
                json.dumps(items, ensure_ascii=False),
                policy,
                post_dict.get("parent_post_id") or "",
                post_dict.get("root_post_id") or "",
                json.dumps(remix_of, ensure_ascii=False) if remix_of else "",
                json.dumps(diff_summary, ensure_ascii=False),
                recipe_hash,
                int(post_dict.get("version") or 1),
                post_dict.get("delete_token") or "",
                now,
                updated,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_community_post_raw(post_dict["id"])


def get_community_post_raw(post_id):
    if not post_id:
        return None
    conn = connect()
    row = conn.execute(
        f"SELECT {_POST_COLS} FROM community_posts WHERE id=?",
        (post_id,),
    ).fetchone()
    conn.close()
    return _row_to_post(row)


def list_community_posts_raw(limit=100):
    conn = connect()
    rows = conn.execute(
        f"SELECT {_POST_COLS} FROM community_posts ORDER BY created_at DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    conn.close()
    return [_row_to_post(r) for r in rows]


def list_forks_of(post_id):
    if not post_id:
        return []
    conn = connect()
    rows = conn.execute(
        f"""
        SELECT {_POST_COLS} FROM community_posts
        WHERE (parent_post_id=? OR root_post_id=?) AND id != ?
        ORDER BY created_at DESC
        """,
        (post_id, post_id, post_id),
    ).fetchall()
    conn.close()
    return [_row_to_post(r) for r in rows]


def get_fork_counts_map():
    """Return {post_id: fork_count} counting direct and root descendants per post."""
    conn = connect()
    rows = conn.execute(
        "SELECT id, parent_post_id, root_post_id FROM community_posts"
    ).fetchall()
    conn.close()
    sets = {}
    for pid, parent_id, root_id in rows:
        if parent_id and parent_id != pid:
            sets.setdefault(parent_id, set()).add(pid)
        if root_id and root_id != pid:
            sets.setdefault(root_id, set()).add(pid)
    return {k: len(v) for k, v in sets.items()}


def list_comments(post_id, limit=100):
    """按时间正序列出某配方的短评论。"""
    if not post_id:
        return []
    conn = connect()
    rows = conn.execute(
        """
        SELECT id, post_id, user_id, author, body, created_at
        FROM community_comments WHERE post_id=?
        ORDER BY created_at ASC LIMIT ?
        """,
        (post_id, int(limit)),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "id": r[0], "post_id": r[1], "user_id": r[2],
            "author": r[3], "body": r[4], "created_at": r[5],
        })
    return out


def add_comment(post_id, user_id, author, body, allow_builtin=False):
    """新增一条短评论，返回新增的评论；配方不存在时返回 None。
    allow_builtin=True 时允许给官方示例（不在 posts 表里）留言。"""
    conn = connect()
    try:
        exists = conn.execute(
            "SELECT 1 FROM community_posts WHERE id=?", (post_id,)
        ).fetchone()
        if not exists and not allow_builtin:
            return None
        cid = "c_" + secrets.token_hex(5)
        now = time.time()
        conn.execute(
            """
            INSERT INTO community_comments
            (id, post_id, user_id, author, body, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cid, post_id, user_id, author, body, now),
        )
        conn.commit()
        return {
            "id": cid, "post_id": post_id, "user_id": user_id,
            "author": author, "body": body, "created_at": now,
        }
    finally:
        conn.close()


def delete_comment(comment_id, user_id):
    """只让作者本人删自己的评论。"""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT user_id FROM community_comments WHERE id=?", (comment_id,)
        ).fetchone()
        if not row:
            return False, 404, "评论不存在"
        if row[0] != user_id:
            return False, 403, "只能删除自己的评论"
        conn.execute("DELETE FROM community_comments WHERE id=?", (comment_id,))
        conn.commit()
        return True, 200, "已删除"
    finally:
        conn.close()


def get_comment_counts():
    """返回 {post_id: 评论数}，广场卡片上一并显示。"""
    conn = connect()
    rows = conn.execute(
        "SELECT post_id, COUNT(*) FROM community_comments GROUP BY post_id"
    ).fetchall()
    conn.close()
    return {r[0]: int(r[1]) for r in rows}


def get_creator_summary(author):
    """某作者的作品数与累计被借走/被改编次数（按昵称聚合，游客也能看）。"""
    conn = connect()
    try:
        rows = conn.execute(
            f"SELECT {_POST_COLS} FROM community_posts WHERE author=? ORDER BY created_at DESC",
            (author,),
        ).fetchall()
        post_ids = [r[0] for r in rows]
        # _POST_COLS 顺序：0=id 3=title 5=grp 15=created_at
        first_ts = min((r[15] for r in rows), default=0)
    finally:
        conn.close()
    borrow = 0
    fork = 0
    if post_ids:
        conn = connect()
        try:
            marks = ",".join("?" for _ in post_ids)
            vrow = conn.execute(
                f"SELECT COALESCE(SUM(count),0) FROM community_vote_counts WHERE tag='borrow' AND post_id IN ({marks})",
                tuple(post_ids),
            ).fetchone()
            borrow = int(vrow[0] or 0)
            for pid in post_ids:
                fork += len(list_forks_of(pid))
        finally:
            conn.close()
    works = []
    for r in rows:
        works.append({
            "id": r[0], "title": r[3], "author": r[2],
            "grp": r[5], "created_at": r[15],
        })
    return {
        "author": author,
        "since": first_ts,
        "post_count": len(works),
        "borrow_count": borrow,
        "fork_count": fork,
        "works": works,
    }


def update_community_post_policy(post_id, user_id, remix_policy):
    if remix_policy not in VALID_REMIX_POLICIES:
        return False, "无效的配方许可"
    if not user_id:
        return False, "请先登录"
    conn = connect()
    try:
        row = conn.execute(
            "SELECT user_id FROM community_posts WHERE id=?",
            (post_id,),
        ).fetchone()
        if not row:
            return False, "配方不存在"
        if row[0] != user_id:
            return False, "没有权限修改配方许可"
        conn.execute(
            "UPDATE community_posts SET remix_policy=?, updated_at=? WHERE id=?",
            (remix_policy, time.time(), post_id),
        )
        conn.commit()
        return True, "已更新配方许可"
    finally:
        conn.close()


def delete_community_post(post_id, user_id=None, delete_token=""):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT user_id, delete_token FROM community_posts WHERE id=?",
            (post_id,),
        ).fetchone()
        if not row:
            return False, 404, "配方不存在"
        owner_uid, stored_tok = row
        owner_ok = bool(user_id and owner_uid and user_id == owner_uid)
        token_ok = bool(
            delete_token
            and stored_tok
            and hmac.compare_digest(str(delete_token), str(stored_tok))
        )
        if not (owner_ok or token_ok):
            return False, 403, "没有删除权限"
        conn.execute("DELETE FROM community_posts WHERE id=?", (post_id,))
        conn.execute("DELETE FROM community_vote_counts WHERE post_id=?", (post_id,))
        conn.execute("DELETE FROM community_user_votes WHERE post_id=?", (post_id,))
        conn.execute("DELETE FROM community_comments WHERE post_id=?", (post_id,))
        conn.commit()
        return True, 200, "已删除"
    finally:
        conn.close()


def get_post_vote_counts(conn, post_id):
    rows = conn.execute(
        "SELECT tag, count FROM community_vote_counts WHERE post_id=?",
        (post_id,),
    ).fetchall()
    counts = {k: 0 for k in ALLOWED_VOTE_TAGS}
    for tag, cnt in rows:
        if tag in counts:
            counts[tag] = max(0, int(cnt or 0))
    return counts


def get_all_vote_counts():
    conn = connect()
    rows = conn.execute(
        "SELECT post_id, tag, count FROM community_vote_counts"
    ).fetchall()
    conn.close()
    out = {}
    for pid, tag, cnt in rows:
        if tag not in ALLOWED_VOTE_TAGS:
            continue
        entry = out.setdefault(pid, {k: 0 for k in ALLOWED_VOTE_TAGS})
        entry[tag] = max(0, int(cnt or 0))
    return out


def get_voter_votes(voter_key):
    if not voter_key:
        return set()
    conn = connect()
    rows = conn.execute(
        "SELECT post_id, tag FROM community_user_votes WHERE voter_key=?",
        (voter_key,),
    ).fetchall()
    conn.close()
    return {(r[0], r[1]) for r in rows}


def toggle_community_vote(post_id, tag, delta, voter_key=None):
    """Update vote count (with per-voter deduplication when voter_key is present).
    Returns (counts_dict, is_voted_on).
    """
    if tag not in ALLOWED_VOTE_TAGS:
        return {k: 0 for k in ALLOWED_VOTE_TAGS}, False
    delta = 1 if int(delta) >= 1 else -1

    conn = connect()
    try:
        voted_on = False
        if voter_key:
            exists = conn.execute(
                "SELECT 1 FROM community_user_votes WHERE voter_key=? AND post_id=? AND tag=?",
                (voter_key, post_id, tag),
            ).fetchone() is not None

            if delta == 1:
                voted_on = True
                if not exists:
                    conn.execute(
                        "INSERT INTO community_user_votes(voter_key, post_id, tag, created_at) VALUES(?,?,?,?)",
                        (voter_key, post_id, tag, time.time()),
                    )
                    conn.execute(
                        """
                        INSERT INTO community_vote_counts(post_id, tag, count) VALUES(?,?,1)
                        ON CONFLICT(post_id, tag) DO UPDATE SET count = MAX(0, count + 1)
                        """,
                        (post_id, tag),
                    )
            else:
                voted_on = False
                if exists:
                    conn.execute(
                        "DELETE FROM community_user_votes WHERE voter_key=? AND post_id=? AND tag=?",
                        (voter_key, post_id, tag),
                    )
                    conn.execute(
                        """
                        INSERT INTO community_vote_counts(post_id, tag, count) VALUES(?,?,0)
                        ON CONFLICT(post_id, tag) DO UPDATE SET count = MAX(0, count - 1)
                        """,
                        (post_id, tag),
                    )
        else:
            voted_on = delta == 1
            if delta == 1:
                conn.execute(
                    """
                    INSERT INTO community_vote_counts(post_id, tag, count) VALUES(?,?,1)
                    ON CONFLICT(post_id, tag) DO UPDATE SET count = MAX(0, count + 1)
                    """,
                    (post_id, tag),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO community_vote_counts(post_id, tag, count) VALUES(?,?,0)
                    ON CONFLICT(post_id, tag) DO UPDATE SET count = MAX(0, count - 1)
                    """,
                    (post_id, tag),
                )
        conn.commit()
        counts = get_post_vote_counts(conn, post_id)
        return counts, voted_on
    finally:
        conn.close()


def migrate_legacy_community(posts_list, votes_dict):
    """Idempotent import from legacy memory/*.json when SQLite tables are empty."""
    conn = connect()
    try:
        post_cnt = conn.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0]
        if post_cnt == 0 and isinstance(posts_list, list):
            for p in posts_list:
                if not isinstance(p, dict) or not p.get("id"):
                    continue
                items = p.get("items") or []
                remix_of = p.get("remix_of") if isinstance(p.get("remix_of"), dict) else None
                parent_id = str((remix_of or {}).get("id") or "")
                now = float(p.get("created_at") or time.time())
                conn.execute(
                    """
                    INSERT OR IGNORE INTO community_posts(
                        id, user_id, author, title, story, grp, items_json, remix_policy,
                        parent_post_id, root_post_id, remix_of_json, diff_summary_json,
                        recipe_hash, version, delete_token, created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(p["id"]),
                        p.get("user_id"),
                        str(p.get("author") or "深夜旅人"),
                        str(p.get("title") or "我的夜息声景"),
                        str(p.get("story") or ""),
                        str(p.get("group") or "自然"),
                        json.dumps(items, ensure_ascii=False),
                        p.get("remix_policy") if p.get("remix_policy") in VALID_REMIX_POLICIES else "star_to_fork",
                        parent_id,
                        parent_id,
                        json.dumps(remix_of, ensure_ascii=False) if remix_of else "",
                        json.dumps(p.get("diff_summary") or [], ensure_ascii=False),
                        normalize_recipe_hash(items),
                        int(p.get("version") or 1),
                        str(p.get("delete_token") or ""),
                        now,
                        now,
                    ),
                )

        vote_cnt = conn.execute("SELECT COUNT(*) FROM community_vote_counts").fetchone()[0]
        if vote_cnt == 0 and isinstance(votes_dict, dict):
            for pid, entry in votes_dict.items():
                if not isinstance(entry, dict):
                    continue
                for tag in ALLOWED_VOTE_TAGS:
                    cnt = max(0, int(entry.get(tag, 0) or 0))
                    if cnt > 0:
                        conn.execute(
                            "INSERT OR IGNORE INTO community_vote_counts(post_id, tag, count) VALUES(?,?,?)",
                            (str(pid), tag, cnt),
                        )
        conn.commit()
    finally:
        conn.close()


def get_user_hub_data(user_id, voter_key):
    conn = connect()
    try:
        my_posts = []
        if user_id:
            rows = conn.execute(
                f"SELECT {_POST_COLS} FROM community_posts WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            my_posts = [_row_to_post(r) for r in rows]

        starred_post_ids = []
        if voter_key:
            s_rows = conn.execute(
                """
                SELECT post_id FROM community_user_votes
                WHERE voter_key=? AND tag='borrow'
                ORDER BY created_at DESC
                """,
                (voter_key,),
            ).fetchall()
            starred_post_ids = [r[0] for r in s_rows]

        vote_counts = get_all_vote_counts()
        fork_counts = get_fork_counts_map()

        original_count = 0
        fork_count = 0
        total_stars_received = 0
        my_ids = set()
        for p in my_posts:
            my_ids.add(p["id"])
            is_fork = bool(p.get("parent_post_id")) or bool(
                isinstance(p.get("remix_of"), dict) and p["remix_of"].get("title")
            )
            if is_fork:
                fork_count += 1
            else:
                original_count += 1
            total_stars_received += int(vote_counts.get(p["id"], {}).get("borrow", 0))

        total_forks_received = 0
        if my_ids:
            placeholders = ",".join("?" for _ in my_ids)
            id_tuple = tuple(my_ids)
            row = conn.execute(
                f"""
                SELECT COUNT(DISTINCT id) FROM community_posts
                WHERE (parent_post_id IN ({placeholders}) OR root_post_id IN ({placeholders}))
                  AND id NOT IN ({placeholders})
                """,
                id_tuple + id_tuple + id_tuple,
            ).fetchone()
            total_forks_received = int(row[0] if row else 0)

        return {
            "stats": {
                "original_count": original_count,
                "fork_count": fork_count,
                "total_stars_received": total_stars_received,
                "total_forks_received": total_forks_received,
            },
            "my_posts": my_posts,
            "starred_post_ids": starred_post_ids,
            "fork_counts": fork_counts,
            "vote_counts": vote_counts,
        }
    finally:
        conn.close()


if os.environ.get("AUTH_SELFTEST") == "1":
    init_db()
    name = "selftest_" + secrets.token_hex(3)
    ok, msg = register(name, "goodpass123")
    print("注册:", ok, msg)
    user, msg = login(name, "goodpass123")
    print("正确密码:", user is not None, msg)
    bad, msg = login(name, "wrongpass")
    print("错误密码:", bad is None, msg)
    token = create_session(user["id"])
    print("会话有效:", user_from_token(token) is not None)
    logout(token)
    print("登出后失效:", user_from_token(token) is None)
    save_memory(user["id"], "preferences", {"counts": {"scene_rain": 2}})
    print("记忆读写:", load_memory(user["id"], "preferences"))
