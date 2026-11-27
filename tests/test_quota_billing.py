"""End-to-end tests for unified quota, anti-abuse, pay-to-unlock, and NowPay reserve/commit."""

import concurrent.futures
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE, "backend")
sys.path.insert(0, BASE)
sys.path.insert(0, BACKEND_DIR)


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http(url, method="GET", body=None, headers=None):
    hdrs = {"User-Agent": "yexi-quota-test/1.0"}
    if headers:
        hdrs.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with _OPENER.open(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read()
        e.close()
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception:
            parsed = {"raw": raw.decode("utf-8", errors="replace")}
        return e.code, parsed


def _submit_and_wait(base, payload, headers):
    code, res = _http(base + "/api/task/submit", method="POST", body=payload, headers=headers)
    if code != 200 or not res.get("taskId"):
        return code, res
    tid = res["taskId"]
    for _ in range(80):
        sc, st = _http(base + "/api/task/status?id=" + tid, headers=headers)
        if sc != 200:
            return sc, st
        state = st.get("state")
        if state == "done":
            return 200, st.get("result") or {}
        if state == "failed":
            result = st.get("result") or {"_task_error": st.get("error", "")}
            out_code = 402 if result.get("action") == "quota" else 400
            return out_code, result
        time.sleep(0.1)
    raise AssertionError("task timed out: " + tid)


def _extract_order_no(pay_url):
    assert "order=" in pay_url, f"missing order= in {pay_url}"
    return pay_url.split("order=", 1)[1].split("&", 1)[0]


def run_http_suite():
    tmpdir = tempfile.mkdtemp(prefix="yexi_quota_test_")
    db_path = os.path.join(tmpdir, "users.db")
    port = _find_free_port()
    base = f"http://127.0.0.1:{port}"

    # Spawn a small launcher so we can isolate auth_db.DB_PATH, disable Qwen external calls,
    # and raise rate_limit generate limit in-process without altering real data/users.db.
    launcher = os.path.join(tmpdir, "run_test_server.py")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write(
            f"""
import os, sys, runpy
sys.path.insert(0, {repr(BASE)})
sys.path.insert(0, {repr(BACKEND_DIR)})
import auth_db, rate_limit, understanding_brain
auth_db.DATA_DIR = {repr(tmpdir)}
auth_db.DB_PATH = {repr(db_path)}
auth_db.init_db()
rate_limit.RULES["generate"] = (60, 200)
# Force deterministic local rules only so tests are fast and offline-safe
def _offline(*a, **kw):
    raise RuntimeError("offline test mode")
understanding_brain.qwen_client.design_soundscape = _offline
understanding_brain.qwen_client.understand = _offline
os.environ["PORT"] = {repr(str(port))}
os.environ["YEXI_PAY_MODE"] = "mock"
os.environ["YEXI_NOWPAY"] = "0"
runpy.run_path(os.path.join({repr(BASE)}, "server.py"), run_name="__main__")
"""
        )

    log_path = os.path.join(tmpdir, "server.log")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [sys.executable, launcher],
        cwd=BASE,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        ready = False
        last_err = ""
        for _ in range(80):
            if proc.poll() is not None:
                log_file.flush()
                with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                    out = lf.read()
                raise AssertionError(f"test server died ({proc.returncode}):\n{out}")
            try:
                c, h = _http(base + "/api/health")
                if c == 200 and h.get("ok"):
                    ready = True
                    break
                last_err = f"status={c}, body={h}"
            except Exception as ex:
                last_err = repr(ex)
            time.sleep(0.25)
        if not ready:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            log_file.flush()
            with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                out = lf.read()
            raise AssertionError(f"timed out waiting for test server (last_err={last_err}):\n{out}")

        # 1. Guest initial quota = 2
        g1_hdr = {"X-Yexi-Client": "guest_alpha_1"}
        c, q = _http(base + "/api/quota", headers=g1_hdr)
        assert c == 200 and q["free_left"] == 2 and q["total_left"] == 2, q

        # 2. ask & blocked do NOT consume quota
        c, r_ask = _submit_and_wait(base, {"say": "睡不着", "seconds": 5}, g1_hdr)
        assert c == 200 and r_ask["action"] == "ask", r_ask
        assert r_ask["quota"]["free_left"] == 2, r_ask

        c, r_blk = _submit_and_wait(base, {"say": "帮我写一份Python冒泡排序代码", "seconds": 5}, g1_hdr)
        assert c in (200, 400) and r_blk["action"] == "blocked", r_blk
        c, q = _http(base + "/api/quota", headers=g1_hdr)
        assert q["free_left"] == 2, q

        # 3. Guest uses 1st free generation -> gets lineage_id with 3 free edits
        c, r1 = _submit_and_wait(base, {"say": "窗外暖一点的夜雨", "force_compose": True, "seconds": 5}, g1_hdr)
        assert c == 200 and r1["action"] == "compose" and r1["quota"]["free_left"] == 1, r1
        assert r1.get("free_edits_left") == 3 and r1.get("billing_mode") == "new" and r1.get("lineage_id"), r1

        # 4. Fake lineage_id + current_tracks MUST still deduct the 2nd free quota (no free edit bypass!)
        c, r2 = _submit_and_wait(
            base,
            {
                "say": "加点夜风",
                "force_compose": True,
                "seconds": 5,
                "lineage_id": "fake_lineage_123456",
                "current_tracks": r1["tracks"],
            },
            g1_hdr,
        )
        assert c == 200 and r2["action"] == "compose" and r2["quota"]["free_left"] == 0 and r2.get("billing_mode") == "new", r2

        # 3rd generation hits 402
        c, r3 = _submit_and_wait(base, {"say": "远海浪", "force_compose": True, "seconds": 5}, g1_hdr)
        assert c == 402 and r3["action"] == "quota" and r3["need_pay"] and r3["product_id"] == "trial3", r3

        # 5. /api/feedback (non-like adjustment) MUST also be blocked by quota
        c, r_fb = _http(
            base + "/api/feedback",
            method="POST",
            body={"feedback": "太吵了", "seconds": 5, "items": r2["tracks"]},
            headers=g1_hdr,
        )
        assert c == 402 and r_fb["action"] == "quota", r_fb

        # 6. Clearing X-Yexi-Client (incognito / new device) on same IP STILL blocked
        g2_hdr = {"X-Yexi-Client": "guest_fresh_cleared"}
        c, q2 = _http(base + "/api/quota", headers=g2_hdr)
        assert c == 200 and q2["free_left"] == 0 and q2["total_left"] == 0, q2
        c, r4 = _submit_and_wait(base, {"say": "山涧溪流", "force_compose": True, "seconds": 5}, g2_hdr)
        assert c == 402 and r4["action"] == "quota", r4

        # 7. Register + Login as g1_hdr inherits used=2 (still 0 free left)
        c, reg = _http(base + "/api/register", method="POST", body={"username": "tester01", "password": "Password123!"}, headers=g1_hdr)
        assert c == 200 and reg["ok"], reg
        c, log = _http(base + "/api/login", method="POST", body={"username": "tester01", "password": "Password123!"}, headers=g1_hdr)
        assert c == 200 and log["ok"], log
        u1_hdr = {"Authorization": "Bearer " + log["token"], "X-Yexi-Client": "brand_new_device_after_login"}
        c, q_u1 = _http(base + "/api/quota", headers=u1_hdr)
        assert c == 200 and q_u1["free_left"] == 0 and q_u1["paid_left"] == 0 and q_u1["total_left"] == 0, q_u1

        # 8. Buy trial3 (+3 generations + 30d full_library) -> exact 3 uses allowed, 4th blocked
        c, order = _http(base + "/api/pay/create", method="POST", body={"product_id": "trial3"}, headers=u1_hdr)
        assert c == 200 and order["pay_url"], order
        ono = _extract_order_no(order["pay_url"])
        c, mock_ok = _http(base + "/api/pay/mock_success", method="POST", body={"order": ono}, headers=u1_hdr)
        assert c == 200 and mock_ok["ok"], mock_ok

        c, q_paid = _http(base + "/api/quota", headers=u1_hdr)
        assert q_paid["free_left"] == 0 and q_paid["paid_left"] == 3 and q_paid["total_left"] == 3 and q_paid["unlocked"] is True and q_paid["unlimited"] is False, q_paid

        for idx in range(3):
            c, rp = _http(
                base + "/api/agent_chat",
                method="POST",
                body={"say": "炉火夜营", "force_compose": True, "seconds": 5},
                headers=u1_hdr,
            )
            assert c == 200 and rp["action"] == "compose", (idx, rp)
            assert rp["quota"]["paid_left"] == 2 - idx, rp
            assert rp["consumed_from"] == "local_paid", rp

        # 4th paid attempt -> 402
        c, rp4 = _http(
            base + "/api/agent_chat",
            method="POST",
            body={"say": "炉火夜营", "force_compose": True, "seconds": 5},
            headers=u1_hdr,
        )
        assert c == 402 and rp4["action"] == "quota", rp4

        # 9. Repeat purchase stacks +3
        c, order2 = _http(base + "/api/pay/create", method="POST", body={"product_id": "trial3"}, headers=u1_hdr)
        ono2 = _extract_order_no(order2["pay_url"])
        c, mock_ok2 = _http(base + "/api/pay/mock_success", method="POST", body={"order": ono2}, headers=u1_hdr)
        assert c == 200 and mock_ok2["ok"]
        c, q_stack = _http(base + "/api/quota", headers=u1_hdr)
        assert q_stack["paid_left"] == 3 and q_stack["total_left"] == 3, q_stack

        # 10. Concurrency + free-first-then-paid: buy +3 while having 2 free left -> 5 concurrent requests
        # Use a separate DB state? Reset today's IP quota directly in isolated test DB for user2
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM daily_quota")
        conn.commit()
        conn.close()

        c, reg2 = _http(base + "/api/register", method="POST", body={"username": "tester02", "password": "Password123!"})
        assert c == 200
        c, log2 = _http(base + "/api/login", method="POST", body={"username": "tester02", "password": "Password123!"})
        assert c == 200
        u2_hdr = {"Authorization": "Bearer " + log2["token"], "X-Yexi-Client": "u2_client_1"}

        # Consume 1 free so u2 has 1 free left, then buy trial3 (+3) => total 4
        c, u2_r1 = _http(base + "/api/generate", method="POST", body={"say": "窗外夜雨", "seconds": 5}, headers=u2_hdr)
        assert c == 200 and u2_r1["consumed_from"] == "free" and u2_r1["quota"]["free_left"] == 1, u2_r1
        c, ord_u2 = _http(base + "/api/pay/create", method="POST", body={"product_id": "trial3"}, headers=u2_hdr)
        _http(base + "/api/pay/mock_success", method="POST", body={"order": _extract_order_no(ord_u2["pay_url"])}, headers=u2_hdr)
        c, q_u2 = _http(base + "/api/quota", headers=u2_hdr)
        assert q_u2["free_left"] == 1 and q_u2["paid_left"] == 3 and q_u2["total_left"] == 4, q_u2

        # Fire 6 concurrent /api/generate requests when only 4 total left -> exactly 4 succeed, 2 get 402
        def _hit(_):
            return _http(base + "/api/generate", method="POST", body={"say": "森林夜风", "seconds": 5}, headers=u2_hdr)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(_hit, range(6)))
        ok_cnt = sum(1 for code, _ in results if code == 200)
        blk_cnt = sum(1 for code, _ in results if code == 402)
        assert ok_cnt == 4 and blk_cnt == 2, f"concurrency leak: {results}"
        c, q_u2_after = _http(base + "/api/quota", headers=u2_hdr)
        assert q_u2_after["free_left"] == 0 and q_u2_after["paid_left"] == 0 and q_u2_after["total_left"] == 0, q_u2_after

        # 11. Free user vs unlocked user catalog material access
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM daily_quota")
        conn.commit()
        conn.close()
        import sound_catalog
        free_files = {os.path.basename(p) for p in sound_catalog.FREE_RELPATHS}

        # Free user asking for premium tent rain -> downgraded to free tracks with notice
        c, r_free_mat = _http(
            base + "/api/agent_chat",
            method="POST",
            body={"say": "想听帐篷大雨", "force_compose": True, "seconds": 5},
            headers={"X-Yexi-Client": "free_mat_chk"},
        )
        assert c == 200 and r_free_mat["full_access"] is False and r_free_mat["catalog_downgraded"] is True, r_free_mat
        assert all(t["path"] in free_files for t in r_free_mat["tracks"]), r_free_mat
        assert "解锁全库" in r_free_mat["reply"], r_free_mat

        # Unlocked user (u1_hdr already bought trial3 above and still has 3 paid left) -> gets premium tent rain!
        c, r_prem_mat = _http(
            base + "/api/agent_chat",
            method="POST",
            body={"say": "想听帐篷大雨", "force_compose": True, "seconds": 5},
            headers=u1_hdr,
        )
        assert c == 200 and r_prem_mat["full_access"] is True and r_prem_mat["catalog_downgraded"] is False, r_prem_mat
        assert any(t["path"] == "帐篷雨_小帐篷大雨_592996.hq.mp3" for t in r_prem_mat["tracks"]), r_prem_mat

        # 12. Expired / free user can still replay previously saved premium recipe & stream its asset
        c, r_play = _http(
            base + "/api/play",
            method="POST",
            body={"title": "旧收藏", "seconds": 5, "items": [{"path": "帐篷雨_小帐篷大雨_592996.hq.mp3", "weight": 0.8}]},
            headers={"X-Yexi-Client": "expired_replay_chk"},
        )
        assert c == 200 and r_play.get("ok") and r_play.get("audio"), r_play
        req_asset = urllib.request.Request(base + "/api/asset?name=" + urllib.parse.quote("帐篷雨_小帐篷大雨_592996.hq.mp3"), headers={"Range": "bytes=0-1023"})
        with _OPENER.open(req_asset, timeout=15) as ar:
            assert ar.status in (200, 206) and len(ar.read()) > 0

        # 13. Core rule: 1 gen -> 3 free edits -> 1 quota buys 2 more edits -> exhausted 402
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM daily_quota")
        conn.commit()
        conn.close()
        g_lin = {"X-Yexi-Client": "lineage_rule_guest"}

        # Gen 1 (uses free #1, left=1, gets 3 free edits)
        c, lg1 = _submit_and_wait(base, {"say": "窗外暖夜雨", "force_compose": True, "seconds": 5}, g_lin)
        assert c == 200 and lg1["quota"]["free_left"] == 1 and lg1["free_edits_left"] == 3 and lg1["billing_mode"] == "new", lg1
        lid = lg1["lineage_id"]
        tracks_cur = lg1["tracks"]

        # Edits 1, 2, 3 -> free (quota stays free_left=1), free_edits_left goes 2 -> 1 -> 0
        for expected_left in (2, 1, 0):
            c, le = _submit_and_wait(
                base,
                {"say": "加点夜风", "force_compose": True, "seconds": 5, "lineage_id": lid, "current_tracks": tracks_cur},
                g_lin,
            )
            assert c == 200 and le["billing_mode"] == "free_edit" and le["consumed_from"] == "lineage_edit", le
            assert le["free_edits_left"] == expected_left and le["quota"]["free_left"] == 1, le
            tracks_cur = le["tracks"]

        # Edit 4 -> 3 free edits exhausted, so consumes free #2 (left=0) and grants 2 edits (1 used now + 1 left)!
        c, le4 = _submit_and_wait(
            base,
            {"say": "更柔一点", "force_compose": True, "seconds": 5, "lineage_id": lid, "current_tracks": tracks_cur},
            g_lin,
        )
        assert c == 200 and le4["billing_mode"] == "refill_edit" and le4["consumed_from"] == "free", le4
        assert le4["free_edits_left"] == 1 and le4["quota"]["free_left"] == 0, le4
        tracks_cur = le4["tracks"]

        # 14. Concurrency test when free_edits_left == 1 and total_left == 0 -> 3 concurrent edits -> exact 1 succeeds, 2 hit 402!
        def _hit_edit(_):
            return _http(
                base + "/api/agent_chat",
                method="POST",
                body={"say": "稳一点", "force_compose": True, "seconds": 5, "lineage_id": lid, "current_tracks": tracks_cur},
                headers=g_lin,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            ed_res = list(pool.map(_hit_edit, range(3)))
        ed_ok = [r for code, r in ed_res if code == 200]
        ed_402 = [r for code, r in ed_res if code == 402]
        assert len(ed_ok) == 1 and len(ed_402) == 2, ed_res
        assert ed_ok[0]["billing_mode"] == "free_edit" and ed_ok[0]["free_edits_left"] == 0, ed_ok[0]

        # Edit 6 -> neither edits nor quota left -> 402
        c, le6 = _http(
            base + "/api/agent_chat",
            method="POST",
            body={"say": "再轻一点", "force_compose": True, "seconds": 5, "lineage_id": lid, "current_tracks": tracks_cur},
            headers=g_lin,
        )
        assert c == 402 and le6["action"] == "quota", le6

        print("PASS: HTTP quota, anti-abuse, concurrency, full-library & 3+2 lineage suite (14 cases)")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        log_file.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_nowpay_and_refund_unit_suite():
    """Unit-test NowPay reserve/commit/inflight lock, expired 30d window, and render-failure refund."""
    tmpdir = tempfile.mkdtemp(prefix="yexi_nowpay_unit_")
    try:
        import auth_db
        import nowpay
        import pay_window
        import server

        orig_db_dir, orig_db_path = auth_db.DATA_DIR, auth_db.DB_PATH
        orig_pw_dir, orig_pw_store = pay_window.DATA_DIR, pay_window.STORE
        orig_np_enabled = nowpay.ENABLED
        orig_np_cfg = nowpay.products_config
        orig_np_quota = nowpay.quota_query
        orig_np_verify = nowpay.quota_verify
        orig_np_refresh = nowpay.quota_refresh
        orig_render = server.render
        orig_cur_user = server.current_user
        orig_design = server.understanding_brain.design_soundscape

        try:
            auth_db.DATA_DIR = tmpdir
            auth_db.DB_PATH = os.path.join(tmpdir, "users.db")
            auth_db.init_db()
            pay_window.DATA_DIR = tmpdir
            pay_window.STORE = os.path.join(tmpdir, "nowpay_first_paid.json")

            assert auth_db.register("npuser", "Password123!")[0]
            user, _ = auth_db.login("npuser", "Password123!")

            class FakeHandler:
                headers = {"X-Yexi-Client": "np_client_1"}
                client_address = ("10.0.0.88", 12345)

            h = FakeHandler()
            server.current_user = lambda _h: user

            # Exhaust free 2 first
            auth_db.reserve_free_quota(["u:" + str(user["id"]), "c:np_client_1", "ip:10.0.0.88"], {
                "u:" + str(user["id"]): 2, "c:np_client_1": 2, "ip:10.0.0.88": 2
            })
            auth_db.reserve_free_quota(["u:" + str(user["id"]), "c:np_client_1", "ip:10.0.0.88"], {
                "u:" + str(user["id"]): 2, "c:np_client_1": 2, "ip:10.0.0.88": 2
            })

            nowpay.ENABLED = True
            nowpay.products_config = lambda: {"trial3": {"out_product_id": "DIRECT_TEST"}}
            state = {"rem": 1, "verify_calls": 0, "fail_verify": False}

            def fake_q(uid, pk):
                return {"code": "10000", "total": 3, "used": 3 - state["rem"], "remaining": state["rem"]}

            def fake_v(uid, pk, amount=1, reason="", out_request_no=""):
                state["verify_calls"] += 1
                if state["fail_verify"]:
                    return {"code": "40004", "sub_msg": "BALANCE_NOT_ENOUGH"}
                state["rem"] -= amount
                return {"code": "10000", "_out_request_no": out_request_no}

            nowpay.quota_query = fake_q
            nowpay.quota_verify = fake_v

            # Case A: Two concurrent reserves when remaining=1 -> only 1 succeeds
            ok1, resv1, _ = server._reserve_generation_quota(h)
            ok2, resv2, _ = server._reserve_generation_quota(h)
            assert ok1 and not ok2, (ok1, ok2)

            # Refund resv1 (e.g. ask branch) -> verify_calls stays 0, rem stays 1
            server._refund_generation_quota(resv1)
            assert state["verify_calls"] == 0 and state["rem"] == 1

            # Case B: render failure releases inflight reservation / refunds quota
            server.render = lambda items, sec: (_ for _ in ()).throw(RuntimeError("boom"))
            server.understanding_brain.design_soundscape = lambda *a, **kw: (
                {"action": "compose", "title": "t", "reply": "r", "intent": {"scene": "rain"}, "reasoning": [], "tracks": [{"path": "母带_城市夜雨_CC0.mp3", "weight": 1.0}], "followups": []},
                "规则",
            )
            captured = []
            crashed = False
            try:
                server.run_agent_chat(h, {"say": "夜雨", "force_compose": True}, lambda obj, code=200: captured.append((code, obj)))
            except RuntimeError:
                crashed = True
            assert crashed, "expected render RuntimeError"
            # Inflight reservation must be released after crash!
            assert server._NOWPAY_INFLIGHT.get(str(user["id"]), 0) == 0, server._NOWPAY_INFLIGHT

            # Case C: quota_verify rejected -> run_agent_chat returns 402 and does NOT return audio
            server.render = orig_render
            state["fail_verify"] = True
            captured.clear()
            server.run_agent_chat(h, {"say": "夜雨", "force_compose": True}, lambda obj, code=200: captured.append((code, obj)))
            assert captured and captured[0][0] == 402 and "audio" not in captured[0][1], captured

            # Case D: 30-day window expired -> unlocked=False, paid_left=1 still usable with free tracks!
            import sound_catalog
            free_files = {os.path.basename(p) for p in sound_catalog.FREE_RELPATHS}
            state["fail_verify"] = False
            server.understanding_brain.design_soundscape = lambda *a, **kw: (
                {"action": "compose", "title": "帐篷大雨", "reply": "r", "intent": {"scene": "rain"}, "reasoning": [], "tracks": [{"path": "帐篷雨_小帐篷大雨_592996.hq.mp3", "weight": 1.0}], "followups": []},
                "规则",
            )
            with open(pay_window.STORE, "w", encoding="utf-8") as f:
                json.dump({str(user["id"]): "2020-01-01"}, f)
            q_exp = server._get_quota_status(h, user=user)
            assert q_exp["unlocked"] is False and q_exp["paid_left"] == 1, q_exp
            captured.clear()
            server.run_agent_chat(h, {"say": "想听帐篷大雨", "force_compose": True}, lambda obj, code=200: captured.append((code, obj)))
            assert captured and captured[0][0] == 200 and captured[0][1]["action"] == "compose", captured
            assert captured[0][1]["full_access"] is False and captured[0][1]["catalog_downgraded"] is True, captured
            assert all(t["path"] in free_files for t in captured[0][1]["tracks"]), captured
            assert state["rem"] == 0, state

            print("PASS: NowPay reserve/commit, crash refund, and 30d expiry unit suite (4 cases)")
        finally:
            auth_db.DATA_DIR, auth_db.DB_PATH = orig_db_dir, orig_db_path
            pay_window.DATA_DIR, pay_window.STORE = orig_pw_dir, orig_pw_store
            nowpay.ENABLED = orig_np_enabled
            nowpay.products_config = orig_np_cfg
            nowpay.quota_query = orig_np_quota
            nowpay.quota_verify = orig_np_verify
            nowpay.quota_refresh = orig_np_refresh
            server.render = orig_render
            server.current_user = orig_cur_user
            server.understanding_brain.design_soundscape = orig_design
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    run_http_suite()
    run_nowpay_and_refund_unit_suite()
    print("\nALL QUOTA & BILLING TESTS PASSED!")
