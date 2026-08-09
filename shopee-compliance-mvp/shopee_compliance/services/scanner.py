"""
扫描调度器 - 编排规则执行顺序
"""
import re
from typing import List, Tuple, Dict, Any
from collections import Counter

from models import Violation, ViolationLevel, RiskLevel
from services.checker_banned_words import scan as banned_words_scan, VARIANT_MAP
from services.checker_category import scan as category_scan


def detect_variants(title: str, description: str = "") -> List[str]:
    """
    检测疑似变体词
    - 命中变体词（v@pe 等）时不作为 violation
    - 仅作为 hygiene 提醒，绝不自动替换
    """
    found = []
    texts = [t for t in [title, description] if t]
    if not texts:
        return found

    for base_word, variants in VARIANT_MAP.items():
        for variant in variants:
            pattern = re.compile(rf'(?<![a-zA-Z0-9]){re.escape(variant)}(?![a-zA-Z0-9])', re.IGNORECASE)
            for text in texts:
                if pattern.search(text):
                    found.append(variant)
                    break
    return found


def run_scan(title: str, description: str, product_category: str = "general", platform: str = "shopee") -> Tuple[List[Violation], RiskLevel]:
    """
    执行完整扫描流程
    - product_category: 类目过滤（general/beauty/electronics/fashion/home）
    - platform: 平台标识（shopee/lazada），平台隔离模式
    - 变体词不在 violations 中返回，仅作为 hygiene 提醒
    """
    all_violations: List[Violation] = []

    # A. 违禁词检测（带类目过滤和平台过滤）
    all_violations.extend(banned_words_scan(title, description, product_category, platform=platform))

    # B. 类目规则检测
    all_violations.extend(category_scan(product_category, title, description))

    # 计算风险等级
    risk_level = calculate_risk_level(all_violations)

    return all_violations, risk_level


def run_hygiene_check(title: str, description: str = "") -> List[Dict[str, Any]]:
    """
    Hygiene 检查（INFO级别，不影响评分）
    - 标题超过128字符
    - 同词（len>3）重复≥4次
    - 全大写占比>0.6
    - 疑似变体词提醒（绝不自动替换）
    """
    hygiene_issues = []

    # 1. 标题长度检查
    if len(title) > 128:
        hygiene_issues.append({
            "type": "title_length",
            "severity": "info",
            "message": "Title exceeds 128 characters - may be truncated on some platforms"
        })

    # 2. 重复词检查（len>3的词重复≥4次）
    words = re.findall(r'\b\w{4,}\b', title.lower())
    word_counts = Counter(words)
    for word, count in word_counts.items():
        if count >= 4:
            hygiene_issues.append({
                "type": "word_repeat",
                "severity": "info",
                "message": f"Word '{word}' repeated {count} times - consider rephrasing"
            })

    # 3. 全大写占比检查
    if title:
        uppercase_chars = sum(1 for c in title if c.isupper())
        total_chars = len(title.replace(" ", ""))  # 排除空格
        if total_chars > 0 and uppercase_chars / total_chars > 0.6:
            hygiene_issues.append({
                "type": "all_caps",
                "severity": "info",
                "message": "Excessive uppercase - reduce for better readability"
            })

    # 4. 疑似变体词提醒（灰色，仅提示不替换）
    variants = detect_variants(title, description)
    for v in variants:
        hygiene_issues.append({
            "type": "variant_word",
            "severity": "info",
            "matched_word": v,
            "message": f"检测到疑似变体词 \"{v}\"，建议修改为标准拼写。"
        })

    return hygiene_issues


def calculate_risk_level(violations: List[Violation]) -> RiskLevel:
    """
    根据违规列表计算风险等级
    - 任一 high -> HIGH
    - 任一 medium（且无 high）-> MEDIUM
    - 任一 low（且无 high/medium）-> LOW
    - 否则 SAFE
    """
    has_high = any(v.level == ViolationLevel.HIGH for v in violations)
    has_medium = any(v.level == ViolationLevel.MEDIUM for v in violations)
    has_low = any(v.level == ViolationLevel.LOW for v in violations)

    if has_high:
        return RiskLevel.HIGH
    elif has_medium:
        return RiskLevel.MEDIUM
    elif has_low:
        return RiskLevel.LOW
    else:
        return RiskLevel.SAFE


def calculate_score(violations: List[Violation]) -> int:
    """
    计算合规评分
    - 基础分 100
    - high = -50, medium = -10, low = -3
    - 最低 0 分
    - 命中 HIGH 词保证分数 < 60，显示红灯
    """
    WEIGHTS = {
        ViolationLevel.HIGH: 50,
        ViolationLevel.MEDIUM: 10,
        ViolationLevel.LOW: 3
    }
    
    total_deduction = sum(WEIGHTS.get(v.level, 0) for v in violations)
    return max(0, 100 - total_deduction)


