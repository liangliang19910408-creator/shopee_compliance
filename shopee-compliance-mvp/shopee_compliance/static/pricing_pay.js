/**
 * Compliance MY - Pricing/Pay Page
 * 支持中英双语切换、支付方式选择、账号复制、WhatsApp 跳转
 */

// ============ Translations ============
const translations = {
    en: {
        // Page
        "payTitle": "Complete Your Purchase",
        "paySubtitle": "Secure checkout. Instant access. No hidden fees.",

        // Plan
        "planLabel": "Pro Plan",
        "planName": "Pro Plan (Monthly)",
        "perMonth": "/ month",
        "feature1": "Unlimited single scans & margin calculator",
        "feature2": "Safe title generator",
        "feature3": "Link detection 50/day",
        "feature4": "Batch CSV up to 200 items (with margin report)",
        "feature5": "CSV report export (with profit data)",
        "feature6": "False positive reward: +7 days Pro",

        // Trust Badges
        "trust1Title": "Secure Payment",
        "trust1Desc": "Powered by Creem",
        "trust2Title": "7-Day Guarantee",
        "trust2Desc": "Money back if not satisfied",
        "trust3Title": "Priority Support",
        "trust3Desc": "WhatsApp support within 12h",

        // Payment Method
        "paymentMethod": "Payment Method",
        "checkoutBtn": "Subscribe with Creem",
        "checkoutHint": "Secure checkout powered by Creem. You'll be redirected to complete payment.",

        // Footer
        "footerNote": "Prices in MYR. Auto-renewal can be cancelled anytime. By proceeding, you agree to our Terms of Service.",

        // WhatsApp FAB
        "whatsappFab": "Chat Support"
    },
    zh: {
        // Page
        "payTitle": "完成购买",
        "paySubtitle": "安全结账。立即开通。无隐藏费用。",

        // Plan
        "planLabel": "专业版",
        "planName": "专业版 (月付)",
        "perMonth": "/ 月",
        "feature1": "无限单条扫描 & 毛利速算",
        "feature2": "安全标题生成器",
        "feature3": "链接检测 50次/天",
        "feature4": "批量标题 (CSV) 200条/次（含毛利报告）",
        "feature5": "CSV 报告导出（含利润数据）",
        "feature6": "误报反馈奖励：确认后 +7天 Pro",

        // Trust Badges
        "trust1Title": "安全支付",
        "trust1Desc": "由 Creem 提供安全支付",
        "trust2Title": "7天无理由",
        "trust2Desc": "不满意全额退款",
        "trust3Title": "优先支持",
        "trust3Desc": "12小时内 WhatsApp 回复",

        // Payment Method
        "paymentMethod": "支付方式",
        "checkoutBtn": "通过 Creem 订阅",
        "checkoutHint": "由 Creem 提供安全结账。您将被跳转完成支付。",

        // Footer
        "footerNote": "价格以马币计。可随时取消自动续费。继续操作即表示您同意我们的服务条款。",

        // WhatsApp FAB
        "whatsappFab": "联系客服"
    }
};

// ============ Config ============
const WHATSAPP_NUMBER = "60123456789";

// ============ State ============
let currentLang = localStorage.getItem("lang") || "en";
let isCheckingOut = false;

// ============ Initialize ============
document.addEventListener("DOMContentLoaded", () => {
    applyLanguage();
    setupWhatsAppLinks();
});

// ============ Language ============
function applyLanguage() {
    const t = translations[currentLang];
    document.documentElement.lang = currentLang;
    document.getElementById("langLabel").textContent = currentLang.toUpperCase();

    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (t[key]) {
            el.textContent = t[key];
        }
    });
}

function toggleLanguage() {
    currentLang = currentLang === "en" ? "zh" : "en";
    localStorage.setItem("lang", currentLang);
    applyLanguage();
}

// ============ Creem Checkout ============
async function handleCheckout() {
    if (isCheckingOut) return;
    isCheckingOut = true;

    const btn = document.getElementById("checkoutBtn");
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = currentLang === "en" ? "Redirecting..." : "跳转中...";

    try {
        const res = await fetch("/api/creem/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plan: "monthly" })
        });

        if (res.status === 401) {
            alert(currentLang === "en" ? "Please login first." : "请先登录。");
            window.location.href = "/login";
            return;
        }

        const data = await res.json();
        if (data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            alert(currentLang === "en" ? "Checkout failed. Please try again." : "结账失败，请重试。");
        }
    } catch (err) {
        console.error("Checkout error:", err);
        alert(currentLang === "en" ? "Network error. Please try again." : "网络错误，请重试。");
    } finally {
        isCheckingOut = false;
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ============ WhatsApp Links ============
function setupWhatsAppLinks() {
    const fabLink = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent("Hi, I need help with my Pro plan.")}`;
    const fab = document.getElementById("whatsappFab");
    if (fab) fab.href = fabLink;
}

// ============ Expose to global scope ============
window.handleCheckout = handleCheckout;
window.toggleLanguage = toggleLanguage;
window.setupWhatsAppLinks = setupWhatsAppLinks;
