"""
IntelliAudit 2.0 综合测试脚本
验证洞察建议引擎 + Free/Pro/Trial 权限系统

运行方式:
    cd /workspace/project/shopee-compliance-mvp/shopee_compliance
    python3 test_intelliaudit2.py
"""
import json
import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============ Mock 对象（模拟真实数据结构）============

@dataclass
class MockProfitResult:
    """模拟 ProfitResult"""
    calculated: bool = True
    selling_price: float = 0
    cost_price: float = 0
    shipping_fee: float = 0
    shipping_cost: float = 0
    net_profit: float = 0
    gross_profit: float = 0
    profit_margin: float = 0   # 百分比值，如 34.39
    break_even_price: float = 0
    roi: float = 0
    margin_level: str = "healthy"


@dataclass
class MockOpportunityScore:
    """模拟 OpportunityScore（注意属性名与真实类一致）"""
    score: int = 0
    score_level: str = "good"
    compliance_score: int = 0
    profit_score: int = 0
    competition_score: int = 0
    risk_score: int = 0
    gate_passed: bool = False
    gate_reason: Optional[str] = None


@dataclass
class MockViolation:
    """模拟 Violation"""
    type: str = "banned_word"
    level: str = "high"
    field: str = "title"
    matched_word: str = ""
    suggestion: Optional[str] = None
    reason: str = ""
    rule_type: Optional[str] = None


# ============ 测试用例 ============

def test_insight_executive_summary():
    """测试洞察引擎 - 综合建议摘要（含熔断机制）"""
    print("=" * 60)
    print("Test 1: Insight Engine - Executive Summary (Circuit Breaker)")
    print("=" * 60)

    from services.insight_generator import generate_executive_summary

    # 1.1 无价格数据 → info
    result = generate_executive_summary({
        "has_price_data": False,
        "compliance_score": 100,
    })
    print(f"\n[1.1] No price data:")
    print(f"  Level: {result['level']}")
    print(f"  Message: {result['message']}")
    assert result["level"] == "info", f"Expected info, got {result['level']}"
    assert result["action"] == "input_price"

    # 1.2 合规违规（熔断1 - 最高优先级）
    result = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 0,
        "has_high_risk": True,
        "net_profit": 100,
        "profit_margin": 50,
    })
    print(f"\n[1.2] Compliance violation (circuit breaker 1):")
    print(f"  Level: {result['level']}")
    print(f"  Message: {result['message']}")
    assert result["level"] == "error", f"Expected error, got {result['level']}"
    assert result["action"] == "fix_compliance"
    # 即使利润很高，合规违规也优先
    assert "封店" in result["message"], "Should mention store ban risk"

    # 1.3 亏损（熔断2）
    result = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 100,
        "has_high_risk": False,
        "net_profit": -5.50,
        "profit_margin": -5.5,
        "total_score": 50,
    }, is_pro=True)
    print(f"\n[1.3] Loss (circuit breaker 2) - Pro user:")
    print(f"  Level: {result['level']}")
    print(f"  Message: {result['message']}")
    assert result["level"] == "error"
    assert result["action"] == "optimize_pricing"
    assert "RM5.50" in result["message"], "Should show exact loss amount for Pro"

    # 1.4 亏损 - Free 用户（模糊化金额）
    result_free = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 100,
        "has_high_risk": False,
        "net_profit": -5.50,
        "profit_margin": -5.5,
        "total_score": 50,
    }, is_pro=False)
    print(f"\n[1.4] Loss (circuit breaker 2) - Free user:")
    print(f"  Level: {result_free['level']}")
    print(f"  Message: {result_free['message']}")
    assert result_free["level"] == "error"
    assert "RM5.50" not in result_free["message"], "Free should NOT see exact amount"
    assert "Pro" in result_free["message"], "Should prompt upgrade"

    # 1.5 低利润预警（熔断3）
    result = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 100,
        "has_high_risk": False,
        "net_profit": 3.5,
        "profit_margin": 8.0,
        "total_score": 60,
        "break_even_price": 40.0,
        "selling_price": 45.0,
    }, is_pro=True)
    print(f"\n[1.5] Low margin (circuit breaker 3) - Pro user:")
    print(f"  Level: {result['level']}")
    print(f"  Message: {result['message']}")
    assert result["level"] == "warning"
    assert "8.0%" in result["message"], "Should show exact margin"
    assert "RM" in result["message"], "Should show suggested price for Pro"

    # 1.6 低利润 - Free 用户
    result_free = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 100,
        "has_high_risk": False,
        "net_profit": 3.5,
        "profit_margin": 8.0,
        "total_score": 60,
        "break_even_price": 40.0,
        "selling_price": 45.0,
    }, is_pro=False)
    print(f"\n[1.6] Low margin - Free user:")
    print(f"  Message: {result_free['message']}")
    assert "8.0%" in result_free["message"], "Free should see margin"
    assert "Pro" in result_free["message"], "Should prompt upgrade"

    # 1.7 优质品相
    result = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 100,
        "has_high_risk": False,
        "net_profit": 34.39,
        "profit_margin": 34.39,
        "total_score": 85,
    }, is_pro=True)
    print(f"\n[1.7] Premium product - Pro user:")
    print(f"  Level: {result['level']}")
    print(f"  Message: {result['message']}")
    assert result["level"] == "success"
    assert "备货" in result["message"], "Pro should see stocking advice"

    # 1.8 优质品相 - Free 用户
    result_free = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 100,
        "has_high_risk": False,
        "net_profit": 34.39,
        "profit_margin": 34.39,
        "total_score": 85,
    }, is_pro=False)
    print(f"\n[1.8] Premium product - Free user:")
    print(f"  Message: {result_free['message']}")
    # Free 用户不应看到具体备货数量，但可以看到"备货"这个词（引导升级）
    assert "100-300" not in result_free["message"], "Free should NOT see stocking quantity"
    assert "Pro" in result_free["message"], "Should prompt upgrade"

    # 1.9 默认（谨慎评估）
    result = generate_executive_summary({
        "has_price_data": True,
        "compliance_score": 100,
        "has_high_risk": False,
        "net_profit": 15.0,
        "profit_margin": 15.0,
        "total_score": 60,
    })
    print(f"\n[1.9] Default (cautious):")
    print(f"  Level: {result['level']}")
    print(f"  Message: {result['message']}")
    assert result["level"] == "warning"
    assert result["action"] == "review_details"

    print("\n✅ Executive Summary: ALL TESTS PASSED")


