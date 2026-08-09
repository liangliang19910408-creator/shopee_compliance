"""
Admin 1.0 管理员路由
- 仪表盘数据（7个核心数字 + 昨日对比）
- 用户反馈看板（列表、采纳奖励、忽略）
- 紧急熔断开关（停用/恢复支付功能）
- 用户提交反馈接口

所有管理员接口需通过 session_token cookie 认证 + is_admin 字段校验。
"""
import json
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel

from config import DATABASE_PATH
from database import (
    get_db, validate_trial, is_admin,
    get_dashboard_stats,
    submit_feedback, get_feedback_list, get_feedback_by_id,
    check_recent_reward, adopt_feedback_and_reward, dismiss_feedback,
    get_system_flag, set_system_flag, log_admin_action,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============ 认证依赖 ============

async def get_admin_user(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """
    管理员认证依赖：
    1. 从 cookie 获取 session_token
    2. validate_trial 校验会话有效性
    3. is_admin 校验管理员身份
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="请先登录")

    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")

    user = result
    email = user.get("email", "")

    if not await is_admin(db, email):
        raise HTTPException(status_code=403, detail="无管理员权限")

    return user


async def get_logged_in_user(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """普通登录用户认证（用于用户提交反馈）"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="请先登录")

    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="会话已过期")

    return result


# ============ 请求模型 ============

class FeedbackRequest(BaseModel):
    content: str


class AdoptFeedbackRequest(BaseModel):
    feedback_id: int
    reward_days: int = 7


class TogglePaymentRequest(BaseModel):
    disabled: bool
    reason: str = ""


# ============ 仪表盘接口 ============

@router.get("/dashboard")
async def dashboard(user=Depends(get_admin_user), db=Depends(get_db)):
    """
    数据仪表盘 — 7个核心数字 + 昨日对比

    返回:
        total_users: 总注册用户
        trial_users: Trial 用户数
        pro_users: Pro 用户数
        free_users: Free 用户数
        pending_feedback: 待处理反馈数
        today_new_users: 今日新增注册
        today_conversions: 今日付费转化
        yesterday_new_users: 昨日新增注册
        yesterday_conversions: 昨日付费转化
        yesterday_pending_feedback: 昨日待处理反馈
    """
    stats = await get_dashboard_stats(db)
    return {"success": True, "data": stats}


# ============ 反馈看板接口 ============

@router.get("/feedback")
async def feedback_list(
    status: Optional[str] = Query(None, description="筛选状态: pending/adopted/dismissed"),
    user=Depends(get_admin_user),
    db=Depends(get_db),
):
    """获取反馈列表（支持按状态筛选）"""
    feedbacks = await get_feedback_list(db, status=status)
    return {"success": True, "data": feedbacks, "count": len(feedbacks)}


@router.post("/feedback/adopt")
async def adopt_feedback(
    body: AdoptFeedbackRequest,
    user=Depends(get_admin_user),
    db=Depends(get_db),
):
    """
    采纳反馈并奖励用户（智能延期）

    规则:
    - Free 用户 → 直接升级为 Pro（非 Trial），7天后到期
    - Trial 用户 → 升级为 Pro，到期时间在 trial_end 基础上顺延
    - Pro 用户 → 到期时间在 paid_until 基础上顺延
    - 防刷：同一用户 7 天内限一次奖励
    - 反馈内容少于 10 字不显示采纳按钮（前端控制 + 后端校验）
    """
    feedback = await get_feedback_by_id(db, body.feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")

    if feedback["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"反馈已处理（状态: {feedback['status']}）")

    # 后端校验：反馈内容少于 10 字不可采纳
    if len(feedback["content"].strip()) < 10:
        raise HTTPException(status_code=400, detail="反馈内容少于10字，不可采纳")

    # 防刷：同一用户 7 天内限一次奖励
    if await check_recent_reward(db, feedback["email"], days=7):
        raise HTTPException(status_code=400, detail="该用户7天内已获得过奖励，请稍后再试")

    # 执行采纳 + 奖励
    result = await adopt_feedback_and_reward(db, body.feedback_id, body.reward_days)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    # 记录管理员操作日志
    admin_email = user.get("email", "")
    await log_admin_action(db, admin_email, "adopt_feedback", str(body.feedback_id),
                          json.dumps({"email": result["email"], "reward_days": body.reward_days,
                                      "new_paid_until": result["new_paid_until"]}))

    # 生成可复制的 WhatsApp 文案
    wa_message = (
        f"🎉 感谢您的反馈！您的建议已被采纳。\n"
        f"作为感谢，我们已为您延长 {body.reward_days} 天 Pro 权限。\n"
        f"到期时间：{result['new_paid_until'][:10]}\n"
        f"如有更多想法，随时欢迎再来找我！"
    )

    return {
        "success": True,
        "data": result,
        "wa_message": wa_message,
    }


@router.post("/feedback/dismiss")
async def dismiss_feedback_api(
    body: AdoptFeedbackRequest,
    user=Depends(get_admin_user),
    db=Depends(get_db),
):
    """忽略反馈（不奖励）"""
    result = await dismiss_feedback(db, body.feedback_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    admin_email = user.get("email", "")
    await log_admin_action(db, admin_email, "dismiss_feedback", str(body.feedback_id), None)

    return {"success": True, "message": result["message"]}


# ============ 熔断开关接口 ============

@router.get("/payment-status")
async def payment_status(user=Depends(get_admin_user), db=Depends(get_db)):
    """获取支付功能当前状态"""
    value = await get_system_flag(db, "payment_disabled")
    disabled = value == "1"

    # 获取最近操作记录
    cursor = await db.execute("""
        SELECT * FROM admin_logs WHERE action = 'toggle_payment'
        ORDER BY created_at DESC LIMIT 5
    """)
    logs = [dict(r) for r in await cursor.fetchall()]

    return {
        "success": True,
        "data": {
            "payment_disabled": disabled,
            "logs": logs,
        }
    }


@router.post("/toggle-payment")
async def toggle_payment(
    body: TogglePaymentRequest,
    user=Depends(get_admin_user),
    db=Depends(get_db),
):
    """
    紧急熔断开关 — 停用/恢复支付功能

    停用后：
    - 用户仍可注册和试用
    - Trial 用户点击升级 Pro 时提示"支付系统维护中"
    - 已付费用户的 Pro 权益不受影响
    """
    value = "1" if body.disabled else "0"
    reason = body.reason or ("手动停用" if body.disabled else "恢复支付")

    await set_system_flag(db, "payment_disabled", value, reason)

    # 记录日志
    admin_email = user.get("email", "")
    await log_admin_action(db, admin_email, "toggle_payment", "payment_disabled",
                          json.dumps({"disabled": body.disabled, "reason": reason}))

    if body.disabled:
        message = "支付功能已停用。用户仍可注册和试用，但无法升级 Pro。"
    else:
        message = "支付功能已恢复。"

    return {
        "success": True,
        "message": message,
        "data": {"payment_disabled": body.disabled, "reason": reason},
    }


# ============ 用户提交反馈接口 ============

@router.post("/feedback/submit")
async def user_submit_feedback(
    body: FeedbackRequest,
    user=Depends(get_logged_in_user),
    db=Depends(get_db),
):
    """
    用户提交反馈（预审结果页底部入口）

    限制:
    - 内容不能为空
    - 内容最少 5 字（前端要求 10 字才能被采纳，但提交门槛低一些）
    - 最大 1000 字
    """
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="反馈内容不能为空")

    if len(content) < 5:
        raise HTTPException(status_code=400, detail="反馈内容至少5个字")

    if len(content) > 1000:
        raise HTTPException(status_code=400, detail="反馈内容不能超过1000字")

    email = user.get("email", "")
    result = await submit_feedback(db, email, content)

    return {
        "success": True,
        "message": "感谢您的反馈！我们会认真阅读每一条建议。",
        "data": result,
    }
