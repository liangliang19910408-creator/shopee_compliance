"""
Pydantic Schemas - 请求/响应数据模型
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SAFE = "SAFE"


class ViolationType(str, Enum):
    BANNED_WORD = "banned_word"
    CATEGORY_CONFLICT = "category_conflict"


class ViolationLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class UserStatus(str, Enum):
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"
    PAID = "paid"
    CANCELLED = "cancelled"


# ============ 请求模型 ============

class ScanRequest(BaseModel):
    """检测请求"""
    token: Optional[str] = Field(None, description="试用 Token")
    title: str = Field(..., description="商品标题")
    category: Optional[str] = Field(None, description="商品类目")
    description: Optional[str] = Field(None, description="商品描述")
    platform: Optional[str] = Field("shopee", description="平台: shopee/lazada")
    cost_rm: Optional[float] = Field(None, description="预估成本价 (RM)")
    price_rm: Optional[float] = Field(None, description="预估售价 (RM)")
    shipping_fee: Optional[float] = Field(None, description="买家支付的运费 (RM)")
    shipping_cost: Optional[float] = Field(None, description="卖家发货成本 (RM)")
    seller_type: Optional[str] = Field("marketplace", description="卖家类型: marketplace/mall")
    cashback_enabled: Optional[bool] = Field(True, description="是否参与返现计划")
    source_type: Optional[str] = Field("text", description="来源类型：text/url")
    shop_id: Optional[str] = Field(None, description="Shopee店铺ID")
    item_id: Optional[str] = Field(None, description="Shopee商品ID")


class TrialStartRequest(BaseModel):
    """开始试用请求"""
    email: EmailStr


class GenerateLoginLinkRequest(BaseModel):
    """生成登录链接请求"""
    email: EmailStr


class PaymentCallbackRequest(BaseModel):
    """支付回调请求 (模拟)"""
    email: EmailStr
    plan_type: str = "compliance_pro"
    months: int = 1


class UpgradeIntentRequest(BaseModel):
    """升级意向请求"""
    email: EmailStr


# ============ 响应模型 ============

class Violation(BaseModel):
    """违规项"""
    type: ViolationType
    level: ViolationLevel
    field: str
    matched_word: str
    suggestion: Optional[str] = None
    reason: str
    safe_title_template: Optional[str] = None  # Safe Title 模板
    rule_type: Optional[str] = None  # "hard_ban" / "soft_ban" / "review"


class ScanResponse(BaseModel):
    """检测响应"""
    success: bool
    error: Optional[str] = None
    needs_payment: bool = False
    need_upgrade: bool = False  # 月扫描限制
    risk_level: Optional[RiskLevel] = None
    violations: Optional[List[Violation]] = None
    trial_remaining_days: Optional[int] = None
    message: Optional[str] = None
    summary: Optional[str] = None  # 报告摘要
    brief_reason: Optional[str] = None  # 一句话原因，如 "Contains prohibited term 'vape'"
    # 合规评分
    score: int = 100  # 100 - 风险词权重总和，最低0
    score_level: str = "GO"  # GO/REVIEW/STOP
    # Safe Title 相关字段
    has_actionable_risk: bool = False
    locked: bool = True  # 免费/试用过期=true；付费=false
    safe_title_preview: Optional[str] = None  # 模糊预览
    safe_title_full: Optional[str] = None  # 完整 Safe Title（付费用户）
    # 类目相关
    product_category: str = "general"
    # Hygiene 检查结果（INFO级别，不影响评分）
    hygiene: Optional[List[dict]] = None  # [{"type": "title_length", "message": "..."}]
    # 当日扫描次数
    scan_count_today: int = 0
    # 毛利计算结果（兼容旧字段）
    gross_profit_rm: Optional[float] = None
    margin_percent: Optional[float] = None
    margin_level: Optional[str] = None  # "High Margin" / "Medium Margin" / "Low Margin"
    # 原始输入数据（用于结果页回显）
    title: Optional[str] = None
    description: Optional[str] = None
    cost_rm: Optional[float] = None
    price_rm: Optional[float] = None
    # 免费版隐藏违规信息
    hidden_violations_info: Optional[dict] = None
    # Phase 1 新增：利润分析（完整费用拆解）
    profit_analysis: Optional[dict] = None  # ProfitResult.to_dict()
    # Phase 1 新增：机会评分
    opportunity_score: Optional[dict] = None  # OpportunityScore.to_dict()
    # Phase 2 新增：洞察建议引擎
    executive_summary: Optional[dict] = None  # {"level": "error/warning/success/info", "message": "...", "action": "..."}
    dimension_tips: Optional[List[dict]] = None  # 分维度改进建议
    is_pro: bool = False  # 是否为Pro用户（前端用于功能差异化展示）
    # P1-2: PLG 会话相关字段（未登录用户）
    scan_timestamp: Optional[str] = None  # 扫描时间戳（ISO格式，用于前端恢复显示）
    session_expires_in: Optional[int] = None  # 会话剩余有效分钟数
    # IntelliAudit 2.0: 顶部状态栏动态文案类型（EXCELLENT / WARNING / CRITICAL）
    risk_type: Optional[str] = None
    # IntelliAudit 2.0 Pro: 利润红线击穿标记（net_profit < min_profit_threshold 时触发）
    profit_alert_triggered: Optional[bool] = None
    # IntelliAudit 2.0 Pro Phase 2.1: 货币/汇率偏好
    # currency: 用户输入时使用的货币代码（如 "RM"/"CNY"），profit_analysis 始终为 RM
    currency: Optional[str] = None
    # exchange_rate: 转换使用的汇率（1 RM = X user_currency），None 表示未转换
    exchange_rate: Optional[float] = None
    # IntelliAudit 2.0 Pro Phase 3.1: 历史对比（Jaccard 相似度 + 新增/已解决违规词）
    history_comparison: Optional[dict] = None


class FetchMetaRequest(BaseModel):
    """URL 元数据获取请求"""
    url: str = Field(..., description="商品链接")


class FetchMetaResponse(BaseModel):
    """URL 元数据获取响应"""
    success: bool
    title: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None
    limit_hit: bool = False
    price_rm: Optional[float] = None  # 预估售价 (RM) - 仅当 currency=MYR 时返回


class WhitelistRequest(BaseModel):
    """白名单设置请求"""
    words: str = Field(..., description="逗号分隔的白名单词")


class TrialStartResponse(BaseModel):
    """开始试用响应"""
    success: bool
    token: Optional[str] = None
    trial_end: Optional[str] = None
    message: Optional[str] = None


class LoginLinkResponse(BaseModel):
    """登录链接响应"""
    success: bool
    message: str
    login_url: Optional[str] = None


class DashboardDataResponse(BaseModel):
    """仪表盘数据响应"""
    email: str
    status: str
    plan_type: Optional[str] = None
    paid_until: Optional[str] = None
    trial_end: Optional[str] = None
    scan_count: int = 0


# ============ 密码认证相关模型 ============

class RegisterRequest(BaseModel):
    """注册请求"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="密码至少8位，需包含字母和数字")
    wa_number: str = Field(..., description="WhatsApp号码（E.164格式，如+60123456789），V1.0 必填，注册即激活 14 天 Trial")


class LoginRequest(BaseModel):
    """登录请求"""
    email: EmailStr
    password: str


class SetPasswordRequest(BaseModel):
    """设置密码请求"""
    new_password: str = Field(..., min_length=8, description="密码至少8位，需包含字母和数字")


class RegisterResponse(BaseModel):
    """注册响应"""
    success: bool
    email: Optional[str] = None
    trial_token: Optional[str] = None
    message: Optional[str] = None


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    email: Optional[str] = None
    status: Optional[str] = None
    paid_until: Optional[str] = None
    subscription_status: Optional[str] = None
    message: Optional[str] = None


class SetPasswordResponse(BaseModel):
    """设置密码响应"""
    success: bool
    message: Optional[str] = None