def test_insight_dimension_tips():
    """测试洞察引擎 - 分维度改进建议"""
    print("\n" + "=" * 60)
    print("Test 2: Insight Engine - Dimension Tips (Free vs Pro)")
    print("=" * 60)

    from services.insight_generator import generate_dimension_tips

    # 2.1 合规维度 - 有违规
    tips = generate_dimension_tips({
        "compliance_score": 50,
        "violations": [{"matched_word": "vape"}],
        "hit_word": "vape",
        "has_price_data": True,
        "cost_price": 30,
        "selling_price": 100,
        "profit_margin": 30,
        "break_even_price": 65,
        "title": "Samsung Galaxy Phone Case Premium Quality Cover",
        "profit_score": 80,
        "title_score": 70,
    }, is_pro=True)

    compliance_tip = next(t for t in tips if t["dimension"] == "compliance")
    print(f"\n[2.1] Compliance violation (Pro):")
    print(f"  Status: {compliance_tip['status']}")
    print(f"  Tip: {compliance_tip['tip']}")
    print(f"  Quick action: {compliance_tip.get('quick_action')}")
    assert compliance_tip["status"] == "error"
    assert compliance_tip.get("quick_action") is not None, "Pro should have quick_action"
    assert compliance_tip["quick_action"]["type"] == "REPLACE_TEXT"

    # 2.2 合规维度 - Free 用户无 quick_action
    tips_free = generate_dimension_tips({
        "compliance_score": 50,
        "violations": [{"matched_word": "vape"}],
        "hit_word": "vape",
        "has_price_data": True,
        "cost_price": 30,
        "selling_price": 100,
        "profit_margin": 30,
        "break_even_price": 65,
        "title": "Samsung Galaxy Phone Case Premium Quality Cover",
        "profit_score": 80,
        "title_score": 70,
    }, is_pro=False)
    compliance_tip_free = next(t for t in tips_free if t["dimension"] == "compliance")
    print(f"\n[2.2] Compliance violation (Free):")
    print(f"  Quick action: {compliance_tip_free.get('quick_action')}")
    assert compliance_tip_free.get("quick_action") is None, "Free should NOT have quick_action"

    # 2.3 利润维度 - 成本占比过高
    tips = generate_dimension_tips({
        "compliance_score": 100,
        "violations": [],
        "has_price_data": True,
        "cost_price": 75,
        "selling_price": 100,
        "profit_margin": 5,
        "break_even_price": 95,
        "title": "Test Product Name That Is Long Enough",
        "profit_score": 30,
        "title_score": 70,
    }, is_pro=True)
    profit_tip = next(t for t in tips if t["dimension"] == "profit")
    print(f"\n[2.3] High cost ratio (Pro):")
    print(f"  Status: {profit_tip['status']}")
    print(f"  Tip: {profit_tip['tip']}")
    assert profit_tip["status"] == "error"
    assert profit_tip.get("quick_action") is not None
    assert profit_tip["quick_action"]["type"] == "ADJUST_COST"

    # 2.4 标题维度 - 标题过短
    tips = generate_dimension_tips({
        "compliance_score": 100,
        "violations": [],
        "has_price_data": True,
        "cost_price": 30,
        "selling_price": 100,
        "profit_margin": 30,
        "break_even_price": 65,
        "title": "Short",
        "profit_score": 80,
        "title_score": 40,
    }, is_pro=True)
    title_tip = next(t for t in tips if t["dimension"] == "title")
    print(f"\n[2.4] Short title (Pro):")
    print(f"  Status: {title_tip['status']}")
    print(f"  Tip: {title_tip['tip']}")
    assert title_tip["status"] == "warning"
    assert title_tip.get("quick_action") is not None
    assert title_tip["quick_action"]["type"] == "ENHANCE_TITLE"

    # 2.5 全部正常
    tips = generate_dimension_tips({
        "compliance_score": 100,
        "violations": [],
        "has_price_data": True,
        "cost_price": 30,
        "selling_price": 100,
        "profit_margin": 35,
        "break_even_price": 65,
        "title": "Samsung Galaxy Phone Case Premium Quality Cover Black",
        "profit_score": 85,
        "title_score": 80,
    })
    print(f"\n[2.5] All good:")
    for t in tips:
        print(f"  {t['dimension']}: {t['status']} - {t['tip'][:50]}")
        assert t["status"] == "success"

    print("\n✅ Dimension Tips: ALL TESTS PASSED")


