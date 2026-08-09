#!/usr/bin/env python3
"""
修完后再跑：复现截图 + 模拟 api_scan 新二次惩罚逻辑，验证各字段一致
"""
import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shopee_compliance'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'shopee_compliance'))

from services.profit_calculator import calculate_profit, calculate_target_price
from services.opportunity_scorer import calculate_opportunity_score
from models import Violation, ViolationLevel, RiskLevel


def apply_threshold_penalty_like_api_scan(opp_score, pr, threshold):
    """严格拷贝 api_scan.py L802-845 里的最新逻辑"""
    if threshold is None:
        return False
    already_blocked = (not opp_score.gate_passed)
    if already_blocked:
        return False
    if pr.net_profit >= float(threshold):
        return False
    pre_threshold_score = opp_score.score
    if opp_score.score > 40:
        opp_score.score = 40
    opp_score.score_level = "risky"
    opp_score.margin_penalty_applied = True
    opp_score.margin_penalty_cap = opp_score.score
    first_penalty = opp_score.details.get("margin_penalty") or {}
    opp_score.details["margin_penalty"] = {
        "original_score": first_penalty.get("original_score", pre_threshold_score),
        "intermediate_score": first_penalty.get("intermediate_score") if first_penalty.get("intermediate_score") is not None else pre_threshold_score,
        "capped_score": opp_score.score,
        "margin_level": "threshold",
        "source": "min_profit_threshold",
        "applied_cap": opp_score.score,
        "pre_threshold_score": pre_threshold_score,
        "reason": f"min_profit_threshold not met - score hard capped at {opp_score.score}",
    }
    opp_score.details["profit_alert"] = {
        "triggered": True,
        "net_profit": round(pr.net_profit, 2),
        "threshold": float(threshold),
        "pre_threshold_score": pre_threshold_score,
        "final_score": opp_score.score,
        "reason": f"净利润 RM {pr.net_profit:.2f} 未达最低利润目标 RM {float(threshold):.2f}，评分强制限制至 {opp_score.score}",
    }
    return True


