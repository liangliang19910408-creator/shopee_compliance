"""
统一权限认证工具
- is_pro 判定逻辑前后端共用
- 用户状态：free / trial / paid / trial_expired / cancelled
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
