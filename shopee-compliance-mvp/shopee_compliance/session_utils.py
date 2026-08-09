"""
P1-1: PLG Session ID Cookie 管理
- 生成/读取/设置 plg_session_id Cookie
- 安全属性：SameSite=Lax, 非 HttpOnly（前端需要读取用于数据认领跳转）
- 过期时间：30分钟（与会话缓存 TTL 一致）
"""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse

# Cookie 名称
PLG_SESSION_COOKIE = "plg_session_id"
# Cookie 过期时间（秒）— 30分钟，与 session_cache TTL 一致
PLG_SESSION_MAX_AGE = 30 * 60


def generate_session_id() -> str:
    """生成唯一的会话ID（UUID4）"""
    return str(uuid.uuid4())


def get_session_id(request: Request) -> Optional[str]:
    """
    从请求 Cookie 中读取 plg_session_id
    返回 None 如果不存在
    """
    return request.cookies.get(PLG_SESSION_COOKIE)


def get_or_create_session_id(request: Request) -> str:
    """
    获取现有会话ID，如果不存在则生成新的
    注意：此函数只生成ID，不设置Cookie。设置Cookie需要在响应中完成。
    """
    sid = get_session_id(request)
    if sid:
        return sid
    return generate_session_id()


def set_session_cookie(response: JSONResponse, session_id: str):
    """
    在响应中设置 plg_session_id Cookie
    - 非 HttpOnly：前端 JS 需要读取（用于注册跳转时传递 session_id）
    - SameSite=Lax：防止 CSRF
    - max_age=30min：与会话缓存 TTL 一致
    """
    response.set_cookie(
        key=PLG_SESSION_COOKIE,
        value=session_id,
        max_age=PLG_SESSION_MAX_AGE,
        httponly=False,        # 前端需要读取
        samesite="lax",        # CSRF 防护
        path="/"               # 全站可读
    )


def clear_session_cookie(response: JSONResponse):
    """清除 plg_session_id Cookie（数据认领完成后）"""
    response.delete_cookie(
        key=PLG_SESSION_COOKIE,
        path="/"
    )


def is_authenticated(request: Request) -> bool:
    """
    检查用户是否已登录（通过 session_token Cookie）
    session_token 是 HttpOnly 的认证 Cookie
    """
    return bool(request.cookies.get("session_token"))