def test_insight_generate_insights():
    """测试洞察引擎 - 一站式生成（使用真实对象）"""
    print("\n" + "=" * 60)
    print("Test 3: Insight Engine - generate_insights (Integration)")
    print("=" * 60)

    from services.insight_generator import generate_insights
    from models import RiskLevel

    # 3.1 使用 Mock 对象（属性名与真实类一致）
    profit = MockProfitResult(
        calculated=True,
        selling_price=89.90,
        cost_price=35.00,
        net_profit=34.39,
        profit_margin=38.25,
        break_even_price=55.62,
        gross_profit=54.90,
    )
    opp_score = MockOpportunityScore(
        score=85,
        score_level="premium",
        compliance_score=100,
        profit_score=90,
        competition_score=80,
        risk_score=100,
        gate_passed=True,
    )

    insights = generate_insights(
        compliance_score=100,
        violations=[],
        risk_level=RiskLevel.SAFE,
        profit_result=profit,
        opportunity_score=opp_score,
        title="Samsung Galaxy Buds 2 Pro Wireless Earbuds Noise Cancellation",
        cost_price=35.00,
        selling_price=89.90,
        is_pro=True,
    )

    print(f"\n[3.1] Premium product (Pro):")
    print(f"  Executive summary level: {insights['executive_summary']['level']}")
    print(f"  Executive summary: {insights['executive_summary']['message']}")
    print(f"  Dimension tips count: {len(insights['dimension_tips'])}")
    for tip in insights["dimension_tips"]:
        print(f"    - {tip['dimension']}: {tip['status']} | quick_action: {tip.get('quick_action') is not None}")

    assert insights["executive_summary"]["level"] == "success"
    assert len(insights["dimension_tips"]) == 3
    # 优质品所有维度都是 success，不会有 quick_action（quick_action 仅用于 warning/error 维度）
    all_success = all(t["status"] == "success" for t in insights["dimension_tips"])
    assert all_success, "Premium product should have all success dimensions"

    # 3.2 合规违规 + 亏损 → 熔断到合规
    profit_loss = MockProfitResult(
        calculated=True,
        selling_price=10.0,
        cost_price=15.0,
        net_profit=-8.50,
        profit_margin=-85.0,
        break_even_price=18.0,
    )
    violation = MockViolation(matched_word="vape", reason="Prohibited item")
    opp_score_blocked = MockOpportunityScore(
        score=0,
        score_level="blocked",
        compliance_score=0,
        gate_passed=False,
    )

    insights2 = generate_insights(
        compliance_score=0,
        violations=[violation],
        risk_level=RiskLevel.HIGH,
        profit_result=profit_loss,
        opportunity_score=opp_score_blocked,
        title="Vape Device Pen",
        cost_price=15.0,
        selling_price=10.0,
        is_pro=False,
    )

    print(f"\n[3.2] Compliance violation + Loss (circuit breaker):")
    print(f"  Executive summary level: {insights2['executive_summary']['level']}")
    print(f"  Executive summary: {insights2['executive_summary']['message']}")
    assert insights2["executive_summary"]["level"] == "error"
    assert insights2["executive_summary"]["action"] == "fix_compliance"
    # 熔断：合规优先于亏损
    assert "封店" in insights2["executive_summary"]["message"]

    # 3.3 无价格数据
    insights3 = generate_insights(
        compliance_score=100,
        violations=[],
        risk_level=RiskLevel.SAFE,
        profit_result=None,
        opportunity_score=None,
        title="Test Product",
        cost_price=0,
        selling_price=0,
        is_pro=False,
    )
    print(f"\n[3.3] No price data:")
    print(f"  Executive summary: {insights3['executive_summary']['message']}")
    assert insights3["executive_summary"]["level"] == "info"
    assert insights3["executive_summary"]["action"] == "input_price"

    print("\n✅ generate_insights: ALL TESTS PASSED")


