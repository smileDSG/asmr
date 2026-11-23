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
    import json
    conn = connect()
    row = conn.execute(
        "SELECT data FROM user_memory WHERE user_id=? AND kind=?",
        (user_id, kind)
    ).fetchone()
    conn.close()
    if not row:
        return {}
    return json.loads(row[0])


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
