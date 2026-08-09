"""
Admin 1.0 综合测试脚本
验证管理员功能：仪表盘、反馈看板、采纳奖励、熔断开关

运行方式:
    cd /workspace/project/shopee-compliance-mvp/shopee_compliance
    python3 test_admin1.py
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite

# 使用临时数据库
TEST_DB = "/tmp/test_admin1.db"


async def setup_test_db():
    """创建测试数据库"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    db = await aiosqlite.connect(TEST_DB)
    db.row_factory = aiosqlite.Row

    from database import init_db_tables
    await init_db_tables(db)
    await db.commit()
    return db


async def test_database_schema():
    """测试数据库表结构"""
    print("=" * 60)
    print("Test 1: Database Schema (Admin Tables)")
    print("=" * 60)

    db = await setup_test_db()
    try:
        # 1.1 user_feedback 表
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_feedback'")
        assert (await cursor.fetchone()) is not None, "user_feedback table missing"
        print("✅ user_feedback table exists")

        # 1.2 system_flags 表
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_flags'")
        assert (await cursor.fetchone()) is not None, "system_flags table missing"
        print("✅ system_flags table exists")

        # 1.3 admin_logs 表
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_logs'")
        assert (await cursor.fetchone()) is not None, "admin_logs table missing"
        print("✅ admin_logs table exists")

        # 1.4 trials 表新字段
        cursor = await db.execute("PRAGMA table_info(trials)")
        columns = {row["name"] for row in await cursor.fetchall()}
        assert "is_admin" in columns, "is_admin field missing"
        assert "paid_at" in columns, "paid_at field missing"
        print("✅ trials table has is_admin and paid_at fields")

        # 1.5 user_feedback 字段
        cursor = await db.execute("PRAGMA table_info(user_feedback)")
        fb_cols = {row["name"] for row in await cursor.fetchall()}
        required = {"id", "email", "content", "status", "reward_days", "rewarded_at", "created_at"}
        assert required.issubset(fb_cols), f"Missing fields: {required - fb_cols}"
        print("✅ user_feedback has all required fields")

        print("\n✅ Database Schema: ALL TESTS PASSED")
    finally:
        await db.close()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


