"""
全局配置常量
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "shopee.db"
BANNED_WORDS_PATH = BASE_DIR / "data" / "msia_banned_words.json"
CATEGORY_RULES_PATH = BASE_DIR / "data" / "category_rules.json"
WHITELIST_PATH = BASE_DIR / "data" / "whitelist.json"

TRIAL_DAYS = 7
CORS_ORIGINS = ["http://localhost:8000", "http://www.compliancemy.com", "http://47.238.151.196"]
HOST = "0.0.0.0"
PORT = 8000
WA_LINK = os.getenv("NEXT_PUBLIC_WA_LINK", "https://wa.me/60123456789")

# ============ Creem 支付配置 ============
CREEM_API_KEY = os.getenv("CREEM_API_KEY", "creem_test_7APlh8jBp38rrCWhFFovwH")
CREEM_WEBHOOK_SECRET = os.getenv("CREEM_WEBHOOK_SECRET", "whsec_71yUjEbb7lepCsDRVrFS8F")
CREEM_PRODUCT_MONTHLY = os.getenv("CREEM_PRODUCT_MONTHLY", "prod_2gQEav4HeQ159IqeeK8X1N")
CREEM_API_BASE = os.getenv("CREEM_API_BASE", "https://test-api.creem.io")
# 支付成功/取消跳转地址（开发环境用 localhost，生产环境通过环境变量覆盖）
CREEM_SUCCESS_URL = os.getenv("CREEM_SUCCESS_URL", "https://www.compliancemy.com//success")
CREEM_CANCEL_URL = os.getenv("CREEM_CANCEL_URL", "https://www.compliancemy.com//pricing/pay")
