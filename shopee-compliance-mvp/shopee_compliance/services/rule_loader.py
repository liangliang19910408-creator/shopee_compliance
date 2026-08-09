"""
词库加载抽象层
- 封装词库加载逻辑，未来可迁移到数据库
- 提供统一的规则查询接口
"""
import json
from typing import List, Dict, Any, Set
from pathlib import Path

from config import BANNED_WORDS_PATH


# 缓存：避免重复加载
_rules_cache: List[Dict[str, Any]] = []


def load_rules() -> List[Dict[str, Any]]:
    """
    加载所有违禁词规则（带缓存）
    - MVP 阶段：从 JSON 文件加载
    - 未来迁移到 DB：只需修改此函数内部实现

    Returns:
        List[Dict]: 所有违禁词规则列表
    """
    global _rules_cache

    if _rules_cache:
        return _rules_cache

    with open(BANNED_WORDS_PATH, "r", encoding="utf-8") as f:
        _rules_cache = json.load(f)

    return _rules_cache


def get_rules(platform: str = "shopee_my", product_category: str = "general") -> List[Dict[str, Any]]:
    """
    获取过滤后的违禁词规则
    - platform: 平台过滤（shopee_my / lazada_my）
    - product_category: 产品类目过滤（general / beauty / electronics / fashion / home）
    - 支持新字段 ruleType: hard_ban / soft_ban / review

    Args:
        platform: 平台标识，默认 shopee_my
        product_category: 产品类目标识，默认 general

    Returns:
        List[Dict]: 过滤后的违禁词规则列表
    """
    all_rules = load_rules()

    active_tags: Set[str] = {"_global", platform}

    filtered_by_platform = []
    for rule in all_rules:
        tags = rule.get("tags", ["_global", "shopee_my"])
        if any(t in active_tags for t in tags):
            filtered_by_platform.append(rule)

    if product_category == "general":
        return filtered_by_platform

    filtered_by_category = [
        rule for rule in filtered_by_platform
        if "general" in rule.get("applies_to", ["general"]) or product_category in rule.get("applies_to", [])
    ]
    return filtered_by_category


def clear_cache() -> None:
    """
    清除缓存（管理员更新词库后调用）
    """
    global _rules_cache
    _rules_cache = []