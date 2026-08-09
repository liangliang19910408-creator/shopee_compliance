"""
Phase 1 测试脚本 - 验证费率引擎、利润计算、机会评分

运行方式:
    cd /workspace/project/shopee-compliance-mvp/shopee_compliance
    python3 test_phase1.py
"""
import json
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_fee_engine():
    """测试费率引擎"""
    print("=" * 60)
    print("Test 1: Fee Engine")
    print("=" * 60)

    from services.fee_engine import get_fee_rate, FEE_LOOKUP, get_all_categories, SstMode, apply_sst

    # 1.1 检查加载
    print(f"\n[1.1] Loaded fee rates: {len(FEE_LOOKUP)} entries")
    assert len(FEE_LOOKUP) > 0, "FEE_LOOKUP should not be empty"

    # 1.2 查询 electronics + marketplace + cashback
    rate = get_fee_rate("electronics", "marketplace", True)
    print(f"\n[1.2] Electronics/Marketplace/Cashback:")
    print(f"  Commission: {rate.commission_rate}% (SST: {rate.commission_sst_mode.value})")
    print(f"  Transaction: {rate.transaction_fee}% (SST: {rate.transaction_sst_mode.value})")
    print(f"  Service: {rate.service_fee}% (SST: {rate.service_sst_mode.value})")
    print(f"  Platform: RM {rate.platform_fee} (SST: {rate.platform_fee_sst_mode.value})")
    assert rate.commission_rate == 5.5, f"Expected 5.5, got {rate.commission_rate}"

    # 1.3 查询 fashion + marketplace + no cashback
    rate2 = get_fee_rate("fashion", "marketplace", False)
    print(f"\n[1.3] Fashion/Marketplace/No Cashback:")
    print(f"  Commission: {rate2.commission_rate}%")
    assert rate2.commission_rate == 14.0, f"Expected 14.0, got {rate2.commission_rate}"

    # 1.4 类目别名测试
    rate3 = get_fee_rate("mobile", "marketplace", True)
    print(f"\n[1.4] Mobile (alias for electronics):")
    print(f"  Commission: {rate3.commission_rate}%")
    assert rate3.commission_rate == 5.5, f"Expected 5.5 (electronics), got {rate3.commission_rate}"

    # 1.5 回退测试
    rate4 = get_fee_rate("unknown_category", "marketplace", True)
    print(f"\n[1.5] Unknown category (fallback to general):")
    print(f"  Commission: {rate4.commission_rate}%")
    assert rate4 is not None, "Should fallback to general"

    # 1.6 SST 计算
    sst_result = apply_sst(100, SstMode.ADDITIONAL, 8.0)
    print(f"\n[1.6] SST calculation: 100 × ADDITIONAL(8%) = {sst_result}")
    assert sst_result == 108.0, f"Expected 108.0, got {sst_result}"

    sst_result2 = apply_sst(100, SstMode.EMBEDDED, 8.0)
    print(f"  SST calculation: 100 × EMBEDDED = {sst_result2}")
    assert sst_result2 == 100.0, f"Expected 100.0, got {sst_result2}"

    print("\n✅ Fee Engine: ALL TESTS PASSED")


