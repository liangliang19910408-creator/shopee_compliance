"""
利润计算器 - 基于 Shopee/Lazada 费率引擎计算商品利润

⚠️ Excel 先行原则：
    在编写任何 Python 代码之前，必须先在 Excel 中拆解真实订单的费用。
    本模块的输出应与 Excel 校验表逐项对比，误差必须为 0。

计算公式：
    1. 佣金 = 售价 × 佣金率
       - 若 commission_sst_mode == ADDITIONAL: 佣金 × (1 + SST%)
       - 若 EMBEDDED: 佣金率已含SST，直接使用
    2. 交易手续费 = (售价 + 买家运费) × 交易费率（已含SST）
    3. 服务费 = 售价 × 服务费率（已含SST，仅参与返现时收取）
    4. 平台费 = 固定金额（已含SST）
    5. 总费用 = 佣金 + 交易手续费 + 服务费 + 平台费
    6. 净利润 = 售价 - 总费用 - 成本价 - 卖家运费
    7. 利润率 = (净利润 / 售价) × 100
    8. 盈亏平衡价 = (买家运费 × 交易费率 + 平台费 + 成本价 + 卖家运费) / (1 - 佣金率×SST系数 - 交易费率 - 服务费率)
    9. ROI = (净利润 / 成本价) × 100
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from services.fee_engine import (
    FeeRate, SstMode, get_fee_rate, apply_sst
)


# ============ 类目健康度阈值 ============
# 不同类目的利润率健康度标准（百分比）
CATEGORY_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "electronics": {"healthy": 25, "warning": 10, "danger": 0},
    "fashion":     {"healthy": 35, "warning": 15, "danger": 0},
    "beauty":      {"healthy": 35, "warning": 15, "danger": 0},
    "home":        {"healthy": 30, "warning": 12, "danger": 0},
    "health":      {"healthy": 30, "warning": 12, "danger": 0},
    "baby":        {"healthy": 30, "warning": 12, "danger": 0},
    "sports":      {"healthy": 30, "warning": 12, "danger": 0},
    "food":        {"healthy": 20, "warning": 8,  "danger": 0},
    "general":     {"healthy": 30, "warning": 12, "danger": 0},
}

DEFAULT_THRESHOLD = {"healthy": 30, "warning": 12, "danger": 0}


@dataclass
class ProfitResult:
    """利润计算结果"""
    # 输入参数
    selling_price: float
    cost_price: float
    shipping_fee: float          # 买家支付的运费
    shipping_cost: float         # 卖家的发货成本
    category: str
    seller_type: str
    cashback_enabled: bool

    # 费率信息
    fee_rate: Optional[Dict[str, Any]] = None

    # 费用拆解（每项已含SST）
    commission: float = 0.0          # 佣金（含SST）
    commission_base: float = 0.0     # 佣金基数（不含SST）
    commission_sst: float = 0.0      # 佣金SST部分
    transaction_fee: float = 0.0     # 交易手续费
    service_fee: float = 0.0         # 服务费
    platform_fee: float = 0.0        # 固定平台费
    total_fees: float = 0.0          # 总平台费用

    # 利润结果
    gross_profit: float = 0.0        # 毛利 = 售价 - 成本
    net_profit: float = 0.0          # 净利润 = 售价 - 总费用 - 成本 - 运费成本
    profit_margin: float = 0.0       # 利润率（百分比）
    break_even_price: float = 0.0    # 盈亏平衡售价
    roi: float = 0.0                 # 投资回报率（百分比）

    # 健康度评估
    margin_level: str = "danger"     # "healthy" / "warning" / "danger"
    category_threshold: Dict[str, float] = field(default_factory=dict)

    # 计算状态
    calculated: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典（用于 API 响应）"""
        return {
            "selling_price": round(self.selling_price, 2),
            "cost_price": round(self.cost_price, 2),
            "shipping_fee": round(self.shipping_fee, 2),
            "shipping_cost": round(self.shipping_cost, 2),
            "category": self.category,
            "seller_type": self.seller_type,
            "cashback_enabled": self.cashback_enabled,
            "fee_rate": self.fee_rate,
            "fee_breakdown": {
                "commission": round(self.commission, 2),
                "commission_base": round(self.commission_base, 2),
                "commission_sst": round(self.commission_sst, 2),
                "transaction_fee": round(self.transaction_fee, 2),
                "service_fee": round(self.service_fee, 2),
                "platform_fee": round(self.platform_fee, 2),
                "total_fees": round(self.total_fees, 2),
            },
            "profit": {
                "gross_profit": round(self.gross_profit, 2),
                "net_profit": round(self.net_profit, 2),
                "profit_margin": round(self.profit_margin, 2),
                "break_even_price": round(self.break_even_price, 2),
                "roi": round(self.roi, 2),
            },
            "health": {
                "margin_level": self.margin_level,
                "category_threshold": self.category_threshold,
            },
            "calculated": self.calculated,
            "error": self.error,
        }


