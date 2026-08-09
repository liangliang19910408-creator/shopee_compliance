"""
机会评分系统 - 两层架构

Layer 1: 门控层（一票否决）
    - 风险等级 HIGH → 直接 0 分（合规红线）
    - 利润率 < 0 → 直接 0 分（亏损产品）

Layer 2: 加权评分层（百分制）
    - 内容合规 (30%): 基于违禁词扫描的合规评分
    - 利润健康度 (30%): 基于利润率 vs 类目阈值
    - 标题质量 (20%): 基于标题长度、关键词密度
    - 违规风险 (20%): 基于违规数量和严重程度

Layer 3: 利润惩罚层
    - 利润率为 danger 级别 → 总分上限 59（不建议）
    - 利润率为 warning 级别 → 总分上限 79（谨慎评估）
    - 确保低利润产品不会获得高评分

🔒 前置依赖：合规扫描必须先加固（ruleType + HALAL 词库）
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from models import Violation, ViolationLevel, RiskLevel
from services.profit_calculator import ProfitResult, CATEGORY_THRESHOLDS, DEFAULT_THRESHOLD


# ============ 权重配置 ============
WEIGHTS = {
    "compliance": 0.30,   # 内容合规权重
    "profit": 0.30,       # 利润健康度权重
    "competition": 0.20,  # 标题质量权重
    "risk": 0.20,         # 违规风险权重
}

# ============ 评分等级阈值 ============
SCORE_THRESHOLDS = {
    "premium": 80,   # 优秀机会
    "good": 60,      # 谨慎评估
    # < 60: 不建议
}

# ============ 利润惩罚上限 ============
MARGIN_PENALTY_CAPS = {
    "danger": 59,    # 利润率低于 warning 阈值 → 总分上限 59
    "warning": 79,   # 利润率低于 healthy 阈值 → 总分上限 79
}


@dataclass
class OpportunityScore:
    """机会评分结果"""
    score: int = 0                    # 总分 0-100
    score_level: str = "blocked"      # "premium" / "good" / "risky" / "blocked"

    # 各维度得分
    compliance_score: int = 0         # 内容合规 0-100
    profit_score: int = 0             # 利润健康度 0-100
    competition_score: int = 0        # 标题质量 0-100
    risk_score: int = 0               # 违规风险 0-100

    # 门控状态
    gate_passed: bool = False         # 是否通过门控
    gate_reason: Optional[str] = None # 未通过门控的原因

    # 利润惩罚
    margin_penalty_applied: bool = False  # 是否应用了利润惩罚
    margin_penalty_cap: Optional[int] = None  # 惩罚上限

    # 详细信息
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        # 从 details.margin_penalty 中提取更完整的惩罚信息（避免后端 api_scan 二次惩罚后字段不一致）
        penalty_details = self.details.get("margin_penalty") or {}
        cap_for_display = self.margin_penalty_cap
        # 如果 details 里记录了二次惩罚的 capped_score / applied_cap，以那个为准（与 self.score 一致）
        if penalty_details.get("capped_score") is not None:
            cap_for_display = int(penalty_details["capped_score"])
        elif penalty_details.get("applied_cap") is not None:
            cap_for_display = int(penalty_details["applied_cap"])
        # 安全检查：若 applied=True 但 cap > score，强制修正到 score
        if self.margin_penalty_applied and cap_for_display is not None and cap_for_display > self.score:
            cap_for_display = self.score
        return {
            "score": self.score,
            "score_level": self.score_level,
            "dimensions": {
                "compliance": self.compliance_score,
                "profit": self.profit_score,
                "competition": self.competition_score,
                "risk": self.risk_score,
            },
            "dimension_labels": {
                "compliance": "内容合规",
                "profit": "利润健康度",
                "competition": "标题质量",
                "risk": "违规风险",
            },
            "weights": WEIGHTS,
            "gate_passed": self.gate_passed,
            "gate_reason": self.gate_reason,
            "margin_penalty": {
                "applied": self.margin_penalty_applied,
                "cap": cap_for_display,
                "original_score": penalty_details.get("original_score"),
                "intermediate_score": penalty_details.get("intermediate_score"),
                "capped_score": penalty_details.get("capped_score") or cap_for_display,
                "source": penalty_details.get("source"),
            },
            "details": self.details,
        }


def calculate_opportunity_score(
    profit_result: Optional[ProfitResult],
    violations: List[Violation],
    risk_level: RiskLevel,
    compliance_score: int,
    title: str = "",
    description: str = "",
    category: str = "general",
) -> OpportunityScore:
    """
    计算机会评分

    Args:
        profit_result: 利润计算结果（可为None，表示未提供价格）
        violations: 违规列表
        risk_level: 风险等级
        compliance_score: 合规评分（来自 scanner.calculate_score）
        title: 商品标题
        description: 商品描述
        category: 商品类目

    Returns:
        OpportunityScore 对象
    """
    result = OpportunityScore()

    # ============ Layer 1: 门控层 ============
    # 规则1: 风险等级 HIGH → 直接淘汰
    if risk_level == RiskLevel.HIGH:
        result.gate_passed = False
        result.gate_reason = "HIGH risk violation detected - product blocked"
        result.score_level = "blocked"
        result.details["blocked_by"] = "compliance_high_risk"
        return result

    # 规则2: 利润率 < 0 → 直接淘汰（仅当提供了价格数据时）
    if profit_result and profit_result.calculated:
        if profit_result.net_profit < 0:
            result.gate_passed = False
            result.gate_reason = f"Negative net profit (RM {profit_result.net_profit:.2f}) - product loses money"
            result.score_level = "blocked"
            result.details["blocked_by"] = "negative_profit"
            result.details["net_profit"] = round(profit_result.net_profit, 2)
            return result

    result.gate_passed = True

    # ============ Layer 2: 加权评分层 ============

    # --- 2.1 合规得分 (30%) ---
    # 直接使用 scanner.calculate_score 的结果
    result.compliance_score = max(0, min(100, compliance_score))

    # --- 2.2 利润健康度 (30%) ---
    if profit_result and profit_result.calculated:
        threshold = CATEGORY_THRESHOLDS.get(category, DEFAULT_THRESHOLD)
        margin = profit_result.profit_margin

        if margin >= threshold["healthy"]:
            # 健康线以上：线性映射 80-100
            excess = margin - threshold["healthy"]
            result.profit_score = min(100, int(80 + excess * 0.5))
        elif margin >= threshold["warning"]:
            # 警告线到健康线之间：线性映射 50-80
            ratio = (margin - threshold["warning"]) / (threshold["healthy"] - threshold["warning"])
            result.profit_score = int(50 + ratio * 30)
        elif margin >= 0:
            # 0到警告线之间：线性映射 10-50
            ratio = margin / threshold["warning"] if threshold["warning"] > 0 else 0
            result.profit_score = int(10 + ratio * 40)
        else:
            result.profit_score = 0

        result.details["margin"] = round(margin, 2)
        result.details["threshold"] = threshold
        result.details["margin_level"] = profit_result.margin_level
    else:
        # 未提供价格数据，利润健康度给中性分
        result.profit_score = 50
        result.details["margin"] = None
        result.details["note"] = "No price data provided - profit score defaulted to 50"

    # --- 2.3 竞争得分 (20%) ---
    # 基于标题质量评估
    result.competition_score = _calculate_competition_score(title, description)
    result.details["title_analysis"] = {
        "length": len(title),
        "word_count": len(title.split()) if title else 0,
    }

    # --- 2.4 风险得分 (20%) ---
    # 基于违规数量和严重程度（得分越高 = 风险越低）
    result.risk_score = _calculate_risk_score(violations)
    result.details["violation_counts"] = {
        "high": sum(1 for v in violations if v.level == ViolationLevel.HIGH),
        "medium": sum(1 for v in violations if v.level == ViolationLevel.MEDIUM),
        "low": sum(1 for v in violations if v.level == ViolationLevel.LOW),
        "info": sum(1 for v in violations if v.level == ViolationLevel.INFO),
        "total": len(violations),
    }

    # ============ 总分计算 ============
    raw_score = (
        result.compliance_score * WEIGHTS["compliance"]
        + result.profit_score * WEIGHTS["profit"]
        + result.competition_score * WEIGHTS["competition"]
        + result.risk_score * WEIGHTS["risk"]
    )
    result.score = int(round(raw_score))

    # ============ Layer 3: 利润惩罚层 ============
    # 低利润产品即使其他维度得分高，也不应获得高总分
    # 记录原始 raw_score 作为基线，后端 api_scan 的二次惩罚（min_profit_threshold 红线）可据此追溯
    _original_raw = int(round(raw_score))
    if profit_result and profit_result.calculated:
        margin_level = profit_result.margin_level
        if margin_level in MARGIN_PENALTY_CAPS:
            cap = MARGIN_PENALTY_CAPS[margin_level]
            if result.score > cap:
                result.score = cap
                result.margin_penalty_applied = True
                result.margin_penalty_cap = cap
                result.details["margin_penalty"] = {
                    "original_score": _original_raw,
                    "intermediate_score": cap,
                    "capped_score": cap,
                    "margin_level": margin_level,
                    "source": "margin_warning" if margin_level == "warning" else "margin_danger",
                    "reason": f"Profit margin is {margin_level} level - score capped at {cap}",
                }

    # ============ 评分等级 ============
    if result.score >= SCORE_THRESHOLDS["premium"]:
        result.score_level = "premium"
    elif result.score >= SCORE_THRESHOLDS["good"]:
        result.score_level = "good"
    else:
        result.score_level = "risky"

    return result


def _calculate_competition_score(title: str, description: str) -> int:
    """
    计算竞争得分（基于标题质量）

    评估维度：
    - 标题长度：30-120字符为佳
    - 关键词密度：有意义的词占比
    - 品牌存在：有品牌词加分
    
    新手保护分：标题长度>5字且无违规词时，基础分60，避免首扫0分挫败感
    """
    if not title:
        return 20

    # 新手保护分：如果标题有基本内容，给予基础分60
    title_len = len(title)
    if title_len > 5:
        score = 60  # 新手保护基础分
    else:
        score = 50  # 原始基础分

    # 标题长度评估
    if 30 <= title_len <= 120:
        score += 15  # 最佳长度
    elif 15 <= title_len < 30 or 120 < title_len <= 150:
        score += 8   # 可接受长度
    elif title_len < 15:
        score -= 5   # 过短（降低惩罚，新手友好）
    # 超过150不额外扣分（已由hygiene检查处理）

    # 关键词多样性
    words = title.split()
    if words:
        unique_ratio = len(set(w.lower() for w in words)) / len(words)
        if unique_ratio >= 0.8:
            score += 10  # 关键词多样
        elif unique_ratio >= 0.5:
            score += 5

    # 品牌词检测（首字母大写的词）
    import re
    brand_candidates = re.findall(r'\b[A-Z][A-Za-z0-9]{1,20}\b', title)
    if brand_candidates:
        score += 10  # 有品牌

    # 描述存在性
    if description and len(description) > 20:
        score += 5

    return max(0, min(100, score))


def _calculate_risk_score(violations: List[Violation]) -> int:
    """
    计算风险得分（得分越高 = 风险越低）

    基于：
    - 无违规 → 100
    - 每个HIGH → -30
    - 每个MEDIUM → -10
    - 每个LOW → -3
    - 每个INFO → -1
    """
    score = 100

    for v in violations:
        if v.level == ViolationLevel.HIGH:
            score -= 30
        elif v.level == ViolationLevel.MEDIUM:
            score -= 10
        elif v.level == ViolationLevel.LOW:
            score -= 3
        elif v.level == ViolationLevel.INFO:
            score -= 1

    return max(0, score)