def test_profit_calculator():
    """测试利润计算器"""
    print("\n" + "=" * 60)
    print("Test 2: Profit Calculator")
    print("=" * 60)

    from services.profit_calculator import calculate_profit

    # 2.1 基本计算 - Electronics, RM100 售价, RM50 成本
    result = calculate_profit(
        selling_price=100.0,
        cost_price=50.0,
        shipping_fee=4.90,
        shipping_cost=3.00,
        category="electronics",
        seller_type="marketplace",
        cashback_enabled=True,
    )

    print(f"\n[2.1] Electronics: RM100 sell, RM50 cost, RM4.90 buyer shipping")
    print(f"  Commission base: RM {result.commission_base:.2f}")
    print(f"  Commission (with SST): RM {result.commission:.2f}")
    print(f"  Commission SST portion: RM {result.commission_sst:.2f}")
    print(f"  Transaction fee: RM {result.transaction_fee:.2f}")
    print(f"  Service fee: RM {result.service_fee:.2f}")
    print(f"  Platform fee: RM {result.platform_fee:.2f}")
    print(f"  Total fees: RM {result.total_fees:.2f}")
    print(f"  Gross profit: RM {result.gross_profit:.2f}")
    print(f"  Net profit: RM {result.net_profit:.2f}")
    print(f"  Profit margin: {result.profit_margin:.2f}%")
    print(f"  Break-even price: RM {result.break_even_price:.2f}")
    print(f"  ROI: {result.roi:.2f}%")
    print(f"  Margin level: {result.margin_level}")

    assert result.calculated, "Should be calculated"
    assert result.commission_base == 5.50, f"Commission base should be 5.50, got {result.commission_base}"
    assert result.commission == 5.94, f"Commission with SST should be 5.94 (5.50×1.08), got {result.commission}"
    assert result.transaction_fee > 0, "Transaction fee should be positive"
    assert result.service_fee > 0, "Service fee should be positive"
    assert result.platform_fee == 0.54, f"Platform fee should be 0.54, got {result.platform_fee}"

    # 2.2 无返现情况
    result2 = calculate_profit(
        selling_price=100.0,
        cost_price=50.0,
        category="fashion",
        seller_type="marketplace",
        cashback_enabled=False,
    )
    print(f"\n[2.2] Fashion/No Cashback: RM100 sell, RM50 cost")
    print(f"  Commission: RM {result2.commission:.2f} (rate: 14%)")
    print(f"  Service fee: RM {result2.service_fee:.2f} (should be 0)")
    print(f"  Net profit: RM {result2.net_profit:.2f}")
    print(f"  Margin: {result2.profit_margin:.2f}%")

    assert result2.service_fee == 0.0, f"Service fee should be 0 without cashback, got {result2.service_fee}"
    assert abs(result2.commission_base - 14.0) < 0.001, f"Commission base should be 14.0, got {result2.commission_base}"

    # 2.3 盈亏平衡验证
    # 用 break_even_price 作为售价，净利润应该接近 0
    be_price = result.break_even_price
    result_be = calculate_profit(
        selling_price=be_price,
        cost_price=50.0,
        shipping_fee=4.90,
        shipping_cost=3.00,
        category="electronics",
        seller_type="marketplace",
        cashback_enabled=True,
    )
    print(f"\n[2.3] Break-even verification:")
    print(f"  Break-even price: RM {be_price:.2f}")
    print(f"  Net profit at break-even: RM {result_be.net_profit:.4f} (should be ~0)")

    assert abs(result_be.net_profit) < 0.01, f"Net profit at break-even should be ~0, got {result_be.net_profit}"

    # 2.4 负利润情况
    result3 = calculate_profit(
        selling_price=10.0,
        cost_price=15.0,
        category="fashion",
        seller_type="marketplace",
        cashback_enabled=True,
    )
    print(f"\n[2.4] Negative profit: RM10 sell, RM15 cost")
    print(f"  Net profit: RM {result3.net_profit:.2f}")
    print(f"  Margin level: {result3.margin_level}")

    assert result3.net_profit < 0, "Should have negative profit"
    assert result3.margin_level == "danger", f"Should be danger, got {result3.margin_level}"

    print("\n✅ Profit Calculator: ALL TESTS PASSED")