def test_auth_system():
    """测试权限系统 - get_effective_status / get_user_tier / is_pro_user"""
    print("\n" + "=" * 60)
    print("Test 4: Auth System - Tier & Status")
    print("=" * 60)

    from auth import get_effective_status, get_user_tier, is_pro_user, get_trial_remaining_days

    now = datetime.utcnow()
    future = (now + timedelta(days=7)).isoformat()
    past = (now - timedelta(days=1)).isoformat()

    # 4.1 Free 用户
    user_free = {"status": "free"}
    assert get_effective_status(user_free) == "free"
    assert get_user_tier(user_free) == "free"
    assert not is_pro_user(user_free)
    print(f"\n[4.1] Free user: status={get_effective_status(user_free)}, tier={get_user_tier(user_free)}")

    # 4.2 Trial 有效
    user_trial = {"status": "trial", "trial_end": future}
    assert get_effective_status(user_trial) == "trial"
    assert get_user_tier(user_trial) == "trial"
    assert is_pro_user(user_trial)  # Trial 期间也算 Pro
    print(f"[4.2] Active trial: status={get_effective_status(user_trial)}, tier={get_user_tier(user_trial)}, is_pro={is_pro_user(user_trial)}")

    # 4.3 Trial 过期（实时降级）
    user_trial_expired = {"status": "trial", "trial_end": past}
    assert get_effective_status(user_trial_expired) == "trial_expired"
    assert get_user_tier(user_trial_expired) == "free"
    assert not is_pro_user(user_trial_expired)
    print(f"[4.3] Expired trial: status={get_effective_status(user_trial_expired)}, tier={get_user_tier(user_trial_expired)}")

    # 4.4 Paid 有效
    user_paid = {"status": "paid", "paid_until": future}
    assert get_effective_status(user_paid) == "paid"
    assert get_user_tier(user_paid) == "pro"
    assert is_pro_user(user_paid)
    print(f"[4.4] Active paid: status={get_effective_status(user_paid)}, tier={get_user_tier(user_paid)}, is_pro={is_pro_user(user_paid)}")

    # 4.5 Paid 过期（降级为 free）
    user_paid_expired = {"status": "paid", "paid_until": past}
    assert get_effective_status(user_paid_expired) == "free"
    assert get_user_tier(user_paid_expired) == "free"
    assert not is_pro_user(user_paid_expired)
    print(f"[4.5] Expired paid: status={get_effective_status(user_paid_expired)}, tier={get_user_tier(user_paid_expired)}")

    # 4.6 Trial 无 trial_end → 视为过期
    user_no_end = {"status": "trial", "trial_end": None}
    assert get_effective_status(user_no_end) == "trial_expired"
    print(f"[4.6] Trial no end: status={get_effective_status(user_no_end)}")

    # 4.7 空用户
    assert get_effective_status(None) == "free"
    assert get_user_tier(None) == "free"
    assert not is_pro_user(None)
    print(f"[4.7] Null user: status={get_effective_status(None)}, tier={get_user_tier(None)}")

    # 4.8 剩余天数
    remaining = get_trial_remaining_days({"status": "trial", "trial_end": future})
    assert remaining > 0 and remaining <= 7, f"Expected 1-7, got {remaining}"
    print(f"[4.8] Trial remaining days: {remaining}")

    # 4.9 Cancelled 用户
    user_cancelled = {"status": "cancelled"}
    assert get_effective_status(user_cancelled) == "cancelled"
    assert get_user_tier(user_cancelled) == "free"
    print(f"[4.9] Cancelled: status={get_effective_status(user_cancelled)}, tier={get_user_tier(user_cancelled)}")

    print("\n✅ Auth System: ALL TESTS PASSED")


