/**
 * Compliance MY Landing Page - 交互逻辑
 * 支持中英双语切换、FAQ 折叠、登录状态检测
 */

// ============ Translations ============
const translations = {
    en: {
        "nav.login": "Login",
        "nav.dashboard": "Pro Dashboard",
        "guide": "Guide",

        "hero.badge": "Smart Pre-Check Tool for Shopee MY",
        "hero.title1": "Stop Getting Banned.",
        "hero.title2": "Start Selling Safely.",
        "hero.subtitle": "Dedicated tool for Shopee & Lazada MY sellers. Check titles & links before you list.",
        "hero.preview.high_risk": "HIGH RISK",
        "hero.preview.score": "Compliance Score: 40/100",
        "hero.preview.example": '⚠️ "vape" detected in title - Shopee MY prohibits vape products',

        "cta.start_free": "Start Free Scan",
        "cta.see_features": "See Features",
        "cta.upgrade": "Upgrade to Pro – RM29/mo",
        "cta.try_now": "Try It Now",
        "cta.section_title": "Ready to sell without worries?",
        "cta.section_subtitle": "Join 2,000+ Malaysian sellers who protect their shops with Compliance MY.",

        "problem.title": "Running a shop shouldn't be stressful.",
        "problem.subtitle": "We've all been there.",
        "problem.item1_title": "Sudden Bans",
        "problem.item1_desc": "Your listing disappears overnight.",
        "problem.item2_title": "Confusing Rules",
        "problem.item2_desc": "Which words are sensitive?",
        "problem.item3_title": "Wrong Links",
        "problem.item3_desc": "Pasted the wrong link for ads.",

        "features.tag": "FEATURES",
        "features.title": "Everything you need to stay compliant",
        "features.subtitle": "Built specifically for Malaysian e-commerce sellers.",
        "features.pro_badge": "PRO",
        "features.item1_title": "Title Shield",
        "features.item1_desc": "Scan titles for sensitive words & emojis.",
        "features.item2_title": "Safe Title",
        "features.item2_desc": "One-click Safe Title, copy-paste ready.",
        "features.item3_title": "Link Inspector",
        "features.item3_desc": "Paste product link, check if valid & not mis-redirected.",
        "features.item4_title": "Batch Scan",
        "features.item4_desc": "Upload CSV with up to 200 titles. Batch report in seconds.",
        "landing.feature.link_detect_desc": "Paste a Shopee link to auto-fill the title and price. Scan for risks and calculate gross profit in one click.",

        "pricing.tag": "PRICING",
        "pricing.title": "Simple Pricing. No Hidden Fees.",
        "pricing.popular_badge": "MOST POPULAR",
        "pricing.pro.badge": "MOST POPULAR",
        "pricing.free_title": "Free",
        "pricing.free.subtitle": "Try before you sell.",
        "pricing.free_feature1": "10 Title Scans/day",
        "pricing.free_feature2": "Safe Title Gen (single)",
        "pricing.free_feature3": "5 Link Checks/day",
        "pricing.free_feature4": "Batch CSV Scan",
        "pricing.free_feature5": "Report Export",
        "pricing.free.hint": "*Enough to test. Not enough to scale.",
        "pricing.free_cta": "Start Free",
        "pricing.pro_title": "Pro",
        "pricing.pro.subtitle": "Your pocket P&L + compliance assistant.",
        "pricing.pro_feature1": "Unlimited Title Scans",
        "pricing.pro_feature2": "Safe Title Gen (single)",
        "pricing.pro_feature3": "50 Link Checks/day (manual)",
        "pricing.pro_feature4": "Batch CSV Scan (200/file)",
        "pricing.pro_feature5": "CSV Report Export",
        "landing.pricing.free.margin": "Single gross profit calculator",
        "landing.pricing.pro.margin": "Unlimited single scans & gross profit calculator",
        "landing.pricing.pro.batch_with_margin": "Batch scan (CSV) up to 200 items (with margin analysis)",
        "landing.pricing.pro.export": "CSV report export (with profit data)",
        "pricing.pro.batch_with_margin": "Batch CSV up to 200 items (with margin report)",
        "pricing.pro.export_with_profit": "CSV report export (with profit data)",
        "pricing.pro.false_positive_reward": "False positive reward: +7 days Pro when confirmed",
        "pricing.pro.item1": "Unlimited single scans & margin calc",
        "pricing.pro.compare_hint": "*Free users limited to 3 scans/day",
        "pricing.pro.item4": "Batch CSV up to 200 items (with margin report)",
        "pricing.pro.item5": "CSV report export (with profit data)",
        "pricing.pro.item6": "False positive reward: +7 days Pro",
        "pricing.pro.trial_hint": "🎁 7-day Pro trial on signup — no credit card needed.",
        "landing.margin.section_title": "More than compliance — your pocket calculator.",
        "landing.margin.section_body": "Paste your product link, enter your cost, and instantly see if a product is worth selling. No Excel, no guesswork.",
        "landing.margin.point1": "Auto-fills price from Shopee/Lazada links via secure OG tags.",
        "landing.margin.point2": "Your cost stays private — only used in your current session.",
        "landing.margin.point3": "Instant margin labels: 🟢 High / 🟡 Medium / 🔴 Low.",
        "landing.margin.demo_note": "*Demo only",
        "landing.margin.demo_profit": "Est. Gross Profit: RM15",
        "landing.margin.demo_margin": "Margin: 60%",
        "landing.margin.demo_label": "🟢 High Margin",
        "landing.margin.demo_hint": "💡 Price shown is Shopee display price, actual may vary.",
        "faq.tag": "FAQ",

        "howitworks.tag": "HOW IT WORKS",
        "howitworks.title": "3 Steps to Safer Listings",
        "howitworks.step1_title": "Paste Link",
        "howitworks.step1_desc": "Drop your Shopee/Lazada URL.",
        "howitworks.step2_title": "Scan",
        "howitworks.step2_desc": "We find risks instantly.",
        "howitworks.step3_title": "Fix",
        "howitworks.step3_desc": "Copy Safe Title & Update.",

        "faq.title": "Frequently Asked Questions",
        "faq.q1": "Is it safe?",
        "faq.a1": "Yes, we only read public info. No password needed.",
        "faq.q2": "Can I cancel?",
        "faq.a2": "Yes, anytime. No lock-in.",
        "faq.q3": "Which platforms supported?",
        "faq.a3": "Shopee MY primary, Lazada MY additional rules.",

        "footer.disclaimer": "Advisory only. Based on publicly available Shopee MY resources. Not affiliated with Shopee/Lazada.",
        "footer.privacy": "Privacy Policy",
        "footer.terms": "Terms of Service",

        "nav.dashboard": "Pro Dashboard"
    },
    zh: {
        "nav.login": "登录",
        "nav.dashboard": "Pro后台",
        "guide": "指南",

        "hero.badge": "专为 Shopee 马来站打造的智能预审工具",
        "hero.title1": "停止下架，安心卖货。",
        "hero.title2": "合规卖货，赚更多。",
        "hero.subtitle": "专为马来西亚 Shopee & Lazada 卖家打造，上架前先检测标题和链接。",
        "hero.preview.high_risk": "高风险",
        "hero.preview.score": "合规评分：40/100",
        "hero.preview.example": '⚠️ 标题检测到 "vape" - Shopee MY 禁止电子烟产品',

        "cta.start_free": "开始免费检测",
        "cta.see_features": "查看功能",
        "cta.upgrade": "升级专业版 – RM29/月",
        "cta.try_now": "立即试试",
        "cta.section_title": "准备好安心卖货了吗？",
        "cta.section_subtitle": "专为 Shopee 马来站卖家打造，用 Compliance MY 保护你的店铺。",

        "problem.title": "开店不应该这么累。",
        "problem.subtitle": "我们都经历过。",
        "problem.item1_title": "突然下架",
        "problem.item1_desc": "商品一夜之间不见了。",
        "problem.item2_title": "规则混乱",
        "problem.item2_desc": "到底哪些词违规？",
        "problem.item3_title": "链接错了",
        "problem.item3_desc": "广告放了错误的链接。",

        "features.tag": "核心功能",
        "features.title": "一站式合规解决方案",
        "features.subtitle": "专为马来西亚电商卖家打造。",
        "features.pro_badge": "Pro",
        "features.item1_title": "标题防护",
        "features.item1_desc": "扫描标题敏感词/Emoji，上架前先扫，避免 Kena Ban。",
        "features.item2_title": "安全标题",
        "features.item2_desc": "一键生成合规标题，复制即上架。",
        "features.item3_title": "链接检测",
        "features.item3_desc": "贴商品链接，检查是否有效、是否跳错页。别浪费广告费。",
        "features.item4_title": "批量扫",
        "features.item4_desc": "CSV 上传，一次 200 条标题，批量出报告。多 SKU 卖家神器。",
        "landing.feature.link_detect_desc": "贴上 Shopee 链接，自动填入标题和售价。一键检测风险并计算毛利。",

        "pricing.tag": "价格方案",
        "pricing.title": "简单定价，无隐藏费用。",
        "pricing.popular_badge": "最受欢迎",
        "pricing.pro.badge": "最受欢迎",
        "pricing.free_title": "免费版",
        "pricing.free.subtitle": "上架前先试试。",
        "pricing.free_feature1": "单条标题扫描 3 次/天",
        "pricing.free_feature2": "安全标题生成（单条）",
        "pricing.free_feature3": "链接检测 3 次/天",
        "pricing.free_feature4": "批量标题 (CSV)",
        "pricing.free_feature5": "报告导出",
        "pricing.free.hint": "*够试用，不够铺货。",
        "pricing.free_cta": "免费开始",
        "pricing.pro_title": "专业版",
        "pricing.pro.subtitle": "你的随身算盘 + 防封助手。",
        "pricing.pro_feature1": "无限单条标题扫描",
        "pricing.pro_feature2": "安全标题生成（单条）",
        "pricing.pro_feature3": "链接检测 50 次/天（单条）",
        "pricing.pro_feature4": "批量标题 (CSV) 200 条/次",
        "pricing.pro_feature5": "CSV 报告导出",
        "landing.pricing.free.margin": "单条毛利速算",
        "landing.pricing.pro.margin": "无限单条扫描 & 毛利速算",
        "landing.pricing.pro.batch_with_margin": "批量标题 (CSV) 200 条/次 (含毛利分析)",
        "landing.pricing.pro.export": "CSV 报告导出 (含利润数据)",
        "pricing.pro.batch_with_margin": "批量标题 (CSV) 200 条/次（含毛利报告）",
        "pricing.pro.export_with_profit": "CSV 报告导出（含利润数据）",
        "pricing.pro.false_positive_reward": "误报反馈奖励：确认后 +7 天 Pro",
        "pricing.pro.item1": "无限单条扫描 & 毛利速算",
        "pricing.pro.compare_hint": "*免费用户每天仅限3次",
        "pricing.pro.item4": "批量标题 (CSV) 200条/次（含毛利报告）",
        "pricing.pro.item5": "CSV 报告导出（含利润数据）",
        "pricing.pro.item6": "误报反馈奖励：确认后 +7天 Pro",
        "pricing.pro.trial_hint": "🎁 注册即享 7 天 Pro 试用，无需信用卡。",
        "landing.margin.section_title": "不止防下架，更是你的随身算盘。",
        "landing.margin.section_body": "贴上商品链接，输入成本，即刻判断这个品值不值得推。告别 Excel，告别拍脑袋。",
        "landing.margin.point1": "通过安全 OG 标签自动获取 Shopee/Lazada 售价。",
        "landing.margin.point2": "成本数据完全私密 — 仅在当前会话中使用。",
        "landing.margin.point3": "即时利润率标签：🟢高毛利 / 🟡中毛利 / 🔴低毛利。",
        "landing.margin.demo_note": "*仅为演示",
        "landing.margin.demo_profit": "预估毛利：RM15",
        "landing.margin.demo_margin": "利润率：60%",
        "landing.margin.demo_label": "🟢 高毛利",
        "landing.margin.demo_hint": "💡 售价为 Shopee 展示价，实际以订单为准。",
        "faq.tag": "常见问题",

        "howitworks.tag": "使用方法",
        "howitworks.title": "3 步保护你的商品",
        "howitworks.step1_title": "粘贴链接",
        "howitworks.step1_desc": "放入你的商品链接。",
        "howitworks.step2_title": "扫描",
        "howitworks.step2_desc": "立即发现风险。",
        "howitworks.step3_title": "修复",
        "howitworks.step3_desc": "复制安全标题并更新。",

        "faq.title": "常见问题",
        "faq.q1": "安全吗？",
        "faq.a1": "安全，我们只读取公开信息，不需要密码。",
        "faq.q2": "能取消吗？",
        "faq.a2": "可以，随时取消，无捆绑。",
        "faq.q3": "支持哪些平台？",
        "faq.a3": "Shopee MY 为主，额外支持 Lazada MY 规则。",

        "footer.disclaimer": "仅供参考。基于 Shopee 马来西亚公开卖家资源。与 Shopee/Lazada 无关联。",
        "footer.privacy": "隐私政策",
        "footer.terms": "服务条款"
    }
};

