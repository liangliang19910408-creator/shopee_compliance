"""
费率引擎 - Shopee/Lazada 平台费率查询
- 模块导入时一次性加载 JSON 到内存（FEE_LOOKUP）
- 支持平台 × 类目 × 卖家类型 × 返现 四维查询
- 毫秒级响应，零文件 I/O

⚠️ SST 模式说明：
  EMBEDDED   - SST已内嵌在费率中（如3.78% = 3.5% + 8%SST），直接使用
  ADDITIONAL - SST附加计算（如佣金先算再×8%），需额外乘以 (1 + sst_rate/100)
  NONE       - 不含SST，也不需要附加计算
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Tuple, List


class SstMode(str, Enum):
    """SST 计算模式"""
    EMBEDDED = "EMBEDDED"
    ADDITIONAL = "ADDITIONAL"
    NONE = "NONE"


@dataclass
class FeeRate:
    """单条费率记录"""
    platform: str
    country: str
    category: str
    seller_type: str          # "marketplace" / "mall"
    cashback_enabled: bool
    commission_rate: float    # 佣金率（百分比，如 5.5 表示 5.5%）
    commission_sst_mode: SstMode
    transaction_fee: float    # 交易手续费率（百分比，已含SST，如 3.78）
    transaction_sst_mode: SstMode
    service_fee: float        # 营销/返现服务费率（百分比，已含SST，如 2.16）
    service_sst_mode: SstMode
    platform_fee: float       # 固定平台费（RM，已含SST，如 0.54）
    platform_fee_sst_mode: SstMode
    sst_rate: float           # SST税率（百分比，如 8.0 表示 8%）
    effective_date: str

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "platform": self.platform,
            "country": self.country,
            "category": self.category,
            "seller_type": self.seller_type,
            "cashback_enabled": self.cashback_enabled,
            "commission_rate": self.commission_rate,
            "commission_sst_mode": self.commission_sst_mode.value,
            "transaction_fee": self.transaction_fee,
            "transaction_sst_mode": self.transaction_sst_mode.value,
            "service_fee": self.service_fee,
            "service_sst_mode": self.service_sst_mode.value,
            "platform_fee": self.platform_fee,
            "platform_fee_sst_mode": self.platform_fee_sst_mode.value,
            "sst_rate": self.sst_rate,
            "effective_date": self.effective_date,
        }


# ============ 类目别名映射 ============
# 项目中使用的类目名 → 费率表中的类目名
CATEGORY_ALIASES: Dict[str, str] = {
    "general": "general",
    "electronics": "electronics",
    "beauty": "beauty",
    "fashion": "fashion",
    "home": "home",
    "health": "health",
    "baby": "baby",
    "toys": "baby",          # 玩具归入 baby 类目费率
    "sports": "sports",
    "food": "food",
    "groceries": "food",
    "pet": "general",         # 宠物用品暂归 general
    "automotif": "general",   # 汽配暂归 general
    "muslim": "fashion",      # 穆斯林服饰归 fashion
    "mobile": "electronics",  # 手机归 electronics
    "toy": "baby",
    "sport": "sports",
    "automotive": "general",
}


# ============ 内存加载 ============

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_FEE_DATA_PATHS = [
    _DATA_DIR / "fee_rates_shopee.json",
    _DATA_DIR / "fee_rates_lazada.json",
]

# 全局查找表：(platform, category, seller_type, cashback_enabled) → FeeRate
FEE_LOOKUP: Dict[Tuple[str, str, str, bool], FeeRate] = {}

# 原始数据列表（供调试/API返回）
FEE_RATES_RAW: List[dict] = []


def _load_fee_rates():
    """加载费率 JSON 到内存（模块导入时调用一次）"""
    global FEE_LOOKUP, FEE_RATES_RAW

    if FEE_LOOKUP:
        return  # 已加载，跳过

    for path in _FEE_DATA_PATHS:
        with open(path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)

        for item in raw_list:
            # 跳过纯注释条目
            if "_note" in item and "platform" not in item:
                continue

            # 合并不含 _note 的条目
            clean = {k: v for k, v in item.items() if not k.startswith("_")}
            FEE_RATES_RAW.append(clean)

            rate = FeeRate(
                platform=clean["platform"],
                country=clean["country"],
                category=clean["category"],
                seller_type=clean["seller_type"],
                cashback_enabled=clean["cashback_enabled"],
                commission_rate=clean["commission_rate"],
                commission_sst_mode=SstMode(clean["commission_sst_mode"]),
                transaction_fee=clean["transaction_fee"],
                transaction_sst_mode=SstMode(clean["transaction_sst_mode"]),
                service_fee=clean["service_fee"],
                service_sst_mode=SstMode(clean["service_sst_mode"]),
                platform_fee=clean["platform_fee"],
                platform_fee_sst_mode=SstMode(clean["platform_fee_sst_mode"]),
                sst_rate=clean["sst_rate"],
                effective_date=clean["effective_date"],
            )

            key = (rate.platform, rate.category, rate.seller_type, rate.cashback_enabled)
            FEE_LOOKUP[key] = rate


def get_fee_rate(
    category: str,
    seller_type: str = "marketplace",
    cashback_enabled: bool = True,
    platform: str = "shopee",
) -> Optional[FeeRate]:
    """
    查询费率

    Args:
        category: 商品类目（支持别名，如 "mobile" → "electronics"）
        seller_type: 卖家类型（"marketplace" / "mall"）
        cashback_enabled: 是否参与返现计划
        platform: 平台（"shopee" / "lazada"）

    Returns:
        FeeRate 对象，或 None（未找到）
    """
    _load_fee_rates()

    # 类目别名转换
    normalized_category = CATEGORY_ALIASES.get(category.lower(), "general")

    # 精确匹配
    key = (platform, normalized_category, seller_type, cashback_enabled)
    if key in FEE_LOOKUP:
        return FEE_LOOKUP[key]

    # 回退：同平台 + general + 同卖家类型 + 同返现
    fallback_key = (platform, "general", seller_type, cashback_enabled)
    if fallback_key in FEE_LOOKUP:
        return FEE_LOOKUP[fallback_key]

    # 再回退：同平台 + general + marketplace + 同返现
    fallback_key2 = (platform, "general", "marketplace", cashback_enabled)
    if fallback_key2 in FEE_LOOKUP:
        return FEE_LOOKUP[fallback_key2]

    # 最后回退：同平台 + general + marketplace + True
    fallback_key3 = (platform, "general", "marketplace", True)
    return FEE_LOOKUP.get(fallback_key3)


def get_all_categories() -> List[str]:
    """获取所有已配置费率的类目列表"""
    _load_fee_rates()
    return sorted({rate.category for rate in FEE_LOOKUP.values()})


def apply_sst(base_amount: float, sst_mode: SstMode, sst_rate: float) -> float:
    """
    根据 SST 模式计算含税金额

    Args:
        base_amount: 未税基数
        sst_mode: SST 模式
        sst_rate: SST 税率（百分比，如 8.0）

    Returns:
        含税金额
    """
    if sst_mode == SstMode.ADDITIONAL:
        return base_amount * (1 + sst_rate / 100)
    # EMBEDDED 或 NONE：基数不变
    return base_amount


def reload():
    """清除缓存并重新加载（管理员更新费率后调用）"""
    global FEE_LOOKUP, FEE_RATES_RAW
    FEE_LOOKUP = {}
    FEE_RATES_RAW = []
    _load_fee_rates()


# 模块导入时自动加载
_load_fee_rates()