def test_globals_constants():
    """测试全局常量配置"""
    print("\n" + "=" * 60)
    print("Test 5: Global Constants")
    print("=" * 60)

    from globals import (
        MYT, FREE_DAILY_SCAN_LIMIT, FREE_DAILY_URL_PARSE_LIMIT,
        REGISTER_IP_HOURLY_LIMIT, TEMP_EMAIL_DOMAINS,
        URL_PARSE_LIMIT, URL_CACHE, SCAN_LIMIT, REGISTER_LIMIT
    )
    from datetime import timezone, timedelta

    # 5.1 MYT 时区
    print(f"\n[5.1] MYT timezone: UTC{MYT.utcoffset(None)}")
    expected_offset = timedelta(hours=8)
    assert MYT.utcoffset(None) == expected_offset, f"Expected UTC+8, got {MYT.utcoffset(None)}"

    # 5.2 日限额
    print(f"[5.2] FREE_DAILY_SCAN_LIMIT: {FREE_DAILY_SCAN_LIMIT}")
    assert FREE_DAILY_SCAN_LIMIT == 5

    print(f"[5.3] FREE_DAILY_URL_PARSE_LIMIT: {FREE_DAILY_URL_PARSE_LIMIT}")
    assert FREE_DAILY_URL_PARSE_LIMIT == 3

    # 5.4 注册限流
    print(f"[5.4] REGISTER_IP_HOURLY_LIMIT: {REGISTER_IP_HOURLY_LIMIT}")
    assert REGISTER_IP_HOURLY_LIMIT == 3

    # 5.5 临时邮箱黑名单
    print(f"[5.5] TEMP_EMAIL_DOMAINS count: {len(TEMP_EMAIL_DOMAINS)}")
    assert len(TEMP_EMAIL_DOMAINS) >= 10
    assert "tempmail.com" in TEMP_EMAIL_DOMAINS
    assert "mailinator.com" in TEMP_EMAIL_DOMAINS

    # 5.6 限流字典
    print(f"[5.6] Rate limit dicts: URL_PARSE_LIMIT={type(URL_PARSE_LIMIT).__name__}, SCAN_LIMIT={type(SCAN_LIMIT).__name__}, REGISTER_LIMIT={type(REGISTER_LIMIT).__name__}")
    assert isinstance(URL_PARSE_LIMIT, dict)
    assert isinstance(SCAN_LIMIT, dict)
    assert isinstance(REGISTER_LIMIT, dict)

    print("\n✅ Global Constants: ALL TESTS PASSED")