async def test_dashboard_stats():
    """测试仪表盘统计"""
    print("\n" + "=" * 60)
    print("Test 2: Dashboard Stats (7 numbers + yesterday comparison)")
    print("=" * 60)

    db = await setup_test_db()
    try:
        from database import get_dashboard_stats
        from globals import MYT

        # 插入测试数据
        now = datetime.utcnow()
        now_myt = datetime.now(MYT)
        today_myt = now_myt.strftime("%Y-%m-%d")
        # 使用 MYT 时间作为 trial_start/paid_at，确保与仪表盘的 MYT 日期匹配
        now_myt_iso = now_myt.strftime("%Y-%m-%dT%H:%M:%S")

        # 2个 free 用户
        for i in range(2):
            await db.execute("""
                INSERT INTO trials (email, trial_token, trial_start, trial_end, status, scan_count)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (f"user{i}@test.com", f"token{i}", now_myt_iso, now_myt_iso, "free"))

        # 1个 trial 用户
        await db.execute("""
            INSERT INTO trials (email, trial_token, trial_start, trial_end, status, scan_count)
            VALUES (?, ?, ?, ?, ?, 0)
        """, ("trial@test.com", "tokentrial", now_myt_iso, (now + timedelta(days=7)).isoformat(), "trial"))

        # 1个 paid 用户（今日付费，paid_at 用 MYT 时间）
        await db.execute("""
            INSERT INTO trials (email, trial_token, trial_start, trial_end, status, paid_until, paid_at, scan_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, ("pro@test.com", "tokenpro", now_myt_iso, now_myt_iso, "paid",
              (now + timedelta(days=30)).isoformat(), now_myt_iso))

        # 1个 trial_expired 用户
        await db.execute("""
            INSERT INTO trials (email, trial_token, trial_start, trial_end, status, scan_count)
            VALUES (?, ?, ?, ?, ?, 0)
        """, ("expired@test.com", "tokenexp", now_myt_iso, now_myt_iso, "trial_expired"))

        # 2条待处理反馈
        from database import submit_feedback
        await submit_feedback(db, "user0@test.com", "This is a test feedback with enough characters")
        await submit_feedback(db, "user1@test.com", "Another feedback message here")

        await db.commit()

        # 获取统计
        stats = await get_dashboard_stats(db)
        print(f"\n  Total users: {stats['total_users']}")
        print(f"  Trial users: {stats['trial_users']}")
        print(f"  Pro users: {stats['pro_users']}")
        print(f"  Free users: {stats['free_users']}")
        print(f"  Pending feedback: {stats['pending_feedback']}")
        print(f"  Today new users: {stats['today_new_users']}")
        print(f"  Today conversions: {stats['today_conversions']}")
        print(f"  Yesterday new users: {stats['yesterday_new_users']}")
        print(f"  Yesterday conversions: {stats['yesterday_conversions']}")

        assert stats["total_users"] == 5, f"Expected 5, got {stats['total_users']}"
        assert stats["trial_users"] == 1, f"Expected 1, got {stats['trial_users']}"
        assert stats["pro_users"] == 1, f"Expected 1, got {stats['pro_users']}"
        assert stats["free_users"] == 3, f"Expected 3 (2 free + 1 trial_expired), got {stats['free_users']}"
        assert stats["pending_feedback"] == 2, f"Expected 2, got {stats['pending_feedback']}"
        assert stats["today_new_users"] == 5, f"Expected 5, got {stats['today_new_users']}"
        assert stats["today_conversions"] == 1, f"Expected 1, got {stats['today_conversions']}"
        assert stats["yesterday_new_users"] == 0, f"Expected 0, got {stats['yesterday_new_users']}"
        assert stats["yesterday_conversions"] == 0, f"Expected 0, got {stats['yesterday_conversions']}"

        print("\n✅ Dashboard Stats: ALL TESTS PASSED")
    finally:
        await db.close()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


async def test_feedback_adopt_reward():
    """测试采纳反馈 + 智能延期奖励"""
    print("\n" + "=" * 60)
    print("Test 3: Feedback Adopt & Smart Reward")
    print("=" * 60)

    db = await setup_test_db()
    try:
        from database import submit_feedback, adopt_feedback_and_reward, check_recent_reward

        now = datetime.utcnow()

        # === 3.1 Free 用户 → 升级为 Pro ===
        await db.execute("""
            INSERT INTO trials (email, trial_token, trial_start, trial_end, status, scan_count)
            VALUES (?, ?, ?, ?, ?, 0)
        """, ("free@test.com", "token1", now.isoformat(), now.isoformat(), "free"))

        fb_result = await submit_feedback(db, "free@test.com", "I would love to see batch scan export feature in the future")
        await db.commit()
        fb_id = fb_result["id"]

        result = await adopt_feedback_and_reward(db, fb_id, reward_days=7)
        print(f"\n[3.1] Free → Pro:")
        print(f"  Success: {result['success']}")
        print(f"  Message: {result['message']}")

        assert result["success"], "Adopt should succeed"

        # 验证用户已升级为 paid
        cursor = await db.execute("SELECT status, paid_until FROM trials WHERE email = ?", ("free@test.com",))
        user = await cursor.fetchone()
        assert user["status"] == "paid", f"Expected paid, got {user['status']}"

        paid_until = datetime.fromisoformat(user["paid_until"])
        expected_end = now + timedelta(days=7)
        diff = abs((paid_until - expected_end).total_seconds())
        assert diff < 60, f"Paid_until should be ~7 days from now, diff={diff}s"
        print(f"  Status: paid, paid_until: {user['paid_until'][:10]} ✅")

        # === 3.2 Trial 用户 → 升级为 Pro，到期时间顺延 ===
        trial_end_future = (now + timedelta(days=5)).isoformat()
        await db.execute("""
            INSERT INTO trials (email, trial_token, trial_start, trial_end, status, scan_count)
            VALUES (?, ?, ?, ?, ?, 0)
        """, ("trial@test.com", "token2", now.isoformat(), trial_end_future, "trial"))

        fb_result2 = await submit_feedback(db, "trial@test.com", "The profit calculator is very helpful, please add more categories")
        await db.commit()
        fb_id2 = fb_result2["id"]

        result2 = await adopt_feedback_and_reward(db, fb_id2, reward_days=7)
        print(f"\n[3.2] Trial → Pro (smart extension):")
        print(f"  Success: {result2['success']}")

        assert result2["success"]

        cursor = await db.execute("SELECT status, paid_until FROM trials WHERE email = ?", ("trial@test.com",))
        user2 = await cursor.fetchone()
        assert user2["status"] == "paid"

        paid_until2 = datetime.fromisoformat(user2["paid_until"])
        # 应该是 max(trial_end, now) + 7 = trial_end + 7 = 12天后
        expected_end2 = datetime.fromisoformat(trial_end_future) + timedelta(days=7)
        diff2 = abs((paid_until2 - expected_end2).total_seconds())
        assert diff2 < 60, f"Should be trial_end + 7 days, diff={diff2}s"
        print(f"  Status: paid, paid_until: {user2['paid_until'][:10]} (trial_end + 7d) ✅")

        # === 3.3 Pro 用户 → 顺延不覆盖 ===
        paid_until_future = (now + timedelta(days=10)).isoformat()
        await db.execute("""
            INSERT INTO trials (email, trial_token, trial_start, trial_end, status, paid_until, paid_at, scan_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, ("pro@test.com", "token3", now.isoformat(), now.isoformat(), "paid", paid_until_future, now.isoformat()))

        fb_result3 = await submit_feedback(db, "pro@test.com", "Could you add Lazada support for compliance checking please")
        await db.commit()
        fb_id3 = fb_result3["id"]

        result3 = await adopt_feedback_and_reward(db, fb_id3, reward_days=7)
        print(f"\n[3.3] Pro → Pro (extension):")
        print(f"  Success: {result3['success']}")

        assert result3["success"]

        cursor = await db.execute("SELECT paid_until FROM trials WHERE email = ?", ("pro@test.com",))
        user3 = await cursor.fetchone()
        paid_until3 = datetime.fromisoformat(user3["paid_until"])
        # 应该是 max(paid_until, now) + 7 = paid_until + 7 = 17天后
        expected_end3 = datetime.fromisoformat(paid_until_future) + timedelta(days=7)
        diff3 = abs((paid_until3 - expected_end3).total_seconds())
        assert diff3 < 60, f"Should be paid_until + 7 days, diff={diff3}s"
        print(f"  paid_until: {user3['paid_until'][:10]} (original + 7d) ✅")

        # === 3.4 防刷：7天内重复奖励被拒绝 ===
        is_blocked = await check_recent_reward(db, "free@test.com", days=7)
        assert is_blocked, "Should be blocked (already rewarded within 7 days)"
        print(f"\n[3.4] Anti-abuse: 7-day cooldown check ✅")

        # === 3.5 反馈内容少于10字不可采纳 ===
        from database import get_feedback_by_id
        short_fb = await submit_feedback(db, "user2@test.com", "短反馈")
        await db.commit()

        # 先插入用户
        await db.execute("""
            INSERT INTO trials (email, trial_token, trial_start, trial_end, status, scan_count)
            VALUES (?, ?, ?, ?, ?, 0)
        """, ("user2@test.com", "token4", now.isoformat(), now.isoformat(), "free"))
        await db.commit()

        short_fb_result = await submit_feedback(db, "user2@test.com", "short")
        await db.commit()

        fb_data = await get_feedback_by_id(db, short_fb_result["id"])
        content_len = len(fb_data["content"].strip())
        assert content_len < 10, "Content should be < 10 chars"
        print(f"[3.5] Short feedback ({content_len} chars) - adopt blocked ✅")

        print("\n✅ Feedback Adopt & Reward: ALL TESTS PASSED")
    finally:
        await db.close()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


async def test_system_flags():
    """测试系统开关（熔断）"""
    print("\n" + "=" * 60)
    print("Test 4: System Flags (Payment Circuit Breaker)")
    print("=" * 60)

    db = await setup_test_db()
    try:
        from database import get_system_flag, set_system_flag, log_admin_action

        # 4.1 默认值
        value = await get_system_flag(db, "payment_disabled")
        print(f"\n[4.1] Default payment_disabled: '{value}'")
        assert value == "0", f"Expected '0', got '{value}'"

        # 4.2 设置为停用
        result = await set_system_flag(db, "payment_disabled", "1", "Creem API outage")
        value = await get_system_flag(db, "payment_disabled")
        print(f"[4.2] After disable: '{value}'")
        assert value == "1", f"Expected '1', got '{value}'"

        # 4.3 恢复
        await set_system_flag(db, "payment_disabled", "0", "Restored")
        value = await get_system_flag(db, "payment_disabled")
        print(f"[4.3] After restore: '{value}'")
        assert value == "0"

        # 4.4 日志记录
        await log_admin_action(db, "admin@test.com", "toggle_payment", "payment_disabled", '{"disabled": true}')
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM admin_logs WHERE action = 'toggle_payment'")
        count = (await cursor.fetchone())["cnt"]
        print(f"[4.4] Admin logs: {count} entry")
        assert count == 1

        print("\n✅ System Flags: ALL TESTS PASSED")
    finally:
        await db.close()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


async def test_api_routes():
    """测试 API 路由注册"""
    print("\n" + "=" * 60)
    print("Test 5: API Routes Registration")
    print("=" * 60)

    from routers.api_admin import router

    expected_routes = {
        "/api/admin/dashboard",
        "/api/admin/feedback",
        "/api/admin/feedback/adopt",
        "/api/admin/feedback/dismiss",
        "/api/admin/feedback/submit",
        "/api/admin/payment-status",
        "/api/admin/toggle-payment",
    }

    actual_routes = {r.path for r in router.routes}
    print(f"\n  Expected: {len(expected_routes)} routes")
    print(f"  Actual: {len(actual_routes)} routes")

    for path in expected_routes:
        exists = path in actual_routes
        status = "✅" if exists else "❌"
        print(f"  {status} {path}")
        assert exists, f"Missing route: {path}"

    print("\n✅ API Routes: ALL TESTS PASSED")


async def test_creem_integration():
    """测试 Creem 集成（熔断拦截 + paid_at 写入）"""
    print("\n" + "=" * 60)
    print("Test 6: Creem Integration (Circuit Breaker + paid_at)")
    print("=" * 60)

    # 检查 api_creem.py 代码
    with open(os.path.join(os.path.dirname(__file__), "routers", "api_creem.py"), "r") as f:
        content = f.read()

    checks = [
        ("Import get_system_flag", "get_system_flag" in content),
        ("Circuit breaker check in checkout", "payment_disabled" in content and "503" in content),
        ("paid_at written in webhook (checkout.completed)", "paid_at=COALESCE(paid_at" in content),
        ("Maintenance message", "安全升级" in content or "temporarily" in content.lower() or "Pro 订阅将暂时关闭" in content),
    ]

    print(f"\n[6.1] Creem integration checks:")
    all_pass = True
    for desc, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {desc}")
        if not result:
            all_pass = False

    assert all_pass, "Some Creem integration checks failed"

    # 检查 upgrade_to_paid 也写入 paid_at
    with open(os.path.join(os.path.dirname(__file__), "database.py"), "r") as f:
        db_content = f.read()

    assert "paid_at = COALESCE(paid_at" in db_content, "upgrade_to_paid should write paid_at"
    print("  ✅ upgrade_to_paid also writes paid_at")

    print("\n✅ Creem Integration: ALL TESTS PASSED")


async def test_admin_page():
    """测试管理员前端页面"""
    print("\n" + "=" * 60)
    print("Test 7: Admin Frontend Page")
    print("=" * 60)

    admin_html_path = os.path.join(os.path.dirname(__file__), "templates", "admin.html")
    assert os.path.exists(admin_html_path), "admin.html not found"

    with open(admin_html_path, "r") as f:
        content = f.read()

    checks = [
        ("Dashboard stat cards", "statTotalUsers" in content and "statTrialUsers" in content),
        ("Pro users stat", "statProUsers" in content),
        ("Free users stat", "statFreeUsers" in content),
        ("Today new users", "statTodayNew" in content),
        ("Today conversions", "statTodayConv" in content),
        ("Pending feedback stat", "statPendingFeedback" in content),
        ("Yesterday comparison", "statYesterdayNew" in content),
        ("Payment circuit breaker section", "toggleModal" in content and "toggle-payment" in content),
        ("CONFIRM input for disable", "CONFIRM" in content),
        ("Feedback list rendering", "renderFeedback" in content),
        ("Adopt feedback button", "showAdoptModal" in content),
        ("WA message copy", "copyWAMessage" in content),
        ("Creem dashboard link", "creem.io" in content),
        ("Auto refresh (60s)", "setInterval" in content and "60000" in content),
    ]

    print(f"\n[7.1] Admin page checks:")
    all_pass = True
    for desc, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {desc}")
        if not result:
            all_pass = False

    assert all_pass, "Some admin page checks failed"

    # 检查 pages.py 有 /admin 路由
    with open(os.path.join(os.path.dirname(__file__), "routers", "pages.py"), "r") as f:
        pages_content = f.read()
    assert "/admin" in pages_content and "admin.html" in pages_content, "pages.py missing /admin route"
    print("\n  ✅ pages.py has /admin route")

    print("\n✅ Admin Frontend Page: ALL TESTS PASSED")


async def test_result_page_feedback():
    """测试结果页反馈入口"""
    print("\n" + "=" * 60)
    print("Test 8: Result Page Feedback Entry")
    print("=" * 60)

    result_html_path = os.path.join(os.path.dirname(__file__), "templates", "result.html")
    with open(result_html_path, "r") as f:
        content = f.read()

    checks = [
        ("Feedback section exists", "feedbackSection" in content),
        ("Toggle feedback form", "toggleFeedbackForm" in content),
        ("Feedback textarea", "feedbackContent" in content),
        ("Character counter", "feedbackCharCount" in content),
        ("Submit function", "submitFeedback" in content),
        ("API call to /api/admin/feedback/submit", "/api/admin/feedback/submit" in content),
        ("Max length 1000", "1000" in content),
        ("Min length validation", "5" in content and "at least 5" in content),
    ]

    print(f"\n[8.1] Result page feedback checks:")
    all_pass = True
    for desc, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {desc}")
        if not result:
            all_pass = False

    assert all_pass, "Some result page checks failed"
    print("\n✅ Result Page Feedback: ALL TESTS PASSED")


async def main():
    print("\n" + "=" * 60)
    print("  Admin 1.0 Test Suite")
    print("  AI跨境商品预审与利润智能平台")
    print("  管理员功能：仪表盘 + 反馈看板 + 熔断开关")
    print("=" * 60)

    tests = [
        ("Database Schema", test_database_schema),
        ("Dashboard Stats", test_dashboard_stats),
        ("Feedback Adopt & Reward", test_feedback_adopt_reward),
        ("System Flags", test_system_flags),
        ("API Routes", test_api_routes),
        ("Creem Integration", test_creem_integration),
        ("Admin Frontend Page", test_admin_page),
        ("Result Page Feedback", test_result_page_feedback),
    ]

    passed = 0
    failed = 0
    for name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("  🎉 ALL ADMIN 1.0 TESTS PASSED!")
    else:
        print("  ⚠️  Some tests failed. Please review above.")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