def test_opportunity_scorer():
    """测试机会评分"""
    print("\n" + "=" * 60)
    print("Test 3: Opportunity Scorer")
    print("=" * 60)

    from services.opportunity_scorer import calculate_opportunity_score
    from services.profit_calculator import calculate_profit
    from models import Violation, ViolationType, ViolationLevel, RiskLevel

    # 3.1 高利润 + 无违规 = 高分
    profit = calculate_profit(
        selling_price=100.0,
        cost_price=30.0,
        category="electronics",
        seller_type="marketplace",
        cashback_enabled=True,
    )
    score = calculate_opportunity_score(
        profit_result=profit,
        violations=[],
        risk_level=RiskLevel.SAFE,
        compliance_score=100,
        title="Samsung Galaxy Phone Case Cover Premium Quality",
        description="High quality phone case",
        category="electronics",
    )
    print(f"\n[3.1] Good product (high margin, no violations):")
    print(f"  Score: {score.score}/100")
    print(f"  Level: {score.score_level}")
    print(f"  Gate passed: {score.gate_passed}")
    print(f"  Compliance: {score.compliance_score}")
    print(f"  Profit: {score.profit_score}")
    print(f"  Competition: {score.competition_score}")
    print(f"  Risk: {score.risk_score}")

    assert score.gate_passed, "Should pass gate"
    assert score.score >= 60, f"Score should be >= 60, got {score.score}"

    # 3.2 HIGH 风险 = 门控拒绝
    violations_high = [Violation(
        type=ViolationType.BANNED_WORD,
        level=ViolationLevel.HIGH,
        field="title",
        matched_word="vape",
        suggestion="Remove vape",
        reason="Prohibited item",
        rule_type="hard_ban"
    )]
    score2 = calculate_opportunity_score(
        profit_result=profit,
        violations=violations_high,
        risk_level=RiskLevel.HIGH,
        compliance_score=50,
        title="Vape Device",
        category="electronics",
    )
    print(f"\n[3.2] HIGH risk product:")
    print(f"  Score: {score2.score}/100")
    print(f"  Level: {score2.score_level}")
    print(f"  Gate passed: {score2.gate_passed}")
    print(f"  Gate reason: {score2.gate_reason}")

    assert not score2.gate_passed, "Should NOT pass gate (HIGH risk)"
    assert score2.score == 0, f"Score should be 0, got {score2.score}"
    assert score2.score_level == "blocked"

    # 3.3 负利润 = 门控拒绝
    profit_neg = calculate_profit(
        selling_price=10.0,
        cost_price=15.0,
        category="fashion",
        seller_type="marketplace",
        cashback_enabled=True,
    )
    score3 = calculate_opportunity_score(
        profit_result=profit_neg,
        violations=[],
        risk_level=RiskLevel.SAFE,
        compliance_score=100,
        title="Nice Shirt",
        category="fashion",
    )
    print(f"\n[3.3] Negative profit product:")
    print(f"  Score: {score3.score}/100")
    print(f"  Gate passed: {score3.gate_passed}")
    print(f"  Gate reason: {score3.gate_reason}")

    assert not score3.gate_passed, "Should NOT pass gate (negative profit)"
    assert score3.score_level == "blocked"

    # 3.4 无价格数据 = 中性利润分
    score4 = calculate_opportunity_score(
        profit_result=None,
        violations=[],
        risk_level=RiskLevel.SAFE,
        compliance_score=100,
        title="Good Product Name Here",
        category="general",
    )
    print(f"\n[3.4] No price data:")
    print(f"  Score: {score4.score}/100")
    print(f"  Profit score: {score4.profit_score} (should be 50)")

    assert score4.profit_score == 50, f"Profit score should be 50, got {score4.profit_score}"

    print("\n✅ Opportunity Scorer: ALL TESTS PASSED")


def test_banned_words_ruletype():
    """测试违禁词 ruleType 字段"""
    print("\n" + "=" * 60)
    print("Test 4: Banned Words ruleType")
    print("=" * 60)

    from services.rule_loader import get_rules, load_rules

    all_rules = load_rules()
    print(f"\n[4.1] Total rules: {len(all_rules)}")

    # 检查所有规则都有 ruleType
    missing = [r for r in all_rules if "ruleType" not in r]
    print(f"  Rules with ruleType: {len(all_rules) - len(missing)}")
    print(f"  Rules missing ruleType: {len(missing)}")
    assert len(missing) == 0, f"{len(missing)} rules missing ruleType"

    # 统计 ruleType 分布
    from collections import Counter
    types = Counter(r.get("ruleType") for r in all_rules)
    print(f"  Distribution: {dict(types)}")

    # 检查 HALAL 词
    halal_rules = [r for r in all_rules if r.get("category") == "halal"]
    print(f"  HALAL entries: {len(halal_rules)}")
    assert len(halal_rules) >= 8, f"Expected >= 8 HALAL entries, got {len(halal_rules)}"

    # 测试扫描
    from services.checker_banned_words import scan
    violations = scan("Halal Certified Product", "", "food", False)
    print(f"\n[4.2] Scan 'Halal Certified Product' in food category:")
    print(f"  Violations found: {len(violations)}")
    for v in violations:
        print(f"  - {v.matched_word} (level={v.level}, ruleType={v.rule_type})")

    assert len(violations) > 0, "Should detect 'Halal Certified'"
    assert violations[0].rule_type is not None, "rule_type should not be None"

    print("\n✅ Banned Words ruleType: ALL TESTS PASSED")