def run_scenario(name, cost, price, shipping_fee, shipping_cost, category, title, violations, compliance_score, threshold):
    print("=" * 70)
    print(f"场景: {name}  |  min_profit_threshold=RM{threshold}")
    print(f"  输入: cost={cost}, price={price}, ship_fee={shipping_fee}, ship_cost={shipping_cost}, cat={category}")
    print(f"  标题: {title!r}")
    print("=" * 70)

    pr = calculate_profit(
        selling_price=price, cost_price=cost,
        shipping_fee=shipping_fee, shipping_cost=shipping_cost,
        category=category,
    )
    pd = pr.to_dict()
    fb = pd["fee_breakdown"]
    pf = pd["profit"]
    print(f"\n[利润] 净利 RM {pf['net_profit']:.2f}  利润率 {pf['profit_margin']:.2f}%  margin_level={pd['health']['margin_level']}")
    print(f"     费用拆解: 佣金 RM{fb['commission']:.2f} + 交易 RM{fb['transaction_fee']:.2f} + 服务 RM{fb['service_fee']:.2f} + 平台 RM{fb['platform_fee']:.2f} = 总 RM{fb['total_fees']:.2f}")

    risk_level = RiskLevel.LOW if not any(v.level == ViolationLevel.HIGH for v in violations) else RiskLevel.HIGH
    os_ = calculate_opportunity_score(
        profit_result=pr if pr.calculated else None,
        violations=violations, risk_level=risk_level,
        compliance_score=compliance_score,
        title=title, description="", category=category,
    )
    osd_before = os_.to_dict()

    print(f"\n[Layer 1-3 后（未 threshold）]")
    print(f"  score={osd_before['score']}  level={osd_before['score_level']}  gate_passed={osd_before['gate_passed']}")
    print(f"  维度: C={osd_before['dimensions']['compliance']} P={osd_before['dimensions']['profit']} T={osd_before['dimensions']['competition']} R={osd_before['dimensions']['risk']}")
    print(f"  margin_penalty (to_dict): applied={osd_before['margin_penalty']['applied']} cap={osd_before['margin_penalty']['cap']}  orig={osd_before['margin_penalty'].get('original_score')} intermediate={osd_before['margin_penalty'].get('intermediate_score')} source={osd_before['margin_penalty'].get('source')}")
    if osd_before["details"].get("margin_penalty"):
        print(f"  details.margin_penalty: {json.dumps(osd_before['details']['margin_penalty'], ensure_ascii=False)}")

    triggered = apply_threshold_penalty_like_api_scan(os_, pr, threshold)
    osd_after = os_.to_dict()
    print(f"\n[threshold 后]  triggered={triggered}")
    print(f"  score={osd_after['score']}  level={osd_after['score_level']}")
    print(f"  margin_penalty (to_dict): applied={osd_after['margin_penalty']['applied']} cap={osd_after['margin_penalty']['cap']}  orig={osd_after['margin_penalty'].get('original_score')} intermediate={osd_after['margin_penalty'].get('intermediate_score')} capped={osd_after['margin_penalty'].get('capped_score')} source={osd_after['margin_penalty'].get('source')}")

    # ===== 关键一致性断言 =====
    mp = osd_after["margin_penalty"]
    dims_ok = (osd_after["dimensions"]["compliance"] == 100 and
               osd_after["dimensions"]["risk"] == 100)
    cap_score_consistent = (not mp["applied"]) or (mp["cap"] == osd_after["score"])
    if os_.gate_passed and triggered:
        cap_score_consistent = cap_score_consistent and (mp["cap"] == 40) and (mp["source"] == "min_profit_threshold")

    pa = osd_after["details"].get("profit_alert") or {}
    print(f"\n[断言]")
    print(f"  维度分合理(C=100,R=100): {'✅' if dims_ok else '❌'}")
    print(f"  margin_penalty.cap == score == 40(触发时): {'✅' if cap_score_consistent else '❌'}  (cap={mp['cap']}, score={osd_after['score']})")
    if triggered:
        print(f"  profit_alert.reason 含具体净利数字: {'✅' if str(round(pr.net_profit,2)) in pa.get('reason','') else '❌'} → {pa.get('reason')}")
        print(f"  profit_alert.triggered=True: {'✅' if pa.get('triggered') else '❌'}")
    if not os_.gate_passed:
        print(f"  亏损场景 score=0, level=blocked, 不触发 threshold: {'✅' if osd_after['score_level']=='blocked' and not triggered else '❌'} (level={osd_after['score_level']}, triggered={triggered})")
    print()


# ===== 用新默认 threshold RM 2 跑 =====
print("\n\n" + "#" * 70)
print("# 新默认 threshold = RM 2（更合理，RM5净利润不触发）")
print("#" * 70)

run_scenario(
    name="盈利场景 (净利 RM5.05)",
    cost=11.0, price=20.0, shipping_fee=1.0, shipping_cost=1.0,
    category="general", title="绿色手机壳", violations=[],
    compliance_score=100, threshold=2.0,   # RM5.05 > RM2 → 不触发 threshold
)

run_scenario(
    name="薄利场景 (净利 RM1.50, 售价 RM15)",
    cost=11.0, price=15.0, shipping_fee=1.0, shipping_cost=1.0,
    category="general", title="绿色手机壳", violations=[],
    compliance_score=100, threshold=2.0,   # RM1.50 < RM2 → 触发
)

run_scenario(
    name="亏损场景 (净利 -RM1.12)",
    cost=11.0, price=13.0, shipping_fee=1.0, shipping_cost=1.0,
    category="general", title="绿色手机壳", violations=[],
    compliance_score=100, threshold=2.0,   # 已blocked → 不触发 threshold
)

# ===== 也跑一下老 threshold RM 10，看三级限制文案链路正确 =====
print("\n\n" + "#" * 70)
print("# 旧阈值 RM 10（验证三级链路 83→79→40 全部串起来）")
print("#" * 70)

run_scenario(
    name="盈利场景 (净利 RM5.05)",
    cost=11.0, price=20.0, shipping_fee=1.0, shipping_cost=1.0,
    category="general", title="绿色手机壳", violations=[],
    compliance_score=100, threshold=10.0,
)