def test_registration_validation():
    """测试注册验证逻辑（纯函数，不依赖数据库）"""
    print("\n" + "=" * 60)
    print("Test 6: Registration Validation Logic")
    print("=" * 60)

    import re
    from globals import TEMP_EMAIL_DOMAINS, REGISTER_IP_HOURLY_LIMIT

    # 6.1 密码强度校验
    password_pattern = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$')
    test_cases = [
        ("Password123", True, "Valid password"),
        ("short1", False, "Too short"),
        ("allletters", False, "No digits"),
        ("12345678", False, "No letters"),
        ("Ab1!5678", True, "Min valid (8 chars)"),
    ]
    print(f"\n[6.1] Password strength:")
    for pwd, expected, desc in test_cases:
        result = bool(password_pattern.match(pwd))
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{pwd}': {result} ({desc})")
        assert result == expected, f"Password '{pwd}' failed: expected {expected}"

    # 6.2 邮箱域名黑名单
    print(f"\n[6.2] Email domain blacklist:")
    test_emails = [
        ("user@gmail.com", False, "Gmail - allowed"),
        ("user@tempmail.com", True, "Tempmail - blocked"),
        ("user@10minutemail.com", True, "10minutemail - blocked"),
        ("user@yahoo.com", False, "Yahoo - allowed"),
        ("user@MAILINATOR.com", True, "Mailinator (uppercase) - blocked"),
    ]
    for email, expected_blocked, desc in test_emails:
        domain = email.split("@")[-1].lower()
        is_blocked = any(domain.endswith(d) for d in TEMP_EMAIL_DOMAINS)
        status = "✅" if is_blocked == expected_blocked else "❌"
        print(f"  {status} {email}: blocked={is_blocked} ({desc})")
        assert is_blocked == expected_blocked

    # 6.3 WA 号格式校验
    wa_pattern = re.compile(r'^\+60\d{9,11}$')
    wa_cases = [
        ("+60123456789", True, "Valid Malaysian WA"),
        ("+6012345678901", True, "Valid (11 digits)"),
        ("60123456789", False, "Missing +"),
        ("+601234", False, "Too short"),
        ("+65123456789", False, "Singapore number"),
        ("+601234567890123", False, "Too long"),
    ]
    print(f"\n[6.3] WhatsApp number format:")
    for wa, expected, desc in wa_cases:
        cleaned = re.sub(r'[\s\-()]', '', wa.strip())
        result = bool(wa_pattern.match(cleaned))
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{wa}': valid={result} ({desc})")
        assert result == expected

    print("\n✅ Registration Validation: ALL TESTS PASSED")


