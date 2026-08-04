"""
API 路由 - 检测、试用、登录、支付相关接口
"""
import json
import csv
import re
import uuid
from datetime import datetime, timedelta
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import aiosqlite
import asyncio
import socket
import urllib.parse
from urllib.request import Request as UrllibRequest, urlopen
from urllib.error import URLError
import bcrypt

from models import (
    ScanRequest, ScanResponse, TrialStartRequest, TrialStartResponse,
    GenerateLoginLinkRequest, LoginLinkResponse, PaymentCallbackRequest,
    UpgradeIntentRequest, ViolationLevel, ViolationType, FetchMetaRequest, FetchMetaResponse,
    RegisterRequest, RegisterResponse, LoginRequest, LoginResponse,
    SetPasswordRequest, SetPasswordResponse, RiskLevel
)
from database import (
    get_db, create_trial, validate_trial, increment_scan_count, increment_scan_count_today, increment_scan_count_today_by_ip,
    get_trial_by_email, get_trial_by_token, upgrade_to_paid,
    create_login_token, validate_login_token,
    save_scan_history, get_scan_history, get_safe_titles,
    create_scan_session, add_scan_result, update_scan_session,
    get_scan_sessions, get_scan_results, get_today_scan_count,
    report_false_positive, log_event, save_user_whitelist, get_user_whitelist,
    check_wa_used, check_email_activated_trial, bind_wa_and_activate_trial
)
from config import WHITELIST_PATH
from auth import is_pro_user, get_trial_remaining_days
from services.scanner import run_scan, generate_safe_title, generate_safe_title_preview, calculate_score, run_hygiene_check
from globals import URL_PARSE_LIMIT, URL_CACHE, SCAN_LIMIT


router = APIRouter(prefix="/api", tags=["api"])


def parse_shopee_url(url: str) -> dict:
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        
        if "xiapibuy.com" not in hostname and "shopee.com" not in hostname:
            return {"is_shopee": False}
        
        path = parsed.path
        
        pattern = r'^(?:/product/\d+/\d+)?/(.+?)-i\.(\d+)\.(\d+)$'
        match = re.match(pattern, path)
        
        if not match:
            pattern2 = r'^/(.+?)-i\.(\d+)\.(\d+)$'
            match = re.match(pattern2, path)
        
        if not match:
            return {"is_shopee": False}
        
        title_encoded = match.group(1)
        shop_id = match.group(2)
        item_id = match.group(3)
        
        title = urllib.parse.unquote(title_encoded)
        title = title.replace("-", " ")
        
        return {
            "is_shopee": True,
            "title": title,
            "shop_id": shop_id,
            "item_id": item_id,
            "original_url": url
        }
    except Exception:
        return {"is_shopee": False}


def parse_lazada_url(url: str) -> dict:
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        
        if "lazada.com" not in hostname:
            return {"is_lazada": False}
        
        path = parsed.path
        
        pattern1 = r'^/products/(.+?)-i(\d+)(?:\.html)?$'
        match1 = re.match(pattern1, path)
        
        if match1:
            title_encoded = match1.group(1)
            item_id = match1.group(2)
            title = urllib.parse.unquote(title_encoded)
            title = title.replace("-", " ")
            return {
                "is_lazada": True,
                "title": title,
                "item_id": item_id,
                "original_url": url
            }
        
        pattern2 = r'^/products/pdp-i(\d+)-s(\d+)(?:\.html)?$'
        match2 = re.match(pattern2, path)
        
        if match2:
            item_id = match2.group(1)
            shop_id = match2.group(2)
            return {
                "is_lazada": True,
                "title": None,
                "item_id": item_id,
                "shop_id": shop_id,
                "original_url": url
            }
        
        return {"is_lazada": False}
    except Exception:
        return {"is_lazada": False}


# ============ POST /api/fetch-meta ============

