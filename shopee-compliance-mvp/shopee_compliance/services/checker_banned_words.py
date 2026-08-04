"""
违禁词检测器
"""
import re
import urllib.parse
from typing import List

from models import Violation, ViolationType, ViolationLevel
from services.rule_loader import get_rules

OPERATIONAL_WORDS_BLACKLIST = {
    'cod', 'limited', 'murah', 'ready', 'stock', 'pre-order', 'inden', 'asli',
    'diskon', 'harga', 'promosi', 'free', 'gift', 'bonus', 'sale', 'hot', 'new',
    'original', 'genuine', 'premium', 'best', 'no.1', 'terbaik', 'imported',
    'authentic', 'official', 'guarantee', 'warranty', 'fast', 'shipping',
    'product', 'wireless', 'headphone', 'phone', 'case', 'cover', 'accessory',
    'replacement', 'refill', 'kit', 'set', 'pack', 'box', 'bag', 'holder',
    'stand', 'charger', 'adapter', 'cable', 'battery', 'screen', 'film', 'glass',
    'protector', 'band', 'strap', 'belt', 'clip', 'mount', 'holder', 'grip',
    'handle', 'button', 'key', 'remote', 'controller', 'board', 'panel', 'frame',
    'base', 'cap', 'lid', 'plug', 'port', 'jack', 'slot', 'door', 'hinge', 'arm',
    'leg', 'wheel', 'stand', 'rack', 'shelf', 'tray', 'basket', 'container', 'pot',
    'cup', 'bowl', 'plate', 'dish', 'spoon', 'fork', 'knife', 'scissors', 'tool',
    'brush', 'comb', 'mirror', 'towel', 'cloth', 'pad', 'mat', 'paper', 'tape',
    'glue', 'sticker', 'label', 'tag', 'badge', 'pin', 'button', 'zipper', 'buckle',
    'hook', 'loop', 'string', 'rope', 'chain', 'wire', 'cable', 'tube', 'pipe',
    'hose', 'valve', 'switch', 'lever', 'knob', 'dial', 'button', 'screen', 'display',
    'light', 'lamp', 'bulb', 'fan', 'motor', 'pump', 'filter', 'tank', 'reservoir',
    'cartridge', 'pod', 'coil', 'wick', 'ceramic', 'metal', 'plastic', 'glass', 'wood',
    'leather', 'fabric', 'silicone', 'rubber', 'foam', 'sponge', 'fiber', 'mesh', 'net',
    'paper', 'card', 'board', 'foil', 'film', 'sheet', 'strip', 'rod', 'bar', 'tube',
    'ball', 'ring', 'disc', 'cone', 'cube', 'block', 'plate', 'panel', 'sheet', 'tile',
    'brick', 'stone', 'sand', 'water', 'oil', 'gas', 'air', 'steam', 'fire', 'ice'
}

BANNED_CLAIMS = ['genuine', 'premium', 'original', 'best', 'no.1', 'terbaik', 'authentic']


def normalize_title(raw_title: str) -> tuple[str, str]:
    """
    预处理归一化函数
    返回 (归一化标题用于逻辑, 原始标题用于展示)
    
    归一化规则：
    - 转小写
    - 移除 【】[](){}《》 及 -/_，替换为空格
    - 解码 URL 编码（如 %20 → 空格）
    - 移除 % 及多余空格
    """
    display_title = raw_title
    
    norm = raw_title.lower()
    norm = urllib.parse.unquote(norm)
    norm = re.sub(r'[【】\[\](){}《》\-/_%]', ' ', norm)
    norm = re.sub(r'\s+', ' ', norm).strip()
    
    return norm, display_title


VARIANT_MAP = {
    'vape': ['v@pe', 'v4pe', 'v*pe', 'va@e', 'va3e', 'va*e'],
    'vaping': ['v@ping', 'v4ping', 'va@ing', 'va3ing'],
    'e-cig': ['e-c1g', 'e-c!g', 'ecig', 'e cig', 'e-cigarette'],
    'cigarette': ['c!garette', 'c1garette', 'cig@rette'],
    'replica': ['r3plica', 'r@plica', 'repl!ca'],
    'knife': ['kn!fe', 'kn1fe'],
    'gun': ['g!n', 'g1n'],
    'ammo': ['@mmo', 'amm0'],
    'explosive': ['expl0s!ve', 'explos!ve'],
    'drugs': ['dr@gs', 'dr0gs', 'd!ugs'],
    'medicine': ['med!cine', 'med1cine'],
    'prescription': ['prescr!ption', 'prescr1ption'],
}


def load_banned_words(product_category: str = "general", include_lazada: bool = False) -> List[dict]:
    """
    从词库加载器获取违禁词列表
    - product_category: 产品类目过滤（general/beauty/electronics/fashion/home）
    - include_lazada: 是否包含 Lazada MY 规则
    """
    platform = "lazada_my" if include_lazada else "shopee_my"
    return get_rules(platform=platform, product_category=product_category)


