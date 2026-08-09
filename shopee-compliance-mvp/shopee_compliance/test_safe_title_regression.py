"""
Safe Title 逻辑重构回归测试脚本（Phase 2）
执行全量回归测试，确保所有含 safe_title_template 的词条均符合新逻辑
"""
import json
import re
import sys
import os
import time
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.checker_banned_words import scan, normalize_title, OPERATIONAL_WORDS_BLACKLIST, BANNED_CLAIMS
from services.scanner import generate_safe_title, extract_brand
from models import Violation


def load_banned_words_with_template() -> List[Dict]:
    """加载所有含 safe_title_template 的词条"""
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'msia_banned_words.json')
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return [item for item in data if item.get('safe_title_template')]


def test_normalization():
    """测试归一化函数"""
    test_cases = [
        ("READY-STOCK Product", ("ready stock product", "READY-STOCK Product")),
        ("COD Wireless Headphone", ("cod wireless headphone", "COD Wireless Headphone")),
        ("TERBAIK Product", ("terbaik product", "TERBAIK Product")),
        ("vape%20empty%20pod", ("vape empty pod", "vape%20empty%20pod")),
        ("[Original] Brand Product", ("original brand product", "[Original] Brand Product")),
    ]
    
    print("=== 归一化测试 ===")
    all_pass = True
    for input_title, expected in test_cases:
        result = normalize_title(input_title)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_pass = False
        print(f"  {status} {input_title!r} -> {result}")
    
    return all_pass


def test_safe_title_generation():
    """测试 Safe Title 生成逻辑"""
    print("\n=== Safe Title 生成测试 ===")
    
    test_cases = [
        ("vape empty pod", ["vape"], "empty pod"),
        ("vape pod", ["vape"], "pod"),
        ("TERBAIK Product", ["terbaik"], "Product"),
        ("Genuine Brand Product", ["genuine"], "Brand Product"),
        ("READY-STOCK COD Wireless", ["ready stock", "cod"], "Wireless"),
        ("Replica Watch", ["replica"], "Watch"),
        ("Original Brand Headphone", ["original"], "Brand Headphone"),
        ("Premium Quality Product", ["premium"], "Quality Product"),
        ("Genuine TERBAIK Product", [], "Quality Quality Product"),
        ("Generic Genuine Item", [], "Generic Quality Item"),
    ]
    
    all_pass = True
    for title, hit_words, expected in test_cases:
        violations = []
        for word in hit_words:
            from models import ViolationType, ViolationLevel
            violations.append(Violation(
                type=ViolationType.BANNED_WORD,
                level=ViolationLevel.HIGH,
                field="title",
                matched_word=word,
                suggestion="",
                reason="",
                safe_title_template=""
            ))
        
        result = generate_safe_title(title, violations)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_pass = False
        print(f"  {status} {title!r} -> {result!r} (expected: {expected!r})")
    
    return all_pass


def test_brand_extraction():
    """测试品牌提取逻辑"""
    print("\n=== 品牌提取测试 ===")
    
    test_cases = [
        ("READY-STOCK Product", [], "[Compatible]"),
        ("COD Wireless", [], "[Compatible]"),
        ("TERBAIK Product", [], "[Compatible]"),
        ("SMOK Vape Pod", ["vape"], "[SMOK]"),
        ("Apple iPhone", [], "[Apple]"),
        ("Original Xiaomi Phone", ["original"], "[Xiaomi]"),
        ("PREMIUM Samsung TV", ["premium"], "[Samsung]"),
        ("Ready Stock Brand X", ["ready stock"], "[Brand]"),
    ]
    
    all_pass = True
    for title, hit_words, expected in test_cases:
        violations = []
        for word in hit_words:
            from models import ViolationType, ViolationLevel
            violations.append(Violation(
                type=ViolationType.BANNED_WORD,
                level=ViolationLevel.HIGH,
                field="title",
                matched_word=word,
                suggestion="",
                reason="",
                safe_title_template=""
            ))
        
        result = extract_brand(title, violations)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_pass = False
        print(f"  {status} {title!r} -> {result!r} (expected: {expected!r})")
    
    return all_pass


def test_full_regression():
    """全量回归测试 - 遍历所有含 safe_title_template 的词条"""
    print("\n=== 全量回归测试 ===")
    
    banned_words_with_template = load_banned_words_with_template()
    print(f"共找到 {len(banned_words_with_template)} 个含 safe_title_template 的词条")
    
    passed = 0
    failed = 0
    
    for item in banned_words_with_template:
        word = item["word"]
        level = item["level"]
        template = item.get("safe_title_template", "")
        tags = item.get("tags", ["_global", "shopee_my"])
        
        test_title = f"{word} Item"
        
        platform = "lazada" if ("lazada_my" in tags and "_global" not in tags) else "shopee"
        violations = scan(test_title, "", "general", platform=platform)
        
        safe_title = generate_safe_title(test_title, violations)
        
        word_lower = word.lower()
        contains_original_word = word_lower in safe_title.lower()
        
        contains_blacklist_word = any(
            black_word in safe_title.lower() 
            for black_word in OPERATIONAL_WORDS_BLACKLIST
        )
        
        contains_banned_claim = any(
            claim in safe_title.lower() 
            for claim in BANNED_CLAIMS
        )
        
        if contains_original_word or contains_blacklist_word or contains_banned_claim:
            failed += 1
            print(f"  ❌ FAIL: '{word}' -> '{safe_title}'")
            if contains_original_word:
                print(f"     - 包含原词: '{word}'")
            if contains_blacklist_word:
                print(f"     - 包含黑名单词")
            if contains_banned_claim:
                print(f"     - 包含绝对化宣称词")
        else:
            passed += 1
            print(f"  ✅ PASS: '{word}' -> '{safe_title}'")
    
    print(f"\n回归测试结果: {passed}/{len(banned_words_with_template)} 通过")
    return passed == len(banned_words_with_template)


def test_performance():
    """性能基准测试"""
    print("\n=== 性能基准测试 ===")
    
    test_titles = [
        "vape empty pod replacement accessories",
        "READY-STOCK COD Wireless Headphone",
        "TERBAIK Original Premium Brand Product",
        "replica watch luxury brand",
        "e-cig cartridge refill",
    ]
    
    iterations = 100
    total_time = 0
    
    for _ in range(iterations):
        for title in test_titles:
            start = time.time()
            violations = scan(title, "", "general", False)
            generate_safe_title(title, violations)
            extract_brand(title, violations)
            end = time.time()
            total_time += (end - start)
    
    avg_time_ms = (total_time / (iterations * len(test_titles))) * 1000
    print(f"平均单次扫描耗时: {avg_time_ms:.2f}ms")
    print(f"性能目标: < 270ms (当前基线约 220ms + 新增逻辑 < 50ms)")
    
    return avg_time_ms < 270


def main():
    """执行所有测试"""
    print("=" * 60)
    print("Safe Title 逻辑重构回归测试（Phase 2）")
    print("=" * 60)
    
    results = []
    
    results.append(("归一化测试", test_normalization()))
    results.append(("Safe Title 生成测试", test_safe_title_generation()))
    results.append(("品牌提取测试", test_brand_extraction()))
    results.append(("全量回归测试", test_full_regression()))
    results.append(("性能基准测试", test_performance()))
    
    print("\n" + "=" * 60)
    print("测试汇总:")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False
    
    print("=" * 60)
    
    if all_pass:
        print("🎉 所有测试通过！可以上线。")
        sys.exit(0)
    else:
        print("⚠️ 部分测试失败，请检查并修复。")
        sys.exit(1)


if __name__ == "__main__":
    main()