def calculate_profit(
    selling_price: float,
    cost_price: float,
    shipping_fee: float = 0.0,
    shipping_cost: float = 0.0,
    category: str = "general",
    seller_type: str = "marketplace",
    cashback_enabled: bool = True,
    platform: str = "shopee",
) -> ProfitResult:
    """
    计算商品利润

    Args:
        selling_price: 售价（RM）
        cost_price: 成本价（RM）
        shipping_fee: 买家支付的运费（RM）
        shipping_cost: 卖家发货成本（RM）
        category: 商品类目
        seller_type: "marketplace" / "mall"
        cashback_enabled: 是否参与返现计划
        platform: "shopee" / "lazada"

    Returns:
        ProfitResult 对象
    """
    result = ProfitResult(
        selling_price=selling_price,
        cost_price=cost_price,
        shipping_fee=shipping_fee,
        shipping_cost=shipping_cost,
        category=category,
        seller_type=seller_type,
        cashback_enabled=cashback_enabled,
    )

    # 基本验证
    if selling_price <= 0:
        result.error = "Selling price must be greater than 0"
        return result

    if cost_price < 0:
        result.error = "Cost price cannot be negative"
        return result

    # 查询费率
    rate = get_fee_rate(category, seller_type, cashback_enabled, platform)
    if not rate:
        result.error = f"No fee rate found for category={category}, seller_type={seller_type}, cashback={cashback_enabled}"
        return result

    result.fee_rate = rate.to_dict()

    # ============ 1. 佣金计算 ============
    # 佣金基数 = 售价（假设无卖家折扣）
    commission_base = selling_price * (rate.commission_rate / 100)
    result.commission_base = commission_base

    # 根据 SST 模式计算含税佣金
    commission_with_sst = apply_sst(commission_base, rate.commission_sst_mode, rate.sst_rate)
    result.commission = commission_with_sst
    result.commission_sst = commission_with_sst - commission_base

    # ============ 2. 交易手续费 ============
    # 基数 = 售价 + 买家运费（买家实付总额）
    buyer_paid = selling_price + shipping_fee
    # 交易费率已含SST（EMBEDDED模式），直接使用
    result.transaction_fee = buyer_paid * (rate.transaction_fee / 100)

    # ============ 3. 服务费（返现计划参与时收取） ============
    if cashback_enabled:
        result.service_fee = selling_price * (rate.service_fee / 100)

    # ============ 4. 平台费（固定金额，已含SST） ============
    result.platform_fee = rate.platform_fee

    # ============ 5. 总费用 ============
    result.total_fees = (
        result.commission
        + result.transaction_fee
        + result.service_fee
        + result.platform_fee
    )

    # ============ 6. 净利润 ============
    result.gross_profit = selling_price - cost_price
    result.net_profit = selling_price - result.total_fees - cost_price - shipping_cost

    # ============ 7. 利润率 ============
    result.profit_margin = (result.net_profit / selling_price) * 100

    # ============ 8. 盈亏平衡售价（二分法求解 net_profit = 0）============
    # 使用二分法直接复用与 calculate_profit 完全一致的净利公式，
    # 消除解析公式在高运费/非线性场景下的失真风险。
    result.break_even_price = _binary_search_break_even(
        cost_price, shipping_fee, shipping_cost, rate, cashback_enabled
    )

    # ============ 9. ROI ============
    if cost_price > 0:
        result.roi = (result.net_profit / cost_price) * 100

    # ============ 健康度评估 ============
    threshold = CATEGORY_THRESHOLDS.get(category, DEFAULT_THRESHOLD)
    result.category_threshold = threshold

    if result.profit_margin >= threshold["healthy"]:
        result.margin_level = "healthy"
    elif result.profit_margin >= threshold["warning"]:
        result.margin_level = "warning"
    else:
        result.margin_level = "danger"

    result.calculated = True
    return result