# ============ Safe Title 生成逻辑 ============

def extract_brand(text: str, violations: List[Violation] = None) -> str:
    """
    重构后的品牌提取逻辑（Phase 2）
    核心原则：
    - 双重黑名单过滤：运营词黑名单 + 违规词库
    - 归一化匹配：基于归一化标题判断
    - 保留原始大小写格式：用于展示
    """
    from services.checker_banned_words import normalize_title, OPERATIONAL_WORDS_BLACKLIST
    from services.rule_loader import get_rules
    
    norm_title, display_title = normalize_title(text)
    
    title_hit_words = [v.matched_word.lower() for v in violations] if violations else []
    
    safe_norm = norm_title
    for word in title_hit_words:
        safe_norm = safe_norm.replace(word, '')
    
    candidates = re.findall(r'\b[A-Z][A-Za-z0-9]{1,20}\b', display_title)
    
    violation_word_list = {rule["word"].lower() for rule in get_rules()}
    
    for candidate in candidates:
        candidate_lower = candidate.lower()
        
        if candidate_lower in OPERATIONAL_WORDS_BLACKLIST:
            continue
        
        if any(black_word in candidate_lower for black_word in OPERATIONAL_WORDS_BLACKLIST):
            continue
        
        if candidate_lower in violation_word_list:
            continue
        
        if 2 <= len(candidate) <= 20:
            return f"[{candidate}]"
    
    return "[Compatible]"


def extract_model(text: str, brand: str = "") -> str:
    """从原标题中提取型号（字母数字组合），优先在 Brand 之后提取"""
    # 如果有 brand，尝试在 brand 之后提取
    if brand:
        brand_idx = text.find(brand)
        if brand_idx >= 0:
            after_brand = text[brand_idx + len(brand):]
            m = re.search(r"\b([A-Z0-9]{2,15})\b", after_brand)
            if m:
                return m.group(1)
    # 否则从整个标题提取
    m = re.search(r"\b([A-Z0-9]{2,15})\b", text)
    return m.group(1) if m else ""


def generate_safe_title(original_title: str, violations: List[Violation]) -> str:
    """
    重构后的 Safe Title 生成逻辑（Phase 2）
    核心原则：
    - 归一化先行：所有匹配、删除、品牌提取操作均基于归一化后的标题
    - 全级别清洗：无论风险等级，命中词一律删除，禁止回注
    - 中性回落：清理后若标题为空，回落至中性词
    - 绝对化宣称过滤：剔除不当宣称词（无论是否命中违规）
    """
    from services.checker_banned_words import normalize_title, BANNED_CLAIMS
    
    norm_title, display_title = normalize_title(original_title)
    
    title_hit_words = [v.matched_word for v in violations if v.field == "title"]
    
    cleaned_display = display_title
    
    all_words_to_remove = set(title_hit_words)
    
    for word in all_words_to_remove:
        norm_word = normalize_title(word)[0]
        
        pattern_str = re.escape(norm_word)
        pattern_str = pattern_str.replace(r'\ ', r'[\s\-_]+')
        
        pattern = re.compile(pattern_str, re.IGNORECASE)
        cleaned_display = pattern.sub('', cleaned_display)
    
    for claim in BANNED_CLAIMS:
        cleaned_display = re.sub(rf'\b{claim}\b', 'Quality', cleaned_display, flags=re.IGNORECASE)
    
    cleaned_display = re.sub(r'\s+', ' ', cleaned_display).strip(' [-')
    
    if not cleaned_display or cleaned_display.isspace():
        cleaned_display = "[Compatible Accessory]"
    
    cleaned_display = re.sub(r'\s+', ' ', cleaned_display).strip()
    
    return cleaned_display if cleaned_display else "[Generic Product]"


def generate_safe_title_preview(safe_title_full: str) -> str:
    """
    生成预览版 Safe Title（模糊版）
    保留品牌部分，只模糊中间和尾部
    例如: "SMOK RPM80 Empty Device Case Cover" -> "SMOK ••••"
    """
    if not safe_title_full:
        return "•" * 6

    # 提取品牌（第一个大写字母开头的词）
    brand_match = re.search(r'^([A-Z][a-zA-Z]{1,15})', safe_title_full)
    if brand_match:
        brand = brand_match.group(1)
        # 返回品牌 + 模糊符号
        return f"{brand} ••••"

    # 如果没有品牌，保留前15个字符 + 模糊
    prefix = safe_title_full[:15].strip()
    return f"{prefix} ••••"
