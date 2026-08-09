"""
IntelliAudit 2.0 Pro 配置中心 API
- GET /api/user/preferences — 获取当前用户偏好（合并默认值）
- PUT /api/user/preferences — 更新偏好（UPSERT，按字段合并）
- GET /api/user/preferences/platform?platform=shopee — 获取指定平台偏好（扫描页 onload 回填用）

所有接口需通过 session_token cookie 认证。
偏好存储为单行 JSON 字段（user_preferences 表）。
"""
from typing import Optional, Any, List, Dict

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field

from database import (
    get_db, validate_trial, log_event,
    get_user_preferences, save_user_preferences, get_platform_preference,
)
from auth import is_pro_user, get_user_tier


router = APIRouter(prefix="/api/user", tags=["preferences"])


# ============ 认证依赖 ============

async def get_logged_in_user(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """普通登录用户认证，返回 user dict"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="请先登录")

    is_valid, result = await validate_trial(db, session_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")

    return result


# ============ Pydantic 模型 ============

class PlatformPrefs(BaseModel):
    shipping_fee: Optional[float] = None
    shipping_cost: Optional[float] = None
    default_category: Optional[str] = None
    cashback: Optional[bool] = None
    seller_type: Optional[str] = None
    target_profit_margin: Optional[float] = None
    min_profit_threshold: Optional[float] = None


class SupplierItem(BaseModel):
    name: str
    category: str = "general"
    cost: float = 0.0


class GlobalPrefs(BaseModel):
    default_currency: Optional[str] = None
    locked_exchange_rate: Optional[float] = None
    default_cost: Optional[float] = None
    suppliers: Optional[List[SupplierItem]] = None


class PreferencesUpdate(BaseModel):
    """偏好更新请求体。所有字段可选，仅更新提供的字段。"""
    platforms: Optional[Dict[str, PlatformPrefs]] = None
    global_: Optional[GlobalPrefs] = Field(default=None, alias="global")

    model_config = {"populate_by_name": True}


# ============ API 路由 ============

@router.get("/preferences")
async def get_preferences(user: dict = Depends(get_logged_in_user), db: aiosqlite.Connection = Depends(get_db)):
    """
    获取当前用户的完整偏好配置（合并默认值）。
    Free 用户也可读取（用于在配置中心 UI 显示但置灰）。
    """
    email = user.get("email", "")
    prefs = await get_user_preferences(db, email)
    return {
        "success": True,
        "preferences": prefs,
        "is_pro": is_pro_user(user),
        "tier": get_user_tier(user),
    }


@router.put("/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    user: dict = Depends(get_logged_in_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    更新偏好配置。仅 Pro 用户（paid/trial）可写入；Free 用户返回 403。
    采用字段级合并（UPSERT），不会覆盖未提交的字段。

    埋点：config_updated 事件写入 event_logs。
    """
    email = user.get("email", "")
    tier = get_user_tier(user)
    if tier == "free":
        raise HTTPException(status_code=403, detail="Pro 专属功能，请先升级")

    # 转换为 dict（支持 global 别名）
    payload: Dict[str, Any] = {}
    if body.platforms is not None:
        payload["platforms"] = {
            p: prefs.model_dump(exclude_none=True) for p, prefs in body.platforms.items()
        }
    if body.global_ is not None:
        payload["global"] = body.global_.model_dump(exclude_none=True)

    saved = await save_user_preferences(db, email, payload)

    # 埋点：config_updated
    try:
        await log_event(db, "config_updated", {
            "email": email,
            "tier": tier,
            "updated_fields": list(payload.keys()),
        })
    except Exception:
        pass

    return {
        "success": True,
        "preferences": saved,
    }


@router.get("/preferences/platform")
async def get_platform_prefs(
    platform: str = Query("shopee", pattern="^(shopee|lazada)$"),
    user: dict = Depends(get_logged_in_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    获取指定平台的偏好配置子集。扫描页 onload 回填默认值用。
    返回字段：shipping_fee/shipping_cost/default_category/cashback/seller_type/
             target_profit_margin/min_profit_threshold
    """
    email = user.get("email", "")
    prefs = await get_platform_preference(db, email, platform)
    return {
        "success": True,
        "platform": platform,
        "preferences": prefs,
        "is_pro": is_pro_user(user),
    }


# ============ 供应商预设 CRUD（Phase 2.2）============
# 三元组：{name, category, cost}
# 存储在 user_preferences.global.suppliers 数组中

async def _require_pro(user: dict):
    """Pro 权限校验，Free 用户返回 403"""
    if get_user_tier(user) == "free":
        raise HTTPException(status_code=403, detail="Pro 专属功能，请先升级")


# ============ 前端埋点上报（Phase 4.3）============
# 通用事件上报端点，供前端 JS 记录用户行为
# 已知事件：supplier_selected / target_price_viewed / history_compare_viewed

class EventLogRequest(BaseModel):
    event_name: str = Field(..., max_length=64)
    event_data: dict = Field(default_factory=dict)


@router.post("/event/log")
async def log_frontend_event(
    body: EventLogRequest,
    user: dict = Depends(get_logged_in_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    前端埋点上报。需登录用户。
    自动注入 email / tier 到 event_data，便于后续分析。
    """
    email = user.get("email", "")
    tier = get_user_tier(user)
    payload = {**body.event_data, "email": email, "tier": tier}
    try:
        await log_event(db, body.event_name, payload)
    except Exception as e:
        # 埋点失败不影响前端主流程，静默吞掉
        pass
    return {"success": True}


@router.get("/preferences/suppliers")
async def list_suppliers(
    user: dict = Depends(get_logged_in_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """获取供应商预设列表（Pro 专属，Free 可读但前端置灰）"""
    email = user.get("email", "")
    prefs = await get_user_preferences(db, email)
    suppliers = prefs.get("global", {}).get("suppliers", [])
    return {"success": True, "suppliers": suppliers, "is_pro": is_pro_user(user)}


@router.post("/preferences/suppliers")
async def add_supplier(
    item: SupplierItem,
    user: dict = Depends(get_logged_in_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """新增一个供应商预设（Pro 专属）"""
    await _require_pro(user)
    email = user.get("email", "")
    prefs = await get_user_preferences(db, email)
    suppliers = prefs.get("global", {}).get("suppliers", [])
    # 去重：同名供应商不允许
    if any(s.get("name") == item.name for s in suppliers):
        raise HTTPException(status_code=409, detail="供应商名称已存在")
    suppliers.append(item.model_dump())
    await save_user_preferences(db, email, {"global": {"suppliers": suppliers}})
    try:
        await log_event(db, "config_updated", {
            "email": email, "tier": get_user_tier(user),
            "action": "supplier_add", "supplier_name": item.name,
        })
    except Exception:
        pass
    return {"success": True, "suppliers": suppliers}


@router.put("/preferences/suppliers/{supplier_name}")
async def update_supplier(
    supplier_name: str,
    item: SupplierItem,
    user: dict = Depends(get_logged_in_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """更新指定名称的供应商预设（Pro 专属）"""
    await _require_pro(user)
    email = user.get("email", "")
    prefs = await get_user_preferences(db, email)
    suppliers = prefs.get("global", {}).get("suppliers", [])
    idx = next((i for i, s in enumerate(suppliers) if s.get("name") == supplier_name), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    # 若改名，检查新名不冲突
    if item.name != supplier_name and any(s.get("name") == item.name for s in suppliers):
        raise HTTPException(status_code=409, detail="供应商名称已存在")
    suppliers[idx] = item.model_dump()
    await save_user_preferences(db, email, {"global": {"suppliers": suppliers}})
    try:
        await log_event(db, "config_updated", {
            "email": email, "tier": get_user_tier(user),
            "action": "supplier_update", "supplier_name": item.name,
        })
    except Exception:
        pass
    return {"success": True, "suppliers": suppliers}


@router.delete("/preferences/suppliers/{supplier_name}")
async def delete_supplier(
    supplier_name: str,
    user: dict = Depends(get_logged_in_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """删除指定名称的供应商预设（Pro 专属）"""
    await _require_pro(user)
    email = user.get("email", "")
    prefs = await get_user_preferences(db, email)
    suppliers = prefs.get("global", {}).get("suppliers", [])
    new_suppliers = [s for s in suppliers if s.get("name") != supplier_name]
    if len(new_suppliers) == len(suppliers):
        raise HTTPException(status_code=404, detail="供应商不存在")
    await save_user_preferences(db, email, {"global": {"suppliers": new_suppliers}})
    try:
        await log_event(db, "config_updated", {
            "email": email, "tier": get_user_tier(user),
            "action": "supplier_delete", "supplier_name": supplier_name,
        })
    except Exception:
        pass
    return {"success": True, "suppliers": new_suppliers}