def calculate_target_price(
    cost_price: float,
    shipping_fee: float = 0.0,
    shipping_cost: float = 0.0,
    category: str = "general",
    seller_type: str = "marketplace",
    cashback_enabled: bool = True,
    platform: str = "shopee",
    target_margin: float = 20.0,
) -> Dict[str, Any]:
    """
    IntelliAudit 2.0 Pro: 反推达到目标利润率所需的建议售价。

    公式（复用 break_even 分母，额外减去 target_margin）：
        net_profit = S - S×CR×SST - (S+BS)×TF - S×SF - PF - C - SC
        要求 net_profit / S = target_margin%（即 net_profit = S × target_margin_pct）
        => S × (1 - CR×SST - TF - SF - target_margin_pct) = BS×TF + PF + C + SC
        => S = (BS×TF + PF + C + SC) / (1 - CR×SST - TF - SF - target_margin_pct)

    Args:
        target_margin: 目标利润率（百分比，例如 20 表示 20%）

    Returns:
        dict: {
            "target_price": float,        # 建议售价
            "target_margin": float,       # 目标利润率（百分比）
            "current_price": None,        # 由调用方填入
            "delta": None,                # 由调用方填入（建议售价 - 当前售价）
            "feasible": bool,             # 分母 > 0 时为 True
            "denominator": float,         # 实际分母（调试用）
        }
    """
    rate = get_fee_rate(category, seller_type, cashback_enabled, platform)
    if not rate:
        return {
            "target_price": None,
            "target_margin": target_margin,
            "current_price": None,
            "delta": None,
            "feasible": False,
            "denominator": 0.0,
            "error": "No fee rate found",
        }

    cr_sst = (rate.commission_rate / 100) * (
        (1 + rate.sst_rate / 100) if rate.commission_sst_mode == SstMode.ADDITIONAL else 1.0
    )
    tf = rate.transaction_fee / 100
    sf = (rate.service_fee / 100) if cashback_enabled else 0.0
    target_margin_pct = target_margin / 100.0

    denominator = 1.0 - cr_sst - tf - sf - target_margin_pct

    if denominator <= 0:
        # 费率 + 目标利润率过高，无法实现
        return {
            "target_price": None,
            "target_margin": target_margin,
            "current_price": None,
            "delta": None,
            "feasible": False,
            "denominator": round(denominator, 4),
            "reason": "Target margin exceeds fee ceiling (denominator <= 0)",
        }

    target_price = (
        shipping_fee * tf
        + rate.platform_fee
        + cost_price
        + shipping_cost
    ) / denominator

    return {
        "target_price": round(target_price, 2),
        "target_margin": target_margin,
        "current_price": None,  # 由 api_scan 填入
        "delta": None,          # 由 api_scan 填入
        "feasible": True,
        "denominator": round(denominator, 4),
    }


def _net_profit_at_price(
    selling_price: float,
    cost_price: float,
    shipping_fee: float,
    shipping_cost: float,
    rate: FeeRate,
    cashback_enabled: bool,
) -> float:
    """
    在给定售价下计算净利润，逻辑与 calculate_profit 完全一致。
    供二分法复用，保证 break-even / target-price 与主计算结果零偏差。
    """
    # 佣金（含SST）
    commission_base = selling_price * (rate.commission_rate / 100)
    commission = apply_sst(commission_base, rate.commission_sst_mode, rate.sst_rate)
    # 交易手续费（基数 = 售价 + 买家运费）
    transaction_fee = (selling_price + shipping_fee) * (rate.transaction_fee / 100)
    # 服务费
    service_fee = selling_price * (rate.service_fee / 100) if cashback_enabled else 0.0
    # 平台费
    platform_fee = rate.platform_fee
    # 净利润
    total_fees = commission + transaction_fee + service_fee + platform_fee
    return selling_price - total_fees - cost_price - shipping_cost


def _binary_search_break_even(
    cost_price: float,
    shipping_fee: float,
    shipping_cost: float,
    rate: FeeRate,
    cashback_enabled: bool,
) -> float:
    """
    二分法求解 net_profit = 0 的盈亏平衡售价。
    保证与 calculate_profit 的净利润公式完全一致。
    """
    lo, hi = 0.01, 100000.0
    # 先检查上界是否仍亏损（费率过高无法回本）
    net_hi = _net_profit_at_price(hi, cost_price, shipping_fee, shipping_cost, rate, cashback_enabled)
    if net_hi < 0:
        return float('inf')
    # 检查下界是否已经盈利（几乎不可能，但防御性处理）
    net_lo = _net_profit_at_price(lo, cost_price, shipping_fee, shipping_cost, rate, cashback_enabled)
    if net_lo >= 0:
        return lo
    # 二分搜索：50 次迭代精度可达 lo/hi 差 < 1e-10
    for _ in range(50):
        mid = (lo + hi) / 2
        net_mid = _net_profit_at_price(mid, cost_price, shipping_fee, shipping_cost, rate, cashback_enabled)
        if net_mid < 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)
