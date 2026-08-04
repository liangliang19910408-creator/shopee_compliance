"""
Creem 支付路由 - Checkout / Webhook / Status
适配现有 trials 表（email 主键）和 upgrade_to_paid 逻辑
"""
import hmac
import hashlib
import json
from datetime import datetime, timedelta

import httpx
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from config import (
    CREEM_API_KEY, CREEM_WEBHOOK_SECRET, CREEM_PRODUCT_MONTHLY,
    CREEM_API_BASE, CREEM_SUCCESS_URL, CREEM_CANCEL_URL, DATABASE_PATH
)
from database import get_db, get_trial_by_email, get_trial_by_token, upgrade_to_paid
from auth import is_pro_user

router = APIRouter(prefix="/api/creem", tags=["creem"])

# Webhook 路由需要独立 prefix（Creem 配置的 webhook URL 为 /api/webhooks/creem）
webhook_router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ============ Checkout 接口 ============

class CheckoutReq(BaseModel):
    plan: str = "monthly"


@router.post("/checkout")
async def create_checkout(req: CheckoutReq, request: Request):
    """创建 Creem checkout session，从 cookie 获取当前登录用户"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        user = await get_trial_by_token(db, session_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid session")
        email = user["email"]
    finally:
        await db.close()

    payload = {
        "product_id": CREEM_PRODUCT_MONTHLY,
        "customer": {"email": email},
        "success_url": CREEM_SUCCESS_URL,
        "metadata": {"email": email, "plan": req.plan}
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CREEM_API_BASE}/v1/checkouts",
            json=payload,
            headers={"x-api-key": CREEM_API_KEY},
            timeout=15.0
        )
        if resp.status_code != 200:
            print(f"[Creem Checkout Error] {resp.status_code}: {resp.text}")
            raise HTTPException(resp.status_code, f"Creem API error: {resp.text}")

        data = resp.json()
        checkout_url = data.get("checkout_url") or data.get("url")
        if not checkout_url:
            raise HTTPException(500, "No checkout_url in Creem response")

        return {"checkout_url": checkout_url}


# ============ Webhook 接口 ============

@webhook_router.post("/creem")
async def creem_webhook(request: Request):
    """接收 Creem webhook 回调，验证签名后更新用户订阅状态"""
    raw = await request.body()
    sig = request.headers.get("creem-signature")

    if not sig:
        raise HTTPException(401, "Missing signature")

    expected_sig = hmac.new(
        CREEM_WEBHOOK_SECRET.encode(),
        raw,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, sig):
        raise HTTPException(401, "Invalid signature")

    event = json.loads(raw)
    event_type = event.get("eventType") or event.get("event_type")
    data = event.get("data", {})
    meta = data.get("metadata", {})

    # 通过 metadata.email 查找用户，fallback 到 customer_email
    email = meta.get("email") or data.get("customer_email")
    if not email:
        print(f"[Creem Webhook] No email in event {event_type}: {data}")
        return {"status": "ok"}

    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        user = await get_trial_by_email(db, email)
        if not user:
            print(f"[Creem Webhook] User not found: {email}")
            return {"status": "ok"}

        subscription_id = data.get("subscription_id") or data.get("id")
        period_end = data.get("current_period_end_date") or data.get("current_period_end")

        if event_type in ("checkout.completed", "subscription.active"):
            # 激活付费订阅
            paid_until = _parse_period_end(period_end)
            await db.execute("""
                UPDATE trials SET status='paid', plan_type='creem_pro',
                    paid_until=?, billplz_bill_id=?, subscription_status='active'
                WHERE email=?
            """, (paid_until, subscription_id, email))
            await db.commit()
            print(f"[Creem Webhook] Activated pro for {email}, until {paid_until}")

        elif event_type == "subscription.paid":
            # 续费
            paid_until = _parse_period_end(period_end)
            await db.execute("""
                UPDATE trials SET status='paid', paid_until=?, subscription_status='active'
                WHERE email=?
            """, (paid_until, email))
            await db.commit()
            print(f"[Creem Webhook] Renewed pro for {email}, until {paid_until}")

        elif event_type == "subscription.canceled":
            # 取消订阅，保持 paid 状态直到到期
            await db.execute("""
                UPDATE trials SET subscription_status='cancelled'
                WHERE email=?
            """, (email,))
            await db.commit()
            print(f"[Creem Webhook] Cancelled subscription for {email}")

        elif event_type == "subscription.expired":
            # 订阅过期，降级为 free
            await db.execute("""
                UPDATE trials SET status='free', subscription_status='inactive'
                WHERE email=?
            """, (email,))
            await db.commit()
            print(f"[Creem Webhook] Expired subscription for {email}")

        else:
            print(f"[Creem Webhook] Unhandled event type: {event_type}")

    finally:
        await db.close()

    return {"status": "ok"}


def _parse_period_end(period_end: Optional[str]) -> Optional[str]:
    """将 Creem 返回的到期时间转为 ISO 格式字符串"""
    if not period_end:
        # 默认 30 天后
        return (datetime.utcnow() + timedelta(days=30)).isoformat()
    try:
        # Creem 可能返回 "2026-09-01T00:00:00.000Z" 或时间戳
        if isinstance(period_end, (int, float)):
            return datetime.utcfromtimestamp(period_end).isoformat()
        dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None).isoformat()
    except (ValueError, TypeError):
        return (datetime.utcnow() + timedelta(days=30)).isoformat()


# ============ 状态查询接口 ============

@router.get("/status")
async def get_subscription_status(request: Request):
    """
    查询当前用户订阅状态（供前端 success 页轮询）
    返回 active（已激活）/ pending（等待中）
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        return {"status": "pending"}

    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        user = await get_trial_by_token(db, session_token)
        if not user:
            return {"status": "pending"}

        # 重新以 email 查最新状态
        user_data = await get_trial_by_email(db, user["email"])
        if not user_data:
            return {"status": "pending"}

        if is_pro_user(user_data):
            return {"status": "active", "email": user_data["email"]}
        return {"status": "pending"}
    finally:
        await db.close()