// ============ Globals ============
let currentLang = localStorage.getItem('lang') || 'en';

// ============ Init ============
document.addEventListener('DOMContentLoaded', () => {
    applyLanguage(currentLang);
    checkLoginStatus();
});

// ============ Language ============
function toggleLanguage() {
    currentLang = currentLang === 'en' ? 'zh' : 'en';
    localStorage.setItem('lang', currentLang);
    applyLanguage(currentLang);
}

function applyLanguage(lang) {
    const t = translations[lang];
    const isZh = lang === 'zh';

    document.documentElement.lang = isZh ? 'zh-CN' : 'en';
    document.title = isZh
        ? 'Compliance MY - 停止下架，安心卖货。'
        : 'Compliance MY - Stop Getting Banned. Start Selling Safely.';

    const langLabel = document.getElementById('langLabel');
    if (langLabel) {
        langLabel.textContent = isZh ? '中' : 'EN';
    }

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) {
            el.textContent = t[key];
        }
    });

    const authNav = document.getElementById('authNav');
    if (authNav) {
        const link = authNav.querySelector('a');
        if (link && link.getAttribute('href') === '/login') {
            link.textContent = t['nav.login'];
        }
    }
}

// ============ FAQ Toggle ============
function toggleFaq(element) {
    const wasActive = element.classList.contains('active');
    document.querySelectorAll('.faq-item').forEach(item => {
        item.classList.remove('active');
    });
    if (!wasActive) {
        element.classList.add('active');
    }
}

// ============ Check Login Status ============
async function checkLoginStatus() {
    try {
        const res = await fetch('/api/user/info');
        const data = await res.json();

        const authNav = document.getElementById('authNav');
        if (!authNav) return;

        const t = translations[currentLang];

        if (data.logged_in) {
            authNav.innerHTML = `
                <a href="/dashboard" class="text-sm text-slate-300 hover:text-white transition">
                    ${t['nav.dashboard']}
                </a>
            `;
        } else {
            authNav.innerHTML = `
                <a href="/login" class="text-sm text-slate-300 hover:text-white transition">
                    ${t['nav.login']}
                </a>
            `;
        }
    } catch (err) {
        console.error('Failed to check login status:', err);
    }
}
