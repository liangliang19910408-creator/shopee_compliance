"""
报告构建器 - 构建 HTML 报告所需的数据结构
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from models import Violation, RiskLevel, ViolationLevel


def build_report_data(
    title: str,
    description: str,
    category: str,
    violations: List[Violation],
    risk_level: RiskLevel
) -> Dict[str, Any]:
    """
    构建报告页面所需的完整数据结构

    Args:
        title: 商品标题
        description: 商品描述
        category: 商品类目
        violations: 违规列表
        risk_level: 风险等级

    Returns:
        Dict: 包含报告所有数据的字典
    """
    return {
        "title": title,
        "description": description,
        "category": category or "未填写",
        "risk_level": risk_level,
        "risk_label": _get_risk_label(risk_level),
        "risk_color": _get_risk_color(risk_level),
        "violations": [_format_violation(v) for v in violations],
        "violation_count": len(violations),
        "high_count": sum(1 for v in violations if v.level == ViolationLevel.HIGH),
        "medium_count": sum(1 for v in violations if v.level == ViolationLevel.MEDIUM),
        "low_count": sum(1 for v in violations if v.level == ViolationLevel.LOW),
        "scanned_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "summary": _generate_summary(violations, risk_level)
    }


def _format_violation(v: Violation) -> Dict[str, Any]:
    """格式化单个违规项"""
    return {
        "type": v.type.value,
        "type_label": _get_type_label(v.type.value),
        "level": v.level.value,
        "level_label": _get_level_label(v.level.value),
        "field": v.field,
        "field_label": "标题" if v.field == "title" else "描述",
        "matched_word": v.matched_word,
        "suggestion": v.suggestion or "",
        "reason": v.reason,
        "icon": _get_violation_icon(v.type.value, v.level.value)
    }


def _get_risk_label(level: RiskLevel) -> str:
    """获取风险等级标签"""
    labels = {
        RiskLevel.HIGH: "高风险",
        RiskLevel.MEDIUM: "中等风险",
        RiskLevel.LOW: "低风险 / 通过"
    }
    return labels.get(level, "未知")


def _get_risk_color(level: RiskLevel) -> str:
    """获取风险等级对应颜色（Tailwind CSS 类）"""
    colors = {
        RiskLevel.HIGH: "red",
        RiskLevel.MEDIUM: "yellow",
        RiskLevel.LOW: "green"
    }
    return colors.get(level, "gray")


def _get_type_label(type_val: str) -> str:
    """获取违规类型标签"""
    labels = {
        "banned_word": "违禁词",
        "category_conflict": "类目冲突"
    }
    return labels.get(type_val, type_val)


def _get_level_label(level: str) -> str:
    """获取严重程度标签"""
    labels = {
        "high": "严重",
        "medium": "中等",
        "low": "轻微"
    }
    return labels.get(level, level)


def _get_violation_icon(type_val: str, level: str) -> str:
    """获取违规图标（emoji）"""
    if type_val == "banned_word":
        return "🚫"
    elif type_val == "category_conflict":
        return "⚠️"
    return "❌"


def _generate_summary(violations: List[Violation], risk_level: RiskLevel) -> str:
    """生成检测摘要文本"""
    if not violations:
        return "恭喜！您的商品信息未检测到违规内容，符合 Shopee 马来站合规要求。"

    high_count = sum(1 for v in violations if v.level == ViolationLevel.HIGH)
    medium_count = sum(1 for v in violations if v.level == ViolationLevel.MEDIUM)

    if risk_level == RiskLevel.HIGH:
        return f"检测到 {high_count} 项严重违规和 {medium_count} 项中等风险，请立即修改。"
    elif risk_level == RiskLevel.MEDIUM:
        return f"检测到 {medium_count} 项中等风险，建议优化商品描述以提高通过率。"
    else:
        return f"检测到 {len(violations)} 项轻微问题，建议检查并优化。"
