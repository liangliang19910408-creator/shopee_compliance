"""
洞察建议引擎 - IntelliAudit 2.0

基于合规扫描、利润计算、机会评分三大引擎的结果，
生成自然语言建议与行动方案。

Layer 1: 综合建议摘要（executive_summary）
    - 熔断机制：合规违规 > 亏损 > 低利润 > 优质 > 默认
    - 只输出优先级最高的一条

Layer 2: 分维度改进建议（dimension_tips）
    - 合规维度：基于违禁词扫描
    - 利润维度：基于成本占比和利润率
    - 标题维度：基于标题长度和关键词

Free/Pro 区分：
    - Free: 综合建议摘要 + 基础分维度建议（无 quick_action）
    - Pro:  综合建议摘要 + 完整分维度建议（含 quick_action）
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class DimensionTip:
    """分维度建议项"""
    dimension: str           # "compliance" | "profit" | "title"
    status: str              # "success" | "warning" | "error"
    score: int               # 该维度得分 0-100
    tip: str                 # 自然语言建议
    quick_action: Optional[Dict[str, Any]] = None


def generate_executive_summary(data: Dict[str, Any], is_pro: bool = False) -> Dict[str, str]:
    """
    生成综合建议摘要（含熔断机制）

    优先级：
        1. 合规违规（compliance_score == 0 或 HIGH风险）
        2. 净利润 < 0（亏损）
        3. 利润率 < 10%（低利润预警）
        4. 总分 >= 80 且利润率 >= 20%（优质品）
        5. 默认（谨慎评估）

    注意：profit_margin 是百分比值（如 11.19 表示 11.19%），不是小数

    Free/Pro 区分：
        - Free: 模糊化具体金额，提示升级查看详细数据
        - Pro:  展示完整数据和建议
    """
    compliance_score = data.get("compliance_score", 100)
    has_high_risk = data.get("has_high_risk", False)
    net_profit = data.get("net_profit", 0)
    profit_margin = data.get("profit_margin", 0)  # 百分比值，如 11.19
    total_score = data.get("total_score", 0)
    break_even_price = data.get("break_even_price", 0)
    has_price_data = data.get("has_price_data", False)

    # ---- 前置：无价格数据时给出提示 ----
    if not has_price_data:
        return {
            "level": "info",
            "message": "📌 请输入成本和售价，获取完整的利润分析与建议。",
            "action": "input_price"
        }

    # ---- 熔断1：合规违规（最高优先级）----
    if compliance_score == 0 or has_high_risk:
        return {
            "level": "error",
            "message": "🚨 高危：含禁售违规词，上架即面临封店风险，请立即修改标题。",
            "action": "fix_compliance"
        }

    # ---- 熔断2：亏损（防呆：使用绝对值）----
    if net_profit < 0:
        abs_profit = abs(net_profit)
        if is_pro:
            msg = f"🚨 紧急止损：当前定价导致每单亏损 RM{abs_profit:.2f}，请立即提价或重谈成本。"
        else:
            msg = "🚨 紧急止损：当前定价导致亏损，升级 Pro 查看具体亏损金额与优化方案。"
        return {
            "level": "error",
            "message": msg,
            "action": "optimize_pricing"
        }

    # ---- 熔断3：低利润预警（< 10%）----
    if profit_margin < 10:
        if is_pro:
            suggested_price = max(break_even_price * 1.15, data.get("selling_price", 0) * 1.10)
            msg = f"⚠️ 利润预警：当前利润率仅 {profit_margin:.1f}%，建议优化成本或提价至 RM{suggested_price:.2f}。"
        else:
            msg = f"⚠️ 利润预警：当前利润率仅 {profit_margin:.1f}%，升级 Pro 获取建议售价与优化方案。"
        return {
            "level": "warning",
            "message": msg,
            "action": "optimize_pricing"
        }

    # ---- 优质品相 ----
    if total_score >= 80 and profit_margin >= 20:
        if is_pro:
            msg = "✅ 优质潜力品：利润健康且合规安全，建议首批备货 100-300 件测试市场。"
        else:
            msg = "✅ 优质潜力品：利润健康且合规安全。升级 Pro 查看备货建议与深度分析。"
        return {
            "level": "success",
            "message": msg,
            "action": "approve_listing"
        }

    # ---- 默认：谨慎评估 ----
    return {
        "level": "warning",
        "message": "📌 谨慎评估：商品存在多项优化空间，建议调整后再次预审。",
        "action": "review_details"
    }


def generate_dimension_tips(
    data: Dict[str, Any],
    is_pro: bool = False,
    platform: str = "shopee"
) -> List[Dict[str, Any]]:
    """
    生成分维度改进建议（结构化输出）

    Args:
        data: 包含扫描结果的字典
        is_pro: 是否为 Pro 用户（决定是否输出 quick_action）

    Returns:
        三个维度的建议列表
    """
    tips = []
    title = data.get("title", "")
    cost_price = data.get("cost_price", 0)
    selling_price = data.get("selling_price", 1)
    profit_margin = data.get("profit_margin", 0)  # 百分比
    break_even_price = data.get("break_even_price", 0)
    has_price_data = data.get("has_price_data", False)
    violations = data.get("violations", [])
    hit_word = data.get("hit_word", None)

    # === 维度一：合规 ===
    compliance_score = data.get("compliance_score", 100)
    if compliance_score == 100 and not violations:
        tips.append(asdict(DimensionTip(
            dimension="compliance",
            status="success",
            score=compliance_score,
            tip="✅ 标题未检测到违规词，合规状态良好。"
        )))
    else:
        word_display = hit_word or (violations[0].get("matched_word") if violations and isinstance(violations[0], dict) else "敏感词")
        tip_text = f"❌ 标题含违规词：{word_display}，建议替换或移除。若为品牌词，请确认授权。"
        tip = DimensionTip(
            dimension="compliance",
            status="error",
            score=compliance_score,
            tip=tip_text,
        )
        if is_pro:
            tip.quick_action = {"type": "REPLACE_TEXT", "target": word_display}
        tips.append(asdict(tip))

    # === 维度二：利润 ===
    profit_score = data.get("profit_score", 0)

    if not has_price_data:
        tip = DimensionTip(
            dimension="profit",
            status="info",
            score=profit_score,
            tip="💡 输入成本和售价后，将自动分析利润结构并给出优化建议。",
        )
        tips.append(asdict(tip))
    else:
        cost_ratio = cost_price / selling_price if selling_price > 0 else 1

        if cost_ratio > 0.7:
            target_cost = cost_price * 0.8
            if is_pro:
                tip_text = f"💡 成本占比高达 {cost_ratio:.0%}，建议寻找低于 RM{target_cost:.2f} 的货源，或启用海外仓降低运费。"
            else:
                tip_text = f"💡 成本占比高达 {cost_ratio:.0%}，建议优化货源降低成本。升级 Pro 查看目标成本价。"
            tip = DimensionTip(
                dimension="profit",
                status="error",
                score=profit_score,
                tip=tip_text,
            )
            if is_pro:
                tip.quick_action = {"type": "ADJUST_COST", "target_value": round(target_cost, 2)}
            tips.append(asdict(tip))
        elif profit_margin < 10:
            suggested_price = max(break_even_price * 1.15, selling_price * 1.10)
            if is_pro:
                tip_text = f"⚠️ 当前售价逼近盈亏平衡点，建议提价至 RM{suggested_price:.2f}。"
            else:
                tip_text = f"⚠️ 当前售价逼近盈亏平衡点，利润率仅 {profit_margin:.1f}%。升级 Pro 获取建议售价。"
            tip = DimensionTip(
                dimension="profit",
                status="warning",
                score=profit_score,
                tip=tip_text,
            )
            if is_pro:
                tip.quick_action = {"type": "ADJUST_PRICE", "target_value": round(suggested_price, 2)}
            tips.append(asdict(tip))
        else:
            tips.append(asdict(DimensionTip(
                dimension="profit",
                status="success",
                score=profit_score,
                tip="✅ 利润结构健康，当前定价策略合理。"
            )))

    # === 维度四：平台特有建议 ===
    if platform == "lazada":
        tips.append(asdict(DimensionTip(
            dimension="platform",
            status="info",
            score=0,
            tip="💡 Lazada 主图需为白底，否则影响搜索权重。标题权重依赖前 30 字符，建议将核心词前置。Lazada 账期较长（周结/半月结），需预留现金流。"
        )))

    # === 维度三：标题 ===
    title_score = data.get("title_score", 0)
    title_len = len(title.strip()) if title else 0

    if title_len < 30:
        tip = DimensionTip(
            dimension="title",
            status="warning",
            score=title_score,
            tip=f"📝 标题偏短（{title_len}字符），建议补充核心关键词，如品牌、型号、颜色。",
        )
        if is_pro:
            tip.quick_action = {"type": "ENHANCE_TITLE"}
        tips.append(asdict(tip))
    else:
        tips.append(asdict(DimensionTip(
            dimension="title",
            status="success",
            score=title_score,
            tip="✅ 标题格式良好，关键词覆盖较完整。"
        )))

    return tips


def generate_insights(
    # 扫描结果
    compliance_score: int,
    violations: List[Any],
    risk_level: Any,
    # 利润结果
    profit_result: Optional[Any] = None,
    # 机会评分
    opportunity_score: Optional[Any] = None,
    # 原始输入
    title: str = "",
    cost_price: float = 0,
    selling_price: float = 0,
    # 用户权限
    is_pro: bool = False,
    platform: str = "shopee",
) -> Dict[str, Any]:
    """
    一站式生成所有洞察建议

    Args:
        compliance_score: 合规评分（来自 scanner.calculate_score）
        violations: 违规列表（Violation 对象列表）
        risk_level: 风险等级（RiskLevel 枚举）
        profit_result: 利润计算结果（ProfitResult 对象，可为 None）
        opportunity_score: 机会评分（OpportunityScore 对象，可为 None）
        title: 商品标题
        cost_price: 成本价
        selling_price: 售价
        is_pro: 是否为 Pro 用户

    Returns:
        {
            "executive_summary": {...},
            "dimension_tips": [...]
        }
    """
    from models import RiskLevel, ViolationLevel

    # 判断是否有高风险违规
    has_high_risk = risk_level == RiskLevel.HIGH if risk_level else False

    # 判断是否有价格数据
    has_price_data = (
        profit_result is not None
        and profit_result.calculated
        and selling_price > 0
    )

    # 提取第一个违规词
    hit_word = None
    if violations:
        first_v = violations[0]
        if hasattr(first_v, "matched_word"):
            hit_word = first_v.matched_word
        elif isinstance(first_v, dict):
            hit_word = first_v.get("matched_word")

    # 构建数据字典
    data: Dict[str, Any] = {
        "compliance_score": compliance_score,
        "has_high_risk": has_high_risk,
        "has_price_data": has_price_data,
        "hit_word": hit_word,
        "title": title,
        "violations": violations,
        "platform": platform,
    }

    # 填充利润数据
    if has_price_data and profit_result:
        data["net_profit"] = profit_result.net_profit
        data["profit_margin"] = profit_result.profit_margin  # 百分比值
        data["break_even_price"] = profit_result.break_even_price
        data["cost_price"] = profit_result.cost_price
        data["selling_price"] = profit_result.selling_price
    else:
        data["net_profit"] = 0
        data["profit_margin"] = 0
        data["break_even_price"] = 0
        data["cost_price"] = cost_price
        data["selling_price"] = selling_price

    # 填充评分数据
    if opportunity_score:
        data["total_score"] = opportunity_score.score
        data["profit_score"] = opportunity_score.profit_score
        data["title_score"] = opportunity_score.competition_score
    else:
        data["total_score"] = 0
        data["profit_score"] = 0
        data["title_score"] = 0

    # 生成洞察
    summary = generate_executive_summary(data, is_pro=is_pro)
    tips = generate_dimension_tips(data, is_pro=is_pro, platform=platform)

    return {
        "executive_summary": summary,
        "dimension_tips": tips,
    }
