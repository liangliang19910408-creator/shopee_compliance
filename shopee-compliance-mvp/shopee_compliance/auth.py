"""
统一权限认证工具
- is_pro 判定逻辑前后端共用
- 用户状态：free / trial / paid / trial_expired / cancelled
- get_effective_status: 实时计算用户生效状态（处理 Trial 过期降级）
- get_user_tier: 返回用户层级 free / trial / pro
"""
from datetime import datetime
from typing import Optional


def is_pro_user(user: dict) -> bool:
    """
    统一 isPro 判定逻辑
    user.status == 'paid' 且 paid_until > now
    OR user.status == 'trial' 且 trial_end > now
    """
    if not user:
        return False

    status = user.get("status", "")
    now = datetime.utcnow()

    if status == "paid":
        paid_until = user.get("paid_until")
        if paid_until:
            try:
                return datetime.fromisoformat(paid_until) > now
            except (ValueError, TypeError):
                return False
        return True

    if status == "trial":
        trial_end = user.get("trial_end")
        if trial_end:
            try:
                return datetime.fromisoformat(trial_end) > now
            except (ValueError, TypeError):
                return False
        return False

    return False


def get_effective_status(user: dict) -> str:
    """
    获取用户当前实际生效的状态（实时处理 Trial/Paid 过期降级）

    不依赖定时任务，每次请求都实时判断：
    - trial + trial_end <= now → 'trial_expired'
    - paid + paid_until <= now → 'free'
    - 其他 → 保持原 status

    Returns:
        'free' / 'trial' / 'paid' / 'trial_expired' / 'cancelled'
    """
    if not user:
        return "free"

    status = user.get("status", "free")
    now = datetime.utcnow()

    if status == "trial":
        trial_end = user.get("trial_end")
        if trial_end:
            try:
                if datetime.fromisoformat(trial_end) <= now:
                    return "trial_expired"
            except (ValueError, TypeError):
                return "trial_expired"
        else:
            return "trial_expired"

    if status == "paid":
        paid_until = user.get("paid_until")
        if paid_until:
            try:
                if datetime.fromisoformat(paid_until) <= now:
                    return "free"
            except (ValueError, TypeError):
                return "free"

    return status


def get_user_tier(user: dict) -> str:
    """
    返回用户层级（用于功能权限判断）

    Returns:
        'free'  - Free 用户（含 trial_expired、cancelled）
        'trial' - Trial 有效期内的用户
        'pro'   - Pro 付费用户（paid 且未过期）
    """
    effective = get_effective_status(user)
    if effective == "trial":
        return "trial"
    if effective == "paid":
        return "pro"
    return "free"


def get_trial_remaining_days(user: dict) -> int:
    """获取试用剩余天数（向上取整），仅对 trial 状态有效"""
    if not user or user.get("status") != "trial":
        return 0
    trial_end = user.get("trial_end")
    if not trial_end:
        return 0
    try:
        end = datetime.fromisoformat(trial_end)
        now = datetime.utcnow()
        diff = end - now
        if diff.total_seconds() <= 0:
            return 0
        from math import ceil
        return ceil(diff.total_seconds() / 86400)
    except (ValueError, TypeError):
        return 0