def test_database_schema():
    """测试数据库 schema（新表和新字段）"""
    print("\n" + "=" * 60)
    print("Test 7: Database Schema")
    print("=" * 60)

    import asyncio
    import aiosqlite
    from config import DATABASE_PATH

    async def check_schema():
        # 使用临时数据库测试
        test_db_path = "/tmp/test_intelliaudit2.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        async with aiosqlite.connect(test_db_path) as db:
            db.row_factory = aiosqlite.Row

            # 执行 init_db_tables
            from database import init_db_tables
            await init_db_tables(db)

            # 7.1 检查 trials 表新字段
            cursor = await db.execute("PRAGMA table_info(trials)")
            columns = {row["name"]: row for row in await cursor.fetchall()}

            required_new_fields = [
                "scan_count_today",
                "last_scan_date",
                "wa_number",
                "trial_activated_at",
                "trial_activated_wa",
                "email_verified",
                "registered_ip",
                "password_hash",
            ]
            print(f"\n[7.1] trials table new fields:")
            for field in required_new_fields:
                exists = field in columns
                status = "✅" if exists else "❌"
                print(f"  {status} {field}")
                assert exists, f"Missing field: {field}"

            # 7.2 检查 opportunity_scores 表
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='opportunity_scores'")
            row = await cursor.fetchone()
            exists = row is not None
            print(f"\n[7.2] opportunity_scores table: {'✅ exists' if exists else '❌ missing'}")
            assert exists

            # 7.3 检查 opportunity_scores 字段
            cursor = await db.execute("PRAGMA table_info(opportunity_scores)")
            opp_columns = {row["name"] for row in await cursor.fetchall()}
            required_opp_fields = [
                "score", "score_level", "compliance_score",
                "profit_score", "competition_score", "risk_score",
                "profit_margin", "net_profit"
            ]
            print(f"\n[7.3] opportunity_scores fields:")
            for field in required_opp_fields:
                exists = field in opp_columns
                status = "✅" if exists else "❌"
                print(f"  {status} {field}")
                assert exists, f"Missing field: {field}"

            # 7.4 检查 scan_sessions 和 scan_results 表
            for table in ["scan_sessions", "scan_results", "batch_jobs", "batch_job_items"]:
                cursor = await db.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                row = await cursor.fetchone()
                exists = row is not None
                print(f"[7.4] {table}: {'✅' if exists else '❌'}")
                assert exists

            # 7.5 验证 wa_number 唯一索引
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_trials_wa_number'")
            row = await cursor.fetchone()
            exists = row is not None
            print(f"[7.5] idx_trials_wa_number unique index: {'✅' if exists else '❌'}")
            assert exists

        # 清理
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    asyncio.run(check_schema())
    print("\n✅ Database Schema: ALL TESTS PASSED")


def test_batch_limits():
    """测试批量扫描分层限制"""
    print("\n" + "=" * 60)
    print("Test 8: Batch Scan Tier Limits")
    print("=" * 60)

    # 直接验证 api_batch 模块中的常量
    import importlib
    spec = importlib.util.spec_from_file_location(
        "api_batch",
        os.path.join(os.path.dirname(__file__), "routers", "api_batch.py")
    )
    # 由于 api_batch 有依赖，我们直接检查常量值
    # 通过 grep 验证即可，这里模拟逻辑

    # 读取文件验证常量
    with open(os.path.join(os.path.dirname(__file__), "routers", "api_batch.py"), "r") as f:
        content = f.read()

    print(f"\n[8.1] BATCH_LIMIT_FREE = 3: {'✅' if 'BATCH_LIMIT_FREE = 3' in content else '❌'}")
    assert "BATCH_LIMIT_FREE = 3" in content

    print(f"[8.2] BATCH_LIMIT_PRO = 100: {'✅' if 'BATCH_LIMIT_PRO = 100' in content else '❌'}")
    assert "BATCH_LIMIT_PRO = 100" in content

    print(f"[8.3] Uses get_user_tier: {'✅' if 'get_user_tier' in content else '❌'}")
    assert "get_user_tier" in content

    print(f"[8.4] Uses get_effective_status: {'✅' if 'get_effective_status' in content else '❌'}")
    assert "get_effective_status" in content

    tier_check = 'if tier == "free"' in content
    print(f"[8.5] Tier-based limit check: {'✅' if tier_check else '❌'}")
    assert tier_check

    print("\n✅ Batch Limits: ALL TESTS PASSED")


