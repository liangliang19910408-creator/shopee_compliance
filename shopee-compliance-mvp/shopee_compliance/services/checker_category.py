"""
类目规则检测器
"""
import json
from typing import List

from models import Violation, ViolationType, ViolationLevel
from config import CATEGORY_RULES_PATH


def load_category_rules() -> dict:
    """从 JSON 文件加载类目规则"""
    with open(CATEGORY_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def scan(category: str, title: str, description: str) -> List[Violation]:
    """
    检查类目与关键词的冲突
    """
    violations: List[Violation] = []

    if not category:
        return violations

    rules_data = load_category_rules()
    rules = rules_data.get("rules", [])
    category_lower = category.lower()

    for rule in rules:
        category_contains = rule.get("category_contains", "").lower()
        forbidden = rule.get("forbidden_keywords", [])
        reason = rule.get("reason", "类目规则冲突")

        if category_contains not in category_lower:
            continue

        title_lower = title.lower() if title else ""
        desc_lower = description.lower() if description else ""

        for keyword in forbidden:
            kw_lower = keyword.lower()

            if kw_lower in title_lower:
                violations.append(Violation(
                    type=ViolationType.CATEGORY_CONFLICT,
                    level=ViolationLevel.HIGH,
                    field="title",
                    matched_word=keyword,
                    suggestion=f"在「{category}」类目中，请勿使用「{keyword}」",
                    reason=reason
                ))

            if kw_lower in desc_lower:
                violations.append(Violation(
                    type=ViolationType.CATEGORY_CONFLICT,
                    level=ViolationLevel.HIGH,
                    field="description",
                    matched_word=keyword,
                    suggestion=f"在「{category}」类目中，请勿使用「{keyword}」",
                    reason=reason
                ))

    return violations
