"""
全局状态管理 - 避免循环导入
"""
import time
from datetime import timezone, timedelta, datetime

# 马来西亚时区 UTC+8（用于每日限额重置判断）
MYT = timezone(timedelta(hours=8))

# Free 用户每日扫描限制
FREE_DAILY_SCAN_LIMIT = 5

# Free 用户每日 URL 解析限制
FREE_DAILY_URL_PARSE_LIMIT = 3

# 注册 IP 限流：同 IP 每小时最多注册次数
REGISTER_IP_HOURLY_LIMIT = 3

# 临时邮箱域名黑名单
TEMP_EMAIL_DOMAINS = [
    "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "mailinator.com", "yopmail.com", "throwawaymail.com",
    "tempmail.org", "fakeinbox.com", "sharklasers.com",
    "dispostable.com", "maildrop.cc",
]

URL_PARSE_LIMIT = {}  # {ip: {count: 0, date: 'YYYY-MM-DD'}}
URL_CACHE = {}  # {url: {title: '', desc: '', timestamp: 123}}
SCAN_LIMIT = {}  # {ip: {count: 0, hour: 'YYYY-MM-DD HH'}}
REGISTER_LIMIT = {}  # {ip: {count: 0, hour: 'YYYY-MM-DD HH'}}

# ============ P0-3: 内存缓存清理机制 ============
# 缓存最大条目数（超过时触发 LRU 淘汰）
CACHE_MAX_ENTRIES = 5000
# URL_CACHE 过期时间（秒）— 2小时
URL_CACHE_TTL = 2 * 60 * 60
# 限流缓存过期时间（秒）— 25小时（覆盖跨天/跨小时场景）
RATE_LIMIT_TTL = 25 * 60 * 60


def cleanup_url_cache():
    """清理 URL_CACHE 中过期条目，并执行 LRU 淘汰"""
    now = time.time()
    # 1. 清理过期条目
    expired_keys = [
        url for url, val in URL_CACHE.items()
        if isinstance(val, dict) and (now - val.get("timestamp", 0)) > URL_CACHE_TTL
    ]
    for key in expired_keys:
        del URL_CACHE[key]

    # 2. 如果仍超过上限，按 timestamp 淘汰最旧的
    if len(URL_CACHE) > CACHE_MAX_ENTRIES:
        sorted_items = sorted(
            URL_CACHE.items(),
            key=lambda x: x[1].get("timestamp", 0) if isinstance(x[1], dict) else 0
        )
        excess = len(URL_CACHE) - CACHE_MAX_ENTRIES
        for key, _ in sorted_items[:excess]:
            del URL_CACHE[key]

    if expired_keys or len(URL_CACHE) > CACHE_MAX_ENTRIES:
        print(f"[Cache Cleanup] URL_CACHE: removed {len(expired_keys)} expired, current size: {len(URL_CACHE)}")


def cleanup_rate_limit_caches():
    """清理 SCAN_LIMIT 和 REGISTER_LIMIT 中过期的条目"""
    now = datetime.utcnow()
    current_hour_str = now.strftime("%Y-%m-%d %H")
    today_str = now.strftime("%Y-%m-%d")

    # SCAN_LIMIT: 清理非当前小时的条目
    scan_before = len(SCAN_LIMIT)
    scan_expired = [
        ip for ip, rec in SCAN_LIMIT.items()
        if isinstance(rec, dict) and rec.get("hour") != current_hour_str
    ]
    for key in scan_expired:
        del SCAN_LIMIT[key]

    # REGISTER_LIMIT: 清理非当前小时的条目
    reg_before = len(REGISTER_LIMIT)
    reg_expired = [
        ip for ip, rec in REGISTER_LIMIT.items()
        if isinstance(rec, dict) and rec.get("hour") != current_hour_str
    ]
    for key in reg_expired:
        del REGISTER_LIMIT[key]

    # URL_PARSE_LIMIT: 清理非当天的条目
    parse_before = len(URL_PARSE_LIMIT)
    parse_expired = [
        ip for ip, rec in URL_PARSE_LIMIT.items()
        if isinstance(rec, dict) and rec.get("date") != today_str
    ]
    for key in parse_expired:
        del URL_PARSE_LIMIT[key]

    # LRU 淘汰：如果仍超限，随机删除（限流缓存理论上不会太大，但做防御）
    for cache_dict, name, before in [
        (SCAN_LIMIT, "SCAN_LIMIT", scan_before),
        (REGISTER_LIMIT, "REGISTER_LIMIT", reg_before),
        (URL_PARSE_LIMIT, "URL_PARSE_LIMIT", parse_before),
    ]:
        if len(cache_dict) > CACHE_MAX_ENTRIES:
            excess = len(cache_dict) - CACHE_MAX_ENTRIES
            keys_to_remove = list(cache_dict.keys())[:excess]
            for k in keys_to_remove:
                del cache_dict[k]
            print(f"[Cache Cleanup] {name}: LRU evicted {excess} entries")

    total_removed = len(scan_expired) + len(reg_expired) + len(parse_expired)
    if total_removed > 0:
        print(f"[Cache Cleanup] Rate limits: SCAN_LIMIT {scan_before}->{len(SCAN_LIMIT)}, "
              f"REGISTER_LIMIT {reg_before}->{len(REGISTER_LIMIT)}, "
              f"URL_PARSE_LIMIT {parse_before}->{len(URL_PARSE_LIMIT)}")


def cleanup_all_caches():
    """执行全量缓存清理（供后台定时任务调用）"""
    cleanup_url_cache()
    cleanup_rate_limit_caches()