def test_api_response_shape():
    """测试 API 响应结构（模拟 /api/scan 的输出）"""
    print("\n" + "=" * 60)
    print("Test 5: API Response Shape")
    print("=" * 60)

    from services.profit_calculator import calculate_profit
    from services.opportunity_scorer import calculate_opportunity_score
    from models import RiskLevel

    # 模拟一次完整的扫描
    profit = calculate_profit(
        selling_price=89.90,
        cost_price=35.00,
        shipping_fee=4.90,
        shipping_cost=3.50,
        category="electronics",
        seller_type="marketplace",
        cashback_enabled=True,
    )

    score = calculate_opportunity_score(
        profit_result=profit,
        violations=[],
        risk_level=RiskLevel.SAFE,
        compliance_score=100,
        title="Samsung Galaxy Buds 2 Pro Wireless Earbuds",
        description="Original Samsung earbuds with noise cancellation",
        category="electronics",
    )

    # 模拟 API 响应中的 profit_analysis 字段
    profit_dict = profit.to_dict()
    score_dict = score.to_dict()

    print(f"\n[5.1] profit_analysis structure:")
    print(json.dumps(profit_dict, indent=2, ensure_ascii=False))

    print(f"\n[5.2] opportunity_score structure:")
    print(json.dumps(score_dict, indent=2, ensure_ascii=False))

    # 验证关键字段存在
    assert "fee_breakdown" in profit_dict, "profit_analysis should have fee_breakdown"
    assert "profit" in profit_dict, "profit_analysis should have profit"
    assert "health" in profit_dict, "profit_analysis should have health"
    assert "net_profit" in profit_dict["profit"], "profit should have net_profit"
    assert "profit_margin" in profit_dict["profit"], "profit should have profit_margin"
    assert "break_even_price" in profit_dict["profit"], "profit should have break_even_price"

    assert "score" in score_dict, "opportunity_score should have score"
    assert "score_level" in score_dict, "opportunity_score should have score_level"
    assert "dimensions" in score_dict, "opportunity_score should have dimensions"
    assert "gate_passed" in score_dict, "opportunity_score should have gate_passed"

    print("\n✅ API Response Shape: ALL TESTS PASSED")


def test_excel_verification():
    """
    Excel 验证用例 - 用于手工对比

    这个测试用例的数字应该与 Excel 手工计算结果完全一致。
    如果不一致，说明计算公式有 Bug。

    场景: Electronics / Marketplace / Cashback
    售价: RM 100.00
    成本: RM 50.00
    买家运费: RM 4.90
    卖家运费成本: RM 3.00

    手工计算:
    1. 佣金基数 = 100 × 5.5% = 5.50
    2. 佣金含SST = 5.50 × 1.08 = 5.94
    3. 交易手续费 = (100 + 4.90) × 3.78% = 104.90 × 0.0378 = 3.9652
    4. 服务费 = 100 × 2.16% = 2.16
    5. 平台费 = 0.54
    6. 总费用 = 5.94 + 3.9652 + 2.16 + 0.54 = 12.6052
    7. 净利润 = 100 - 12.6052 - 50 - 3 = 34.3948
    8. 利润率 = 34.3948 / 100 × 100 = 34.39%
    """
    print("\n" + "=" * 60)
    print("Test 6: Excel Verification")
    print("=" * 60)

    from services.profit_calculator import calculate_profit

    result = calculate_profit(
        selling_price=100.0,
        cost_price=50.0,
        shipping_fee=4.90,
        shipping_cost=3.00,
        category="electronics",
        seller_type="marketplace",
        cashback_enabled=True,
    )

    # 手工计算的期望值
    expected = {
        "commission_base": 5.50,
        "commission": 5.94,        # 5.50 × 1.08
        "transaction_fee": 3.9652, # 104.90 × 0.0378
        "service_fee": 2.16,       # 100 × 0.0216
        "platform_fee": 0.54,
        "total_fees": 12.6052,     # 5.94 + 3.9652 + 2.16 + 0.54
        "net_profit": 34.3948,     # 100 - 12.6052 - 50 - 3
        "profit_margin": 34.3948,  # 34.3948 / 100 × 100
    }

    print(f"\n[6.1] Hand calculation vs Python:")
    print(f"{'Item':<20} {'Expected':>12} {'Python':>12} {'Diff':>12}")
    print("-" * 60)

    all_match = True
    for key, exp_val in expected.items():
        actual = getattr(result, key)
        diff = abs(actual - exp_val)
        status = "✅" if diff < 0.01 else "❌"
        if diff >= 0.01:
            all_match = False
        print(f"{key:<20} {exp_val:>12.4f} {actual:>12.4f} {diff:>12.4f} {status}")

    if all_match:
        print("\n✅ Excel Verification: ALL VALUES MATCH (误差 < 0.01)")
    else:
        print("\n❌ Excel Verification: MISMATCH DETECTED - check formula!")

    assert all_match, "Excel verification failed - values don't match"


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Phase 1 Test Suite")
    print("  AI跨境商品预审与利润智能平台")
    print("=" * 60)

    test_fee_engine()
    test_profit_calculator()
    test_opportunity_scorer()
    test_banned_words_ruletype()
    test_api_response_shape()
    test_excel_verification()

    print("\n" + "=" * 60)
    print("  🎉 ALL PHASE 1 TESTS PASSED!")
    print("=" * 60)