def scan(title: str, description: str, product_category: str = "general", include_lazada: bool = False) -> List[Violation]:
    """
    扫描标题和描述中的违禁词（Phase 2 重构版）
    - 使用归一化匹配，确保连字符词与空格分隔词能正确匹配
    - product_category: 类目过滤（general/beauty/electronics/fashion/home）
    - include_lazada: 是否同时包含 Lazada MY 规则
    - 变体词不在 violations 中返回，由 hygiene 区处理（绝不自动替换）
    - 优先匹配更长的词组（如 "original guarantee"），避免被单词（如 "original"）打断
    - Shopee-only模式下：仅加载_global和shopee_my规则，纯Lazada词完全跳过
    """
    violations: List[Violation] = []
    all_banned_words = load_banned_words(product_category, include_lazada=True)

    current_platform = "lazada_my" if include_lazada else "shopee_my"
    active_tags = {"_global", current_platform}

    def is_rule_for_current_platform(item: dict) -> bool:
        tags = item.get("tags", ["_global", "shopee_my"])
        return any(t in active_tags for t in tags)

    filtered_rules = [item for item in all_banned_words if is_rule_for_current_platform(item)]

    multi_word_phrases = {item["word"].lower() for item in filtered_rules if " " in item["word"]}

    word_to_phrases: dict = {}
    for phrase in multi_word_phrases:
        for w in phrase.split():
            if w not in word_to_phrases:
                word_to_phrases[w] = []
            word_to_phrases[w].append(phrase)

    filtered_rules_sorted = sorted(filtered_rules, key=lambda x: len(x["word"]), reverse=True)

    matched_positions: dict = {}

    norm_title, _ = normalize_title(title)
    norm_description, _ = normalize_title(description)

    for item in filtered_rules_sorted:
        word = item["word"]
        level = item["level"]
        scope = item["scope"]
        reason = item["reason"]
        suggestion_text = item.get("suggestion_text", "")
        
        norm_word, _ = normalize_title(word)

        for field in scope:
            text = norm_title if field == "title" else norm_description
            if not text:
                continue

            pattern = re.escape(norm_word)
            regex = re.compile(rf'(?<![a-zA-Z]){pattern}(?![a-zA-Z])', re.IGNORECASE)

            for match in regex.finditer(text):
                start, end = match.start(), match.end()

                if field in matched_positions:
                    is_overlap = False
                    for m_start, m_end in matched_positions[field]:
                        if not (end <= m_start or start >= m_end):
                            is_overlap = True
                            break
                    if is_overlap:
                        continue

                if word in word_to_phrases:
                    is_part_of_phrase = False
                    for phrase in word_to_phrases[word]:
                        phrase_pattern = re.escape(phrase)
                        phrase_regex = re.compile(rf'(?<![a-zA-Z]){phrase_pattern}(?![a-zA-Z])', re.IGNORECASE)
                        for phrase_match in phrase_regex.finditer(text):
                            pm_start, pm_end = phrase_match.start(), phrase_match.end()
                            if start >= pm_start and end <= pm_end:
                                is_part_of_phrase = True
                                break
                        if is_part_of_phrase:
                            break

                    if is_part_of_phrase:
                        continue

                if field not in matched_positions:
                    matched_positions[field] = []
                matched_positions[field].append((start, end))

                violations.append(Violation(
                    type=ViolationType.BANNED_WORD,
                    level=ViolationLevel(level),
                    field=field,
                    matched_word=item["word"],
                    suggestion=suggestion_text,
                    reason=reason,
                    safe_title_template=item.get("safe_title_template")
                ))
                break

    return apply_exempt_combos(violations, title, description)


def apply_exempt_combos(violations: List[Violation], title: str, description: str) -> List[Violation]:
    """
    应用豁免组合规则
    - 如果标题或描述中包含豁免组合词，将对应违规降级为 INFO
    - 审计日志保留原始命中
    """
    text_lower = (title + " " + description).lower()
    from services.rule_loader import load_rules
    rules = load_rules()

    word_to_exempt_combos = {}
    for rule in rules:
        word = rule["word"].lower()
        exempt_combos = rule.get("exempt_combos", [])
        if exempt_combos:
            word_to_exempt_combos[word] = exempt_combos

    for v in violations:
        matched_word_lower = v.matched_word.lower()
        if matched_word_lower in word_to_exempt_combos:
            for combo in word_to_exempt_combos[matched_word_lower]:
                if combo.lower() in text_lower:
                    v.level = ViolationLevel.INFO
                    v.reason = f"Exempted by combo '{combo}': {v.reason}"
                    break

    return violations