def test_api_scan_integration():
    """测试 API 扫描路由的集成（关键代码片段验证）"""
    print("\n" + "=" * 60)
    print("Test 9: API Scan Integration")
    print("=" * 60)

    with open(os.path.join(os.path.dirname(__file__), "routers", "api_scan.py"), "r") as f:
        content = f.read()

    checks = [
        ("MYT timezone import", "from globals import" in content and "MYT" in content),
        ("FREE_DAILY_SCAN_LIMIT used", "FREE_DAILY_SCAN_LIMIT" in content),
        ("TEMP_EMAIL_DOMAINS used", "TEMP_EMAIL_DOMAINS" in content),
        ("REGISTER_IP_HOURLY_LIMIT used", "REGISTER_IP_HOURLY_LIMIT" in content),
        ("get_effective_status called", "get_effective_status" in content),
        ("get_user_tier imported", "get_user_tier" in content),
        ("generate_insights called", "generate_insights(" in content),
        ("executive_summary in response", "executive_summary" in content),
        ("dimension_tips in response", "dimension_tips" in content),
        ("is_pro in response", "is_pro" in content),
        ("Daily limit reset with MYT", "datetime.now(MYT)" in content),
        ("WA number validation", "+60" in content and "wa_pattern" in content),
        ("Email blacklist check", "TEMP_EMAIL_DOMAINS" in content and "email_domain" in content),
        ("IP rate limiting", "REGISTER_LIMIT" in content),
        ("Unified quota (no separate profit limit)", "统一日配额" in content),
        ("Trial 14 days", "timedelta(days=14)" in content),
        ("bind_wa_and_activate_trial imported", "bind_wa_and_activate_trial" in content),
        ("check_wa_used imported", "check_wa_used" in content),
    ]

    print(f"\n[9.1] API scan integration checks:")
    all_pass = True
    for desc, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {desc}")
        if not result:
            all_pass = False

    assert all_pass, "Some integration checks failed"
    print("\n✅ API Scan Integration: ALL TESTS PASSED")


def test_profit_calculator_integration():
    """测试利润计算器与洞察引擎的数据流一致性"""
    print("\n" + "=" * 60)
    print("Test 10: Profit Calculator → Insight Engine Data Flow")
    print("=" * 60)

    from services.profit_calculator import calculate_profit
    from services.opportunity_scorer import calculate_opportunity_score
    from services.insight_generator import generate_insights
    from models import RiskLevel

    # 完整数据流：利润计算 → 机会评分 → 洞察生成
    profit = calculate_profit(
        selling_price=100.0,
        cost_price=50.0,
        shipping_fee=4.90,
        shipping_cost=3.00,
        category="electronics",
        seller_type="marketplace",
        cashback_enabled=True,
    )

    opp_score = calculate_opportunity_score(
        profit_result=profit,
        violations=[],
        risk_level=RiskLevel.SAFE,
        compliance_score=100,
        title="Samsung Galaxy Phone Case Premium Quality Cover Black Edition",
        description="High quality phone case",
        category="electronics",
    )

    insights = generate_insights(
        compliance_score=100,
        violations=[],
        risk_level=RiskLevel.SAFE,
        profit_result=profit,
        opportunity_score=opp_score,
        title="Samsung Galaxy Phone Case Premium Quality Cover Black Edition",
        cost_price=50.0,
        selling_price=100.0,
        is_pro=True,
    )

    print(f"\n[10.1] Full pipeline result:")
    print(f"  Profit margin: {profit.profit_margin:.2f}%")
    print(f"  Net profit: RM{profit.net_profit:.2f}")
    print(f"  Opportunity score: {opp_score.score}/100 ({opp_score.score_level})")
    print(f"  Executive summary: [{insights['executive_summary']['level']}] {insights['executive_summary']['message']}")
    print(f"  Dimension tips: {len(insights['dimension_tips'])} tips")

    # 验证数据一致性
    assert profit.calculated, "Profit should be calculated"
    assert opp_score.score > 0, "Score should be positive for good product"
    assert insights["executive_summary"] is not None
    assert len(insights["dimension_tips"]) == 3

    # 验证利润数据正确传递到洞察引擎
    summary_msg = insights["executive_summary"]["message"]
    if profit.profit_margin >= 20 and opp_score.score >= 80:
        assert insights["executive_summary"]["level"] == "success", "Should be premium"

    print("\n✅ Profit Calculator Integration: ALL TESTS PASSED")


# ============ 主入口 ============

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  IntelliAudit 2.0 Test Suite")
    print("  AI跨境商品预审与利润智能平台")
    print("  洞察建议引擎 + Free/Pro/Trial 权限系统")
    print("=" * 60)

    tests = [
        test_insight_executive_summary,
        test_insight_dimension_tips,
        test_insight_generate_insights,
        test_auth_system,
        test_globals_constants,
        test_registration_validation,
        test_database_schema,
        test_batch_limits,
        test_api_scan_integration,
        test_profit_calculator_integration,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("  🎉 ALL INTELLIAUDIT 2.0 TESTS PASSED!")
    else:
        print("  ⚠️  Some tests failed. Please review above.")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