@router.post("/fetch-meta", response_model=FetchMetaResponse)
async def fetch_meta(body: FetchMetaRequest, request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """
    URL 元数据解析接口
    - 未登录用户：每日5次URL解析
    - 已登录用户：每日50次URL解析
    - 相同链接24小时内直接返回缓存
    - 发起单次 GET 请求，UA 模拟浏览器
    - 超时强制 5 秒
    - 解析 HTML，提取 og:title 和 og:description
    """
    url = body.url.strip()
    if not url:
        return FetchMetaResponse(success=False, error="URL is required")

    client_ip = request.client.host
    today = datetime.utcnow().strftime("%Y-%m-%d")
    user_record = None
    is_paid_user = False
    is_logged_in = False

    token = request.cookies.get("session_token")
    if token:
        is_valid, result = await validate_trial(db, token)
        if is_valid:
            is_logged_in = True
            user_record = result
            email = user_record["email"]
            user_status = user_record["status"]
            paid_until = user_record.get("paid_until")
            now = datetime.utcnow()
            is_paid_user = user_status == "paid" and paid_until and datetime.fromisoformat(paid_until) > now

    if is_logged_in and user_record:
        email = user_record["email"]
        cursor = await db.execute("""
            SELECT url_parse_count_today, last_url_parse_date FROM trials WHERE email = ?
        """, (email,))
        row = await cursor.fetchone()
        if row:
            url_parse_count = row["url_parse_count_today"]
            last_parse_date = row["last_url_parse_date"]
            
            if last_parse_date != today:
                await db.execute("""
                    UPDATE trials SET url_parse_count_today = 0, last_url_parse_date = ? WHERE email = ?
                """, (today, email))
                await db.commit()
                url_parse_count = 0

            if is_paid_user:
                daily_limit = 50
            elif user_status == "trial":
                daily_limit = None
            else:
                daily_limit = 3
            
            if daily_limit is not None and url_parse_count >= daily_limit:
                return FetchMetaResponse(
                    success=False, 
                    error=f"今日解析次数已用完（每日{daily_limit}次），请明日再来",
                    limit_hit=True
                )
        else:
            url_parse_count = 0
            last_parse_date = today
    else:
        cursor = await db.execute("""
            SELECT * FROM trials WHERE ip_address = ? AND (email IS NULL OR email = '')
        """, (client_ip,))
        ip_record = await cursor.fetchone()

        if not ip_record:
            trial_token = str(uuid.uuid4())
            now = datetime.utcnow()
            trial_end = now + timedelta(days=365 * 100)
            await db.execute("""
                INSERT INTO trials (email, trial_token, trial_start, trial_end, ip_address, url_parse_count_today, last_url_parse_date, status, trial_status, subscription_status)
                VALUES (?, ?, ?, ?, ?, 0, ?, 'free', 'active', 'inactive')
            """, ("", trial_token, now.isoformat(), trial_end.isoformat(), client_ip, today))
            await db.commit()
            url_parse_count = 0
            last_parse_date = today
        else:
            ip_record = dict(ip_record)
            url_parse_count = ip_record.get("url_parse_count_today", 0)
            last_parse_date = ip_record.get("last_url_parse_date", "")
            
            if last_parse_date != today:
                await db.execute("""
                    UPDATE trials SET url_parse_count_today = 0, last_url_parse_date = ? WHERE ip_address = ? AND (email IS NULL OR email = '')
                """, (today, client_ip))
                await db.commit()
                url_parse_count = 0

        if url_parse_count >= 3:
            return FetchMetaResponse(
                success=False, 
                error="今日解析次数已用完（每日3次），请登录或明日再来",
                limit_hit=True
            )
    
    # 5. 缓存检查（24小时内相同链接直接返回）
    cache_record = URL_CACHE.get(url)
    if cache_record:
        if (datetime.utcnow().timestamp() - cache_record.get("timestamp", 0)) < 86400:
            return FetchMetaResponse(
                success=True,
                title=cache_record.get("title"),
                description=cache_record.get("description"),
                price_rm=cache_record.get("price_rm")
            )

    # 6. 优先尝试Shopee链接解析（从URL路径提取标题，不依赖HTTP请求）
    shopee_parse = parse_shopee_url(url)
    if shopee_parse["is_shopee"]:
        title = shopee_parse["title"]
        description = None
        price_rm = None

        URL_CACHE[url] = {
            "title": title,
            "description": description,
            "price_rm": price_rm,
            "timestamp": datetime.utcnow().timestamp()
        }

        return FetchMetaResponse(
            success=True,
            title=title,
            description=description,
            price_rm=price_rm
        )

    # 7. 尝试Lazada链接解析（从URL路径提取标题，不依赖HTTP请求）
    lazada_parse = parse_lazada_url(url)
    if lazada_parse["is_lazada"]:
        if lazada_parse["title"]:
            title = lazada_parse["title"]
            description = None
            price_rm = None

            URL_CACHE[url] = {
                "title": title,
                "description": description,
                "price_rm": price_rm,
                "timestamp": datetime.utcnow().timestamp()
            }

            return FetchMetaResponse(
                success=True,
                title=title,
                description=description,
                price_rm=price_rm
            )
        else:
            return FetchMetaResponse(
                success=False,
                error="Lazada链接格式不支持自动解析标题，请手动输入商品标题。",
                title=None,
                description=None,
                price_rm=None
            )

    allowed_domains = {"my.xiapibuy.com", "shopee.com.my", "lazada.com.my"}
    
    try:
        parsed_url = urllib.parse.urlparse(url)
        hostname = parsed_url.hostname.lower() if parsed_url.hostname else ""
        
        is_allowed = False
        for domain in allowed_domains:
            if hostname == domain or hostname.endswith("." + domain):
                is_allowed = True
                break
        
        if not is_allowed:
            return FetchMetaResponse(
                success=False,
                error="不支持的链接来源，请使用 Shopee 或 Lazada 链接。",
                title=None,
                description=None,
                price_rm=None
            )
        
        req = UrllibRequest(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        with urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')

        title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        price_match = re.search(r'<meta\s+property=["\']og:price:amount["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        currency_match = re.search(r'<meta\s+property=["\']og:price:currency["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)

        title = title_match.group(1) if title_match else None
        description = desc_match.group(1) if desc_match else None
        
        price_amount = price_match.group(1) if price_match else None
        price_currency = currency_match.group(1) if currency_match else None
        
        price_rm = None
        if price_amount and price_currency == "MYR":
            try:
                price_rm = float(price_amount)
            except (ValueError, TypeError):
                price_rm = None

        if is_logged_in and user_record:
            await db.execute("""
                UPDATE trials SET url_parse_count_today = url_parse_count_today + 1 WHERE email = ?
            """, (user_record["email"],))
            await db.commit()
        else:
            await db.execute("""
                UPDATE trials SET url_parse_count_today = url_parse_count_today + 1 WHERE ip_address = ? AND (email IS NULL OR email = '')
            """, (client_ip,))
            await db.commit()

        URL_CACHE[url] = {
            "title": title,
            "description": description,
            "price_rm": price_rm,
            "timestamp": datetime.utcnow().timestamp()
        }

        return FetchMetaResponse(
            success=True,
            title=title,
            description=description,
            price_rm=price_rm
        )

    except socket.timeout:
        # 降级：尝试返回已抓取的残缺标题（如有）
        partial = URL_CACHE.get(url, {})
        return FetchMetaResponse(
            success=False,
            error="链接解析超时，请手动粘贴标题/描述。",
            title=partial.get("title"),
            description=partial.get("description")
        )
    except URLError as e:
        return FetchMetaResponse(success=False, error="链接解析超时，请手动粘贴标题/描述。")
    except Exception as e:
        return FetchMetaResponse(success=False, error="链接解析超时，请手动粘贴标题/描述。")


# ============ POST /api/scan ============

@router.post("/scan", response_model=ScanResponse)
async def scan_product(
    body: ScanRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    商品合规检测接口
    - 免费用户（无token）：可扫描，显示违规词，但Safe Title脱敏
    - 试用用户：可扫描，Safe Title完整显示
    - 付费用户：全部功能解锁
    - 单IP每小时20次扫描硬顶（后端风控，不告知用户）
    - 计算合规评分: 100 - (high*30 + medium*10 + low*3)
    - 白名单过滤: 扫描前先替换白名单词
    - 评分等级: >=80 GO, 60-79 REVIEW, <60 STOP
    - 历史记录: 无论免费付费均写入 scan_history
    """
    token = body.token if body.token is not None else request.cookies.get("session_token")
    product_category = body.category or "general"

    # 单IP每小时20次扫描硬顶（后端风控，不告知用户）
    client_ip = request.client.host
    current_hour = datetime.utcnow().strftime("%Y-%m-%d %H")
    ip_record = SCAN_LIMIT.get(client_ip, {})
    if ip_record.get("hour") == current_hour:
        if ip_record.get("count", 0) >= 20:
            raise HTTPException(status_code=429, detail="Too many requests")
    else:
        ip_record = {"hour": current_hour, "count": 0}
    ip_record["count"] += 1
    SCAN_LIMIT[client_ip] = ip_record

    client_ip = request.client.host
    today = datetime.utcnow().strftime("%Y-%m-%d")
    is_free_user = False
    scan_count_today = 0

    if not token:
        is_free_user = True
        cursor = await db.execute("""
            SELECT * FROM trials WHERE ip_address = ? AND (email IS NULL OR email = '')
        """, (client_ip,))
        ip_record = await cursor.fetchone()

        if not ip_record:
            trial_token = str(uuid.uuid4())
            now = datetime.utcnow()
            trial_end = now + timedelta(days=365 * 100)
            await db.execute("""
                INSERT INTO trials (email, trial_token, trial_start, trial_end, ip_address, scan_count_today, last_scan_date, status, trial_status, subscription_status)
                VALUES (?, ?, ?, ?, ?, 0, ?, 'free', 'active', 'inactive')
            """, ("", trial_token, now.isoformat(), trial_end.isoformat(), client_ip, today))
            await db.commit()
            scan_count_today = 0
        else:
            ip_record = dict(ip_record)
            scan_count_today = ip_record.get("scan_count_today", 0)
            last_scan_date = ip_record.get("last_scan_date", "")
            
            if last_scan_date != today:
                await db.execute("""
                    UPDATE trials SET scan_count_today = 0, last_scan_date = ? WHERE ip_address = ? AND (email IS NULL OR email = '')
                """, (today, client_ip))
                await db.commit()
                scan_count_today = 0

        if scan_count_today >= 3:
            return ScanResponse(
                success=False,
                error="DAILY_LIMIT",
                needs_payment=True,
                product_category=product_category
            )

        email = ""
        user_status = "free"
        trial_end = None
        paid_until = None
        user = None
    else:
        is_valid, result = await validate_trial(db, token)
        if not is_valid:
            if result == "NEEDS_PAYMENT":
                return ScanResponse(success=False, error="NEEDS_PAYMENT", needs_payment=True)
            return ScanResponse(success=False, error=result)

        user = result
        email = user["email"]
        user_status = user["status"]
        trial_end = user.get("trial_end")
        paid_until = user.get("paid_until")

        if user_status in ("free", "trial_expired"):
            today = datetime.utcnow().strftime("%Y-%m-%d")
            cursor = await db.execute("""
                SELECT COALESCE(scan_count_today, 0) as scan_count_today, last_scan_date FROM trials WHERE email = ?
            """, (email,))
            row = await cursor.fetchone()
            
            scan_count_today = 0
            if row:
                row_dict = dict(row)
                scan_count_today = int(row_dict.get("scan_count_today", 0))
                last_scan_date = row_dict.get("last_scan_date", "")
                
                if last_scan_date != today:
                    await db.execute("""
                        UPDATE trials SET scan_count_today = 0, last_scan_date = ? WHERE email = ?
                    """, (today, email))
                    await db.commit()
                    scan_count_today = 0
            
            if scan_count_today >= 3:
                return ScanResponse(
                    success=False,
                    error="DAILY_LIMIT",
                    needs_payment=True,
                    product_category=product_category
                )
        elif user_status == "trial":
            scan_count_today = 0

    now = datetime.utcnow()

    is_paid = user_status == "paid" and paid_until and datetime.fromisoformat(paid_until) > now
    trial_end_dt = datetime.fromisoformat(trial_end) if trial_end else None
    is_trial_active = user_status == "trial" and trial_end_dt and trial_end_dt > now
    can_unlock_safe_title = is_paid or is_trial_active
    is_trial = is_trial_active

    # 注释掉：已移除用户可见的月扫描限制
    # can_scan, limit_reason = await check_monthly_limit(db, email)
    # if not can_scan:
    #     return ScanResponse(
    #         success=False,
    #         error=limit_reason,
    #         need_upgrade=True,
    #         product_category=product_category
    #     )

    if is_free_user:
        await db.execute("""
            UPDATE trials SET scan_count = scan_count + 1, scan_count_today = COALESCE(scan_count_today, 0) + 1 WHERE ip_address = ? AND (email IS NULL OR email = '')
        """, (client_ip,))
        await db.commit()
    else:
        await increment_scan_count(db, email)
        if user_status in ("free", "trial_expired"):
            await db.execute("""
                UPDATE trials SET scan_count_today = COALESCE(scan_count_today, 0) + 1 WHERE email = ?
            """, (email,))
            await db.commit()

    title_to_scan = body.title
    desc_to_scan = body.description or ""
    include_lazada = body.include_lazada

    shopee_parse = parse_shopee_url(body.title)
    if shopee_parse["is_shopee"]:
        title_to_scan = shopee_parse["title"]
        if not body.shop_id:
            body.shop_id = shopee_parse["shop_id"]
        if not body.item_id:
            body.item_id = shopee_parse["item_id"]
        if not body.source_type or body.source_type == 'text':
            body.source_type = 'url'

    # 使用全局白名单过滤输入文本（由管理员维护）
    try:
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            global_whitelist = json.load(f)
            for item in global_whitelist:
                word = item.get("word", "")
                if word:
                    title_to_scan = re.sub(re.escape(word), "___WL___", title_to_scan, flags=re.IGNORECASE)
                    desc_to_scan = re.sub(re.escape(word), "___WL___", desc_to_scan, flags=re.IGNORECASE)
    except Exception:
        pass

    # 使用用户个人白名单过滤（由用户维护）
    try:
        user_whitelist = await get_user_whitelist(db, email)
        if user_whitelist:
            words = [w.strip().lower() for w in user_whitelist.split(",") if w.strip()]
            for word in words:
                title_to_scan = re.sub(re.escape(word), "___WL___", title_to_scan, flags=re.IGNORECASE)
                desc_to_scan = re.sub(re.escape(word), "___WL___", desc_to_scan, flags=re.IGNORECASE)
    except Exception:
        pass

    # 执行扫描（带类目过滤和平台过滤）
    violations, risk_level = run_scan(title_to_scan, desc_to_scan, product_category, include_lazada)

    # 执行 Hygiene 检查（INFO级别，不影响评分）
    hygiene_issues = run_hygiene_check(body.title, body.description or "")

    # 计算合规评分
    score = calculate_score(violations)

    # 计算评分等级（由命中词的 level 属性决定，分数仅用于展示）
    if risk_level == RiskLevel.HIGH:
        score_level = "STOP"
    elif risk_level == RiskLevel.MEDIUM:
        score_level = "REVIEW"
    else:
        score_level = "GO"

    has_actionable_risk = len(violations) > 0

    # 生成 Safe Title（HIGH风险等级不生成，仅提示下架）
    safe_title_full = None
    safe_title_preview = None

    if has_actionable_risk and risk_level != RiskLevel.HIGH:
        safe_title_full = generate_safe_title(body.title, violations)
        if can_unlock_safe_title:
            safe_title_preview = safe_title_full
        else:
            safe_title_preview = generate_safe_title_preview(safe_title_full)

    # 生成 brief_reason（一句话原因）
    brief_reason = None
    if has_actionable_risk and violations:
        first_violation = violations[0]
        if score_level == "STOP":
            brief_reason = f'High risk violation detected: "{first_violation.matched_word}". Item may be removed.'
        else:
            brief_reason = f'Contains prohibited term "{first_violation.matched_word}"'

    # 权限控制：根据用户状态过滤返回字段
    filtered_violations = violations
    hidden_violations_info = None
    if not is_paid and not is_trial:
        high_violations = [v for v in violations if v.level == ViolationLevel.HIGH]
        other_violations = [v for v in violations if v.level != ViolationLevel.HIGH]
        
        prioritized = high_violations + other_violations
        filtered_violations = prioritized[:3]
        
        remaining_count = len(prioritized) - 3
        if remaining_count > 0:
            remaining_medium = sum(1 for v in prioritized[3:] if v.level == ViolationLevel.MEDIUM)
            remaining_info = sum(1 for v in prioritized[3:] if v.level == ViolationLevel.INFO)
            hidden_violations_info = {
                "remaining_count": remaining_count,
                "remaining_medium": remaining_medium,
                "remaining_info": remaining_info
            }

    # 保存扫描历史（无论免费付费）
    violations_dict = [v.model_dump() for v in violations]
    await save_scan_history(
        db, email, body.title[:200], risk_level.value if risk_level else 'SAFE',
        score, json.dumps(violations_dict), 
        source_type=body.source_type or 'text',
        generated_safe_title=safe_title_full,
        shop_id=body.shop_id,
        item_id=body.item_id
    )

    # 毛利计算（独立计数限制）
    gross_profit_rm = None
    margin_percent = None
    margin_level = None
    can_calculate_margin = True
    
    if body.cost_rm and body.price_rm and body.cost_rm > 0 and body.price_rm > 0:
        if not is_paid and not is_trial_active:
            margin_count_today = 0
            last_margin_date = ""
            
            if email:
                cursor = await db.execute("""
                    SELECT COALESCE(margin_count_today, 0) as margin_count_today, last_margin_date FROM trials WHERE email = ?
                """, (email,))
                row = await cursor.fetchone()
                if row:
                    row_dict = dict(row)
                    margin_count_today = int(row_dict.get("margin_count_today", 0))
                    last_margin_date = row_dict.get("last_margin_date", "")
                    
                    if last_margin_date != today:
                        await db.execute("""
                            UPDATE trials SET margin_count_today = 0, last_margin_date = ? WHERE email = ?
                        """, (today, email))
                        await db.commit()
                        margin_count_today = 0
            else:
                cursor = await db.execute("""
                    SELECT COALESCE(margin_count_today, 0) as margin_count_today, last_margin_date FROM trials WHERE ip_address = ? AND (email IS NULL OR email = '')
                """, (client_ip,))
                row = await cursor.fetchone()
                if row:
                    row_dict = dict(row)
                    margin_count_today = int(row_dict.get("margin_count_today", 0))
                    last_margin_date = row_dict.get("last_margin_date", "")
                    
                    if last_margin_date != today:
                        await db.execute("""
                            UPDATE trials SET margin_count_today = 0, last_margin_date = ? WHERE ip_address = ? AND (email IS NULL OR email = '')
                        """, (today, client_ip))
                        await db.commit()
                        margin_count_today = 0
            
            if margin_count_today >= 3:
                can_calculate_margin = False
        
        if can_calculate_margin:
            gross_profit_rm = body.price_rm - body.cost_rm
            margin_percent = (gross_profit_rm / body.price_rm) * 100
            if margin_percent >= 50:
                margin_level = "High Margin"
            elif margin_percent >= 20:
                margin_level = "Medium Margin"
            else:
                margin_level = "Low Margin"
            
            if not is_paid and not is_trial_active:
                if email:
                    await db.execute("""
                        UPDATE trials SET margin_count_today = COALESCE(margin_count_today, 0) + 1 WHERE email = ?
                    """, (email,))
                else:
                    await db.execute("""
                        UPDATE trials SET margin_count_today = COALESCE(margin_count_today, 0) + 1 WHERE ip_address = ? AND (email IS NULL OR email = '')
                    """, (client_ip,))
                await db.commit()

    # 写入新的 scan_sessions 和 scan_results（单条扫描）
    session_id = await create_scan_session(db, email, 'single')
    
    high_count = sum(1 for v in violations if v.level == ViolationLevel.HIGH)
    medium_count = sum(1 for v in violations if v.level == ViolationLevel.MEDIUM)
    low_count = sum(1 for v in violations if v.level == ViolationLevel.LOW)
    
    await add_scan_result(
        db, session_id, body.title[:200], 
        risk_level.value if risk_level else 'SAFE',
        body.cost_rm, body.price_rm, margin_percent, json.dumps(violations_dict),
        'Shopee', body.description[:500] if body.description else None,
        body.shop_id, body.item_id
    )
    
    await update_scan_session(
        db, session_id, 
        status='done',
        total_count=1,
        risk_high=high_count,
        risk_medium=medium_count,
        risk_low=low_count,
        avg_margin=margin_percent
    )

    remaining_days = 0
    if user:
        trial_end_val = user.get("trial_end")
        if trial_end_val:
            try:
                trial_end_dt = datetime.fromisoformat(trial_end_val)
                diff = trial_end_dt - datetime.utcnow()
                if diff.total_seconds() <= 0:
                    remaining_days = 0
                else:
                    remaining_days = max(0, diff.days + 1)
            except (ValueError, TypeError):
                remaining_days = 0

    # 生成报告摘要
    high_count = sum(1 for v in violations if v.level == ViolationLevel.HIGH)
    medium_count = sum(1 for v in violations if v.level == ViolationLevel.MEDIUM)
    low_count = sum(1 for v in violations if v.level == ViolationLevel.LOW)
    total_violations = len(violations)
    summary = f"{total_violations} violation(s) found - {high_count} severe, {medium_count} moderate, {low_count} minor"

    # 埋点：scan_completed
    try:
        await log_event(db, "scan_completed", {
            "email": email,
            "source": "text",
            "success": True,
            "score": score,
            "score_level": score_level,
            "risk_level": risk_level.value if risk_level else None
        })
    except Exception:
        pass

    if is_free_user or user_status in ("free", "trial_expired"):
        cursor = await db.execute("""
            SELECT COALESCE(scan_count_today, 0) as scan_count_today FROM trials WHERE email = ?
        """, (email,))
        row = await cursor.fetchone()
        scan_count_today = int(row["scan_count_today"]) if row else 0
    else:
        scan_count_today = await get_today_scan_count(db, email)

    return ScanResponse(
        success=True,
        risk_level=risk_level,
        violations=filtered_violations,
        trial_remaining_days=remaining_days,
        message="检测完成",
        summary=summary,
        brief_reason=brief_reason,
        score=score,
        score_level=score_level,
        has_actionable_risk=has_actionable_risk,
        locked=not can_unlock_safe_title,
        safe_title_preview=safe_title_preview,
        safe_title_full=safe_title_full if can_unlock_safe_title else None,
        product_category=product_category,
        title=title_to_scan,
        description=body.description or "",
        cost_rm=body.cost_rm,
        price_rm=body.price_rm,
        hygiene=hygiene_issues if hygiene_issues else None,
        scan_count_today=scan_count_today,
        gross_profit_rm=gross_profit_rm,
        margin_percent=margin_percent,
        margin_level=margin_level,
        hidden_violations_info=hidden_violations_info
    )


# ============ POST /api/scan-batch ============

@router.post("/scan-batch")
async def scan_batch(
    request: Request,
    file: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    批量扫描接口 - Pro 用户专属
    - 接收 CSV 文件上传（使用内置 csv 模块）
    - 输入列：original_title（必填），cost_rm（选填），price_rm（选填）
    - 最多处理 200 行
    - 返回 CSV 文件流，输出列：original_title, is_risk, risk_type, safe_title, cost_rm, price_rm, gross_profit_rm, margin_percent, margin_level
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Session expired")

    user = result
    email = user["email"]
    
    if not is_pro_user(user):
        raise HTTPException(
            status_code=403,
            detail={"error": "Pro required", "upgrade": True}
        )

    try:
        content = await file.read()
        csv_text = content.decode('utf-8', errors='ignore')
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to read CSV file")

    reader = csv.DictReader(StringIO(csv_text))
    rows = list(reader)

    # 限制最大 200 行
    if len(rows) > 200:
        rows = rows[:200]

    # 输出 CSV 列定义（双语表头）
    fieldnames = [
        'Title', 
        'Platform', 
        'Risk Level (风险等级)', 
        'Violations (违规词)', 
        'Cost(RM)', 
        'Price(RM)', 
        'Margin(利润率%)', 
        'Scanned At'
    ]

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    # 加载全局白名单（由管理员维护）
    global_whitelist = []
    try:
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            global_whitelist = json.load(f)
    except Exception:
        pass

    # 加载用户个人白名单（由用户维护）
    user_whitelist_words = []
    try:
        user_whitelist = await get_user_whitelist(db, email)
        if user_whitelist:
            user_whitelist_words = [w.strip().lower() for w in user_whitelist.split(",") if w.strip()]
    except Exception:
        pass

    # 创建批量扫描会话（新表）
    session_id = await create_scan_session(db, email, 'batch')
    
    total_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    total_margin = 0
    margin_count = 0

    for row in rows:
        title = row.get('original_title', '').strip()
        cost_rm = float(row.get('cost_rm', 0) or 0)
        price_rm = float(row.get('price_rm', 0) or 0)

        if not title:
            writer.writerow({
                'Title': '',
                'Platform': '',
                'Risk Level (风险等级)': '',
                'Violations (违规词)': '',
                'Cost(RM)': '',
                'Price(RM)': '',
                'Margin(利润率%)': '',
                'Scanned At': ''
            })
            continue

        # 全局白名单过滤
        title_to_scan = title
        for item in global_whitelist:
            word = item.get("word", "")
            if word:
                title_to_scan = re.sub(re.escape(word), "___WL___", title_to_scan, flags=re.IGNORECASE)

        # 用户个人白名单过滤
        for word in user_whitelist_words:
            title_to_scan = re.sub(re.escape(word), "___WL___", title_to_scan, flags=re.IGNORECASE)

        # 执行标题扫描
        violations, risk_level = run_scan(title_to_scan, "", "general")
        score = calculate_score(violations)

        # 统计风险数量
        if risk_level.value == "HIGH":
            high_count += 1
        elif risk_level.value == "MEDIUM":
            medium_count += 1
        elif risk_level.value == "LOW":
            low_count += 1

        # 提取风险类型（检测到的具体词）
        risk_types = [v.matched_word for v in violations]
        risk_type_str = ", ".join(risk_types) if risk_types else ""

        # 生成 Safe Title（HIGH风险等级不生成）
        safe_title = ""
        if len(violations) > 0 and risk_level.value != "HIGH":
            safe_title = generate_safe_title(title, violations)

        # 毛利计算
        gross_profit_rm = None
        margin_percent = None
        margin_level = None
        
        if cost_rm > 0 and price_rm > 0:
            gross_profit_rm = price_rm - cost_rm
            margin_percent = (gross_profit_rm / price_rm) * 100
            total_margin += margin_percent
            margin_count += 1
            
            if margin_percent >= 50:
                margin_level = "High Margin"
            elif margin_percent >= 20:
                margin_level = "Medium Margin"
            else:
                margin_level = "Low Margin"

        # 保存扫描历史（旧表）
        violations_dict = [v.model_dump() for v in violations]
        await save_scan_history(
            db, email, title[:200], risk_level.value if risk_level else 'SAFE',
            score, json.dumps(violations_dict), source_type='batch',
            generated_safe_title=safe_title
        )

        # 写入新表 scan_results
        await add_scan_result(
            db, session_id, title[:200],
            risk_level.value if risk_level else 'SAFE',
            cost_rm, price_rm, margin_percent, json.dumps(violations_dict)
        )

        total_count += 1

        # 格式化违规词：原文 + 类型（如 "vape (banned)"）
        violations_formatted = []
        for v in violations:
            type_label = "banned" if v.type == ViolationType.BANNED_WORD else "category"
            violations_formatted.append(f"{v.matched_word} ({type_label})")
        violations_str = ", ".join(violations_formatted)

        # 格式化日期（UTC+8 马来时区）
        scanned_at = datetime.utcnow() + timedelta(hours=8)
        scanned_at_str = scanned_at.strftime('%Y-%m-%d %H:%M')

        # 写入 CSV 行
        writer.writerow({
            'Title': title,
            'Platform': 'Shopee',
            'Risk Level (风险等级)': risk_level.value if risk_level else "SAFE",
            'Violations (违规词)': violations_str,
            'Cost(RM)': cost_rm if cost_rm > 0 else "",
            'Price(RM)': price_rm if price_rm > 0 else "",
            'Margin(利润率%)': round(margin_percent, 2) if margin_percent else "",
            'Scanned At': scanned_at_str
        })

    # 更新批量扫描会话状态
    avg_margin = total_margin / margin_count if margin_count > 0 else None
    await update_scan_session(
        db, session_id,
        status='done',
        total_count=total_count,
        risk_high=high_count,
        risk_medium=medium_count,
        risk_low=low_count,
        avg_margin=avg_margin
    )

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batch_report_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


# ============ POST /api/trial/start ============

@router.post("/trial/start", response_model=TrialStartResponse)
async def start_trial(
    body: TrialStartRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """开始试用接口"""
    client_ip = request.client.host
    now = datetime.utcnow()

    # 1. 查找该 IP 的现有记录（未绑定邮箱的记录）
    cursor = await db.execute("""
        SELECT * FROM trials WHERE ip_address = ? AND (email IS NULL OR email = '')
    """, (client_ip,))
    ip_record = await cursor.fetchone()

    # 2. 如果有 IP 记录，将邮箱绑定到该记录
    if ip_record:
        ip_record = dict(ip_record)
        trial_token = str(uuid.uuid4())
        trial_end = now + timedelta(days=7)
        
        await db.execute("""
            UPDATE trials 
            SET email = ?, trial_token = ?, trial_start = ?, trial_end = ?, status = 'trial'
            WHERE ip_address = ? AND (email IS NULL OR email = '')
        """, (body.email, trial_token, now.isoformat(), trial_end.isoformat(), client_ip))
        await db.commit()

        trial = {
            "trial_token": trial_token,
            "trial_end": trial_end.isoformat(),
            "email": body.email,
            "status": "trial"
        }
    else:
        # 3. 没有 IP 记录，直接创建新记录
        trial = await create_trial(db, body.email)

    # 埋点：email_captured
    trigger = request.headers.get("X-Trigger", "trial_start")
    try:
        await log_event(db, "email_captured", {
            "email": body.email,
            "trigger": trigger,
            "ip_address": client_ip
        })
    except Exception:
        pass

    return TrialStartResponse(
        success=True,
        token=trial["trial_token"],
        trial_end=trial["trial_end"],
        message="试用已激活，有效期 7 天"
    )


# ============ POST /api/generate_login_link ============

@router.post("/generate_login_link", response_model=LoginLinkResponse)
async def generate_login_link(
    body: GenerateLoginLinkRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    生成 Magic Link（仅付费用户可用）
    """
    trial = await get_trial_by_email(db, body.email)
    if not trial or trial["status"] != "paid":
        return LoginLinkResponse(
            success=False,
            message="Access denied. Paid users only."
        )

    token_uuid = await create_login_token(db, body.email)
    login_url = f"{str(request.base_url).rstrip('/')}/api/auth?token={token_uuid}"

    return LoginLinkResponse(
        success=True,
        message="Login link generated. Check your email (simulated).",
        login_url=login_url
    )


# ============ GET /api/auth ============

@router.get("/auth")
async def auth_callback(
    token: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Magic Link 验证 -> 设置 Session Cookie -> 重定向到 Dashboard
    """
    login_token = await validate_login_token(db, token)
    if not login_token:
        raise HTTPException(status_code=401, detail="Invalid or expired login link")

    trial = await get_trial_by_email(db, login_token["email"])
    if not trial:
        raise HTTPException(status_code=404, detail="User not found")

    redirect = RedirectResponse(url="/dashboard", status_code=302)
    redirect.set_cookie(
        key="session_token",
        value=trial["trial_token"],
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="lax"
    )
    return redirect


# ============ POST /api/upgrade-intent ============

@router.post("/upgrade-intent")
async def upgrade_intent(
    body: UpgradeIntentRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    升级意向接口
    - 用户提交邮箱后，更新 upgrade_pending_since 为当前UTC时间，billplz_bill_id 先留空
    - 如果用户不存在，先创建试用记录
    """
    trial = await get_trial_by_email(db, body.email)
    if not trial:
        trial = await create_trial(db, body.email)

    await db.execute("""
        UPDATE trials 
        SET upgrade_pending_since = ? 
        WHERE email = ?
    """, (datetime.utcnow().isoformat(), body.email))
    await db.commit()

    return {
        "success": True,
        "message": "Upgrade intent recorded.",
        "email": body.email,
        "upgrade_pending_since": datetime.utcnow().isoformat()
    }


# ============ POST /api/payment/callback (模拟) ============

@router.post("/payment/callback")
async def payment_callback(
    body: PaymentCallbackRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Billplz 支付回调模拟接口
    """
    trial = await get_trial_by_email(db, body.email)
    if not trial:
        raise HTTPException(status_code=404, detail="User not found")

    result = await upgrade_to_paid(db, body.email, body.plan_type, body.months)
    return {
        "success": True,
        "message": "Payment confirmed. Account upgraded to Pro.",
        "paid_until": result["paid_until"],
        "plan_type": result["plan_type"]
    }


# ============ GET /api/dashboard/data ============

@router.get("/dashboard/data")
async def dashboard_data(
    request: Request,
    page: int = 1,
    page_size: int = 10,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    获取仪表盘数据（需登录）
    通过 cookie 中的 token 查到 email，再以 email 为准查询
    支持分页参数 page 和 page_size
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Session expired")

    user = result
    email = user["email"]
    is_pro = is_pro_user(user)
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).isoformat()

    # 从新的 scan_sessions 表获取历史记录
    if not is_pro:
        page_size = min(page_size, 5)
        page = 1
        cursor = await db.execute("""
            SELECT * FROM scan_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET 0
        """, (email, page_size))
        rows = await cursor.fetchall()
        sessions = [dict(r) for r in rows]

        cursor = await db.execute("""
            SELECT COUNT(*) as total FROM scan_sessions
            WHERE user_id = ?
        """, (email,))
        total_row = await cursor.fetchone()
        history_total = total_row[0] if total_row else 0
    else:
        sessions, history_total = await get_scan_sessions(db, email, page, page_size)

    # 为 single 模式的 session 获取对应的 scan_result 和旧表数据
    history = []
    for session in sessions:
        session_dict = dict(session)
        if session["mode"] == "single":
            cursor = await db.execute("""
                SELECT * FROM scan_results WHERE session_id = ? LIMIT 1
            """, (session["id"],))
            result_row = await cursor.fetchone()
            
            if result_row:
                result_dict = dict(result_row)
                session_dict["title"] = result_dict.get("title", "")
                session_dict["title_snippet"] = result_dict.get("title", "")
                session_dict["description"] = result_dict.get("description", "")
                session_dict["risk"] = result_dict.get("risk", "")
                session_dict["margin"] = result_dict.get("margin", "")
                session_dict["cost_rm"] = result_dict.get("cost_rm", "")
                session_dict["price_rm"] = result_dict.get("price_rm", "")
                session_dict["violations"] = result_dict.get("violations", "")
                session_dict["scanned_at"] = result_dict.get("scanned_at", "")
            else:
                session_dict["title"] = ""
                session_dict["title_snippet"] = ""
                session_dict["risk"] = ""
                session_dict["margin"] = ""
                session_dict["cost_rm"] = ""
                session_dict["price_rm"] = ""
                session_dict["violations"] = ""
                session_dict["scanned_at"] = ""
            
            # 从旧表获取 score, title_snippet 和 generated_safe_title
            cursor = await db.execute("""
                SELECT score, title_snippet, generated_safe_title FROM scan_history 
                WHERE email = ? AND scan_time >= ? AND scan_time <= ?
                ORDER BY scan_time DESC LIMIT 1
            """, (email, session["created_at"][:19], (datetime.fromisoformat(session["created_at"]) + timedelta(seconds=10)).isoformat()[:19]))
            history_row = await cursor.fetchone()
            if history_row:
                session_dict["score"] = history_row["score"]
                if history_row["title_snippet"]:
                    session_dict["title_snippet"] = history_row["title_snippet"]
                session_dict["generated_safe_title"] = history_row["generated_safe_title"] if history_row["generated_safe_title"] else None
            else:
                session_dict["score"] = 100
                session_dict["generated_safe_title"] = None
        elif session["mode"] == "batch":
            session_dict["title"] = f"Batch Scan"
            session_dict["title_snippet"] = f"Batch Scan"
            session_dict["risk"] = ""
            session_dict["margin"] = session.get("avg_margin", "")
            session_dict["violations"] = ""
            session_dict["scanned_at"] = session.get("created_at", "")
            session_dict["score"] = 100
        
        history.append(session_dict)

    safe_titles = await get_safe_titles(db, email)
    whitelist_words = await get_user_whitelist(db, email)

    # 计算今日扫描次数（从 trials 表读取，与限制检查保持一致）
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor = await db.execute("""
        SELECT COALESCE(scan_count_today, 0) as scan_count_today, last_scan_date FROM trials WHERE email = ?
    """, (email,))
    row = await cursor.fetchone()
    scan_count_today = 0
    if row:
        row_dict = dict(row)
        scan_count_today = int(row_dict.get("scan_count_today", 0))
        if row_dict.get("last_scan_date") != today:
            scan_count_today = 0

    # 计算高风险条数
    risk_count = 0
    for session in sessions:
        risk_count += session.get("risk_high", 0)

    return {
        "email": email,
        "status": user["status"],
        "plan_type": user.get("plan_type"),
        "paid_until": user.get("paid_until"),
        "trial_end": user.get("trial_end"),
        "scan_count": user.get("scan_count", 0),
        "scan_count_today": scan_count_today,
        "scan_limit": 3 if not is_pro else None,
        "risk_count": risk_count,
        "is_pro": is_pro,
        "trial_remaining_days": get_trial_remaining_days(user),
        "has_password": bool(user.get("password_hash")),
        "wa_bound": bool(user.get("wa_number")),
        "history": history,
        "history_total": history_total,
        "safe_titles": safe_titles,
        "whitelist_words": whitelist_words or ""
    }


# ============ GET /api/history/export ============
@router.get("/history/export")
async def export_history(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    导出扫描历史为 CSV 文件（Pro 用户专属）
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    is_valid, user = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Session expired")

    email = user["email"]
    
    if not is_pro_user(user):
        raise HTTPException(
            status_code=403,
            detail={"error": "Pro required", "upgrade": True}
        )

    # 从新表 scan_sessions 获取所有会话
    cursor = await db.execute("""
        SELECT * FROM scan_sessions 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (email,))
    sessions = await cursor.fetchall()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Title', 'Platform', 'Risk Level (风险等级)', 'Violations (违规词)',
        'Cost(RM)', 'Price(RM)', 'Gross Profit(RM) (毛利)', 'Margin(利润率%)', 'Scanned At'
    ])

    for session in sessions:
        session_dict = dict(session)
        session_id = session_dict["id"]
        
        # 获取该会话的所有扫描结果
        results = await get_scan_results(db, session_id)
        
        for item in results:
            item_dict = dict(item)
            
            # Parse violations
            violations = []
            try:
                if item_dict.get('violations'):
                    violations = json.loads(item_dict['violations'])
            except:
                pass
            
            violations_formatted = []
            for v in violations:
                v_type = v.get('type', 'banned_word')
                type_label = "banned" if v_type == "banned_word" else "category"
                violations_formatted.append(f"{v.get('matched_word', v.get('word', ''))} ({type_label})")
            violations_str = ", ".join(violations_formatted)
            
            risk_level = item_dict.get('risk', 'SAFE')
            
            # Format scan_time to UTC+8
            scan_time = item_dict.get('scanned_at', '')
            if scan_time:
                try:
                    scan_dt = datetime.fromisoformat(scan_time.replace('Z', '+00:00'))
                    scan_dt = scan_dt + timedelta(hours=8)
                    scan_time_str = scan_dt.strftime('%Y-%m-%d %H:%M')
                except:
                    scan_time_str = scan_time[:16].replace('T', ' ') if scan_time else ''
            else:
                scan_time_str = ''
                
            writer.writerow([
                item_dict.get("title", ''),
                item_dict.get("platform", 'Shopee'),
                risk_level,
                violations_str,
                item_dict.get("cost_rm", '') if item_dict.get("cost_rm") else '',
                item_dict.get("price_rm", '') if item_dict.get("price_rm") else '',
                round(item_dict.get("price_rm", 0) - item_dict.get("cost_rm", 0), 2) if item_dict.get("cost_rm") and item_dict.get("price_rm") else '',
                item_dict.get("margin", '') if item_dict.get("margin") else '',
                scan_time_str
            ])

    output.seek(0)
    filename = f"scan_history_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )


# ============ POST /api/settings/whitelist ============

class WhitelistRequest(BaseModel):
    words: str

@router.post("/settings/whitelist")
async def settings_whitelist(
    body: WhitelistRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    保存用户白名单词（逗号分隔）
    - Free 用户：最多 3 个词
    - Pro 用户：不限
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Session expired")

    user = result
    email = user["email"]
    
    # Free 用户白名单限制：最多 3 个词
    if not is_pro_user(user):
        words_list = [w.strip() for w in body.words.strip().split(',') if w.strip()]
        if len(words_list) > 3:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Whitelist limit reached",
                    "upgrade": True,
                    "max_words": 3
                }
            )
    
    await save_user_whitelist(db, email, body.words.strip())

    return {"success": True, "message": "Whitelist saved"}


# ============ GET /api/user/info ============

@router.get("/user/info")
async def user_info(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    获取当前用户信息（用于首页显示）
    通过 cookie 或 localStorage token 查询
    """
    from fastapi.responses import JSONResponse
    
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        response = JSONResponse({
            "logged_in": False,
            "email": None,
            "status": None
        })
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    is_valid, result = await validate_trial(db, session_token)
    
    if not is_valid:
        if result == "NEEDS_PAYMENT":
            user = await get_trial_by_token(db, session_token)
            if user:
                email = user["email"]
                user_data = await get_trial_by_email(db, email)
                if user_data:
                    response = JSONResponse({
                        "logged_in": True,
                        "email": user_data["email"],
                        "status": user_data["status"],
                        "plan_type": user_data.get("plan_type"),
                        "paid_until": user_data.get("paid_until"),
                        "trial_end": user_data.get("trial_end"),
                        "is_pro": is_pro_user(user_data),
                        "trial_remaining_days": get_trial_remaining_days(user_data)
                    })
                    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                    return response
        
        response = JSONResponse({
            "logged_in": False,
            "email": None,
            "status": None
        })
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    user = result
    response = JSONResponse({
        "logged_in": True,
        "email": user["email"],
        "status": user["status"],
        "plan_type": user.get("plan_type"),
        "paid_until": user.get("paid_until"),
        "trial_end": user.get("trial_end"),
        "is_pro": is_pro_user(user),
        "trial_remaining_days": get_trial_remaining_days(user)
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# ============ POST /api/subscription/cancel ============

@router.post("/subscription/cancel")
async def cancel_subscription(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    取消订阅（修改为 cancelled 状态）
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Session expired")

    user = result
    email = user["email"]
    await db.execute(
        "UPDATE trials SET status = 'cancelled' WHERE email = ?",
        (email,)
    )
    await db.commit()
    return {"success": True, "message": "Subscription cancelled at period end."}


# ============ POST /api/logout ============

@router.post("/logout")
async def logout(
    request: Request,
    response: RedirectResponse = None
):
    """
    登出接口：清除 session_token cookie
    """
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"success": True, "message": "Logged out"})
    resp.delete_cookie(key="session_token", path="/", httponly=True, samesite="lax")
    return resp


class UpgradeClickedRequest(BaseModel):
    source_page: str
    button_position: str


@router.post("/upgrade-clicked")
async def upgrade_clicked(
    body: UpgradeClickedRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    埋点：upgrade_clicked 事件
    - 用户点击升级按钮时触发
    - 字段含 user_id/email/source_page/button_position/timestamp
    """
    token = request.cookies.get("session_token")
    email = "anonymous"
    user_id = None
    
    if token:
        is_valid, result = await validate_trial(db, token)
        if is_valid:
            email = result["email"]
            user_id = result["email"]
    
    try:
        await log_event(db, "upgrade_clicked", {
            "user_id": user_id,
            "email": email,
            "source_page": body.source_page,
            "button_position": body.button_position,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception:
        pass
    
    return {"success": True}


# ============ POST /api/report-false-positive ============

class FalsePositiveRequest(BaseModel):
    reported_word: str
    reason: str
    email: Optional[str] = None  # 非必填

@router.post("/report-false-positive")
async def report_false_positive_endpoint(
    body: FalsePositiveRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    误报申诉接口
    - email 非必填，为空时存储 'anonymous'
    - 防刷：同 IP 24 小时内限 1 次
    """
    client_ip = request.client.host

    # 防刷检查
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM false_positives
        WHERE (email = ? OR ? = 'anonymous') AND created_at >= ?
    """, (body.email or 'anonymous', body.email or 'anonymous', cutoff))
    row = await cursor.fetchone()

    if row['cnt'] > 0:
        return {
            "success": False,
            "message": "You have already submitted a report in the last 24 hours."
        }

    # 存储误报记录
    email_to_store = body.email.strip() if body.email and body.email.strip() else 'anonymous'

    await db.execute("""
        INSERT INTO false_positives (email, reported_word, reason, status, created_at)
        VALUES (?, ?, ?, 'pending', datetime('now'))
    """, (email_to_store, body.reported_word, body.reason))
    await db.commit()

    return {
        "success": True,
        "message": "False positive report submitted successfully.",
        "notice": "申诉词条将进入公共词库复核，审核通过后全局生效。" if email_to_store != 'anonymous' else "申诉词条已提交，但由于未提供邮箱，无法通知审核结果。"
    }


# ============ POST /api/safe-title/copied (埋点) ============

@router.post("/safe-title/copied")
async def safe_title_copied(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """埋点：safe_title_copied"""
    token = request.cookies.get("session_token")
    email = "anonymous"

    if token:
        is_valid, result = await validate_trial(db, token)
        if is_valid:
            email = result["email"]

    try:
        await log_event(db, "safe_title_copied", {"email": email})
    except Exception:
        pass

    return {"success": True}


# ============ POST /api/cron/reactivation (运营脚本) ============

@router.post("/cron/reactivation")
async def run_reactivation(
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    试用召回脚本：每周一执行
    - 找出 trial_expired 且过期满7天的用户
    - 发送唤醒邮件：'您的合规门禁已休眠，点击领取RM19特惠月卡，重新锁定Safe Title。'
    - 通过 reactivation_logs 表防止 7 天内重复打扰
    """
    from database import (
        get_trial_expired_over_7_days,
        was_reactivation_sent_recently,
        record_reactivation_sent
    )

    candidates = await get_trial_expired_over_7_days(db)
    sent_count = 0
    skipped = 0
    for user in candidates:
        email = user["email"]
        if await was_reactivation_sent_recently(db, email, days=7):
            skipped += 1
            continue
        # 模拟发送邮件（生产环境应接入真实邮件服务）
        print(f"[REACTIVATION EMAIL] To: {email}")
        print(f"  Body: 您的合规门禁已休眠，点击领取RM19特惠月卡，重新锁定Safe Title。")
        await record_reactivation_sent(db, email)
        sent_count += 1

    return {
        "success": True,
        "candidates": len(candidates),
        "sent": sent_count,
        "skipped": skipped
    }


# ============ POST /api/auth/register ============

@router.post("/auth/register")
async def register(
    body: RegisterRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    注册接口
    - 校验邮箱格式和密码强度（≥8位，含字母+数字）
    - 如果邮箱已存在，返回 409
    - 创建新用户，设置密码哈希，生成 trial_token
    """
    password_pattern = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$')
    if not password_pattern.match(body.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters and contain both letters and numbers"
        )

    existing_user = await get_trial_by_email(db, body.email)
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    password_hash = bcrypt.hashpw(body.password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

    trial_token = str(uuid.uuid4())
    now = datetime.utcnow()
    trial_end = now  # free 用户试用未激活，trial_end 设为当前时间

    await db.execute("""
        INSERT INTO trials (
            email, password_hash, trial_token, trial_start, trial_end,
            scan_count, status, trial_status, subscription_status,
            url_parse_count_today, scan_count_today
        ) VALUES (?, ?, ?, ?, ?, 0, 'free', 'inactive', 'inactive', 0, 0)
    """, (body.email, password_hash, trial_token, now.isoformat(), trial_end.isoformat()))
    await db.commit()

    from fastapi.responses import JSONResponse
    response = JSONResponse({
        "success": True,
        "email": body.email,
        "trial_token": trial_token,
        "message": "Registration successful. Bind WhatsApp to activate 7-day Pro trial."
    })
    response.set_cookie(
        key="session_token",
        value=trial_token,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="lax"
    )

    return response


# ============ POST /api/auth/login ============

@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    登录接口
    - 校验邮箱和密码
    - 如果 password_hash 为 NULL，返回 400
    - 登录成功后设置 HttpOnly cookie
    """
    # 查询用户
    user = await get_trial_by_email(db, body.email)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if user.get("password_hash"):
        if not bcrypt.checkpw(body.password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )
    else:
        pass

    # 登录成功，设置 cookie
    from fastapi.responses import JSONResponse
    response = JSONResponse({
        "success": True,
        "email": user["email"],
        "status": user["status"],
        "paid_until": user.get("paid_until"),
        "subscription_status": user.get("subscription_status", "inactive")
    })
    response.set_cookie(
        key="session_token",
        value=user["trial_token"],
        max_age=60 * 60 * 24 * 30,  # 30 天
        httponly=True,
        samesite="lax"
    )

    return response


# ============ POST /api/bind-wa ============

class BindWaRequest(BaseModel):
    wa_number: str


@router.post("/bind-wa")
async def bind_wa(
    body: BindWaRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    绑定 WhatsApp 号并激活 Trial
    - 校验 WA 号格式（E.164，马来号 +60 开头）
    - 校验 WA 号唯一性（该 WA 号是否已绑过其他账号且 Trial 未过期）
    - 绑定成功后：状态切 trial、trial_end = now+7d、记录激活时间
    - 发送 WA 模板消息
    """
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    is_valid, user = await validate_trial(db, token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    email = user["email"]
    wa_number = body.wa_number.strip()
    
    # 移除空格、连字符等分隔符，只保留数字和+号
    cleaned_wa_number = re.sub(r'[\s\-()]', '', wa_number)
    
    # 校验 WA 号格式（E.164，马来号 +60 开头，9-11位数字）
    wa_pattern = re.compile(r'^\+60\d{9,11}$')
    if not wa_pattern.match(cleaned_wa_number):
        raise HTTPException(
            status_code=400,
            detail="Invalid WhatsApp number format. Please use format like +60123456789 (Malaysian numbers only)"
        )
    
    wa_number = cleaned_wa_number
    
    # 校验 WA 号唯一性（该 WA 号是否曾用于激活试用）
    if await check_wa_used(db, wa_number):
        raise HTTPException(
            status_code=409,
            detail="This WhatsApp number has already been used to activate a trial."
        )
    
    # 校验账户是否曾激活过试用（每个账户只能试用一次）
    if await check_email_activated_trial(db, email):
        raise HTTPException(
            status_code=409,
            detail="This account has already activated a trial before."
        )
    
    # 绑定 WA 号并激活 Trial
    await bind_wa_and_activate_trial(db, email, wa_number)
    
    # 获取更新后的用户信息
    updated_user = await get_trial_by_email(db, email)
    
    # 发送 WA 模板消息（V1.0 暂只记录日志，实际 API 调用后续接入）
    trial_end_date = datetime.fromisoformat(updated_user["trial_end"])
    print(f"[WA Notification] Trial activated for {email}, WA: {wa_number}, expires: {trial_end_date.strftime('%Y-%m-%d')}")
    
    return {
        "success": True,
        "message": "Trial activated! Check your WhatsApp for confirmation.",
        "wa_number": wa_number,
        "trial_end": updated_user["trial_end"],
        "status": updated_user["status"]
    }


# ============ POST /api/auth/set-password ============

@router.post("/auth/set-password", response_model=SetPasswordResponse)
async def set_password(
    body: SetPasswordRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    设置密码接口（已登录用户）
    - 从 cookie 获取 session token
    - 校验新密码格式
    - 更新密码哈希
    """
    # 从 cookie 获取 session token
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Not logged in"
        )

    # 验证 session token
    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Session expired"
        )

    user = result
    email = user["email"]

    # 校验新密码格式
    password_pattern = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$')
    if not password_pattern.match(body.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters and contain both letters and numbers"
        )

    # 生成密码哈希并更新
    password_hash = bcrypt.hashpw(body.new_password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

    await db.execute(
        "UPDATE trials SET password_hash = ? WHERE email = ?",
        (password_hash, email)
    )
    await db.commit()

    return SetPasswordResponse(
        success=True,
        message="Password updated successfully"
    )
