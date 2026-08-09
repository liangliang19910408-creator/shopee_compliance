/**
 * Shopee 合规检测 - 前端交互逻辑
 * 支持中英双语切换、Traffic Light System、响应式布局
 */

// ============ Constants ============
const WHATSAPP_LINK = 'https://wa.me/yournumber';

// ============ Helpers ============
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// Phase 4.3: 通用埋点上报（fire-and-forget，失败静默）
async function trackEvent(eventName, eventData = {}) {
    try {
        await fetch('/api/user/event/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event_name: eventName, event_data: eventData }),
        });
    } catch (e) {
        // 静默吞掉，不影响主流程
    }
}

function showToast(message, type = 'warning', actions = []) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    const bgColor = type === 'warning' ? 'bg-amber-900/90 border-amber-500/50' :
                    type === 'error' ? 'bg-red-900/90 border-red-500/50' :
                    type === 'success' ? 'bg-green-900/90 border-green-500/50' :
                    'bg-slate-800/90 border-slate-500/50';

    toast.className = `
        fixed top-5 right-5 z-50
        px-4 py-3 rounded-lg shadow-2xl
        text-white text-sm font-medium
        border ${bgColor}
        opacity-0 transform translate-y-2
        transition-all duration-300 ease-out
        flex items-center gap-3
        max-w-sm
    `;

    const msgSpan = document.createElement('span');
    msgSpan.className = 'flex-1';
    msgSpan.textContent = message;
    toast.appendChild(msgSpan);

    if (actions && actions.length > 0) {
        const actionContainer = document.createElement('div');
        actionContainer.className = 'flex gap-2';
        actions.forEach(action => {
            const actionLink = document.createElement('a');
            // 支持 action.url 或 action.onclick
            if (action.onclick) {
                actionLink.href = '#';
                actionLink.onclick = (e) => { e.preventDefault(); action.onclick(); };
            } else {
                actionLink.href = action.url || '#';
                actionLink.target = action.target || '_self';
            }
            actionLink.className = 'text-amber-300 hover:text-amber-200 font-semibold text-xs underline whitespace-nowrap';
            actionLink.textContent = action.text;
            actionContainer.appendChild(actionLink);
        });
        toast.appendChild(actionContainer);
    }

    const closeBtn = document.createElement('button');
    closeBtn.className = 'text-white/60 hover:text-white/80 transition ml-1';
    closeBtn.innerHTML = '✕';
    closeBtn.onclick = () => {
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    };
    toast.appendChild(closeBtn);

    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.remove('opacity-0', 'translate-y-2');
        toast.classList.add('opacity-100', 'translate-y-0');
    });

    setTimeout(() => {
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// ============ Globals ============
let trialToken = getCookie('session_token') || localStorage.getItem('trial_token') || null;
let trialEmail = localStorage.getItem('trial_email') || null;
let trialEnd = localStorage.getItem('trial_end') || null;
let currentLang = localStorage.getItem('lang') || 'en';
let selectedCsvFile = null;
let batchIsPro = false;
let userIsPro = false;  // 定价模拟器权限控制
let currentPlatform = 'shopee'; // P1-A: 当前选中的平台 (shopee/lazada)

// ============ Translations ============
const translations = {
    en: {
        pageTitle: 'Shopee & Lazada MY Pre-Audit & Profit Intelligence',
        pageSubtitle: 'Pre-audit compliance, fee breakdown & opportunity scoring. List with confidence.',
        productTitle: 'Product Title',
        productInput: 'Product Title or Link',
        titlePlaceholder: 'e.g. New Wireless Bluetooth Earphone...',
        description: 'Description',
        descPlaceholder: 'Enter detailed description...',
        productUrl: 'Product URL',
        urlPlaceholder: 'https://shopee.my/...',
        category: 'Category',
        categoryPlaceholder: 'e.g. Fashion > Men\'s Wear',
        productCategory: 'Product Category',
        catGeneral: 'General (All Products)',
        catElectronics: 'Electronics',
        catBeauty: 'Beauty & Skincare',
        catFashion: 'Fashion & Apparel',
        catHome: 'Home & Living',
        catHealth: 'Health & Supplements',
        catBaby: 'Baby & Toys',
        catSports: 'Sports & Outdoor',
        catFood: 'Food & Beverages',
        startScan: 'Start Scan',
        scanNow: 'Scan Now',
        scanning: 'Scanning...',
        tabTextInput: 'Text Input',
        tabUrlInput: 'Product Link',
        fetchMetaBtn: 'Fetch Product Info',
        batchUpload: '📥 Batch Upload CSV',
        sampleCsv: 'Sample CSV',
        export_csv: 'Export CSV',
        unlockTrial: 'Unlock 7-Day Free Trial',
        trialHint: 'Enter your email for unlimited scans, no credit card required.',
        emailPlaceholder: 'your@email.com',
        unlock: 'Unlock Trial',
        cancel: 'Cancel',
        submit: 'Submit',

        trialRemaining: 'Remaining',
        days: 'days',

        highRisk: 'High Risk',
        mediumRisk: 'Medium Risk',
        lowRisk: 'Low Risk / Pass',
        issue: 'Issue',
        detectedIn: 'detected in',
        why: 'Why',
        action: 'Action',
        title: 'Title',
        desc: 'Description',

        highRiskMsg: 'Critical violations detected. Immediate action required.',
        mediumRiskMsg: 'Moderate risk detected. Review recommended.',
        lowRiskMsg: 'Your listing appears compliant.',
        violationsFound: 'violation(s) found',

        complianceScore: 'Compliance Score',
        scoreHigh: 'High Risk',
        scoreMedium: 'Medium',
        scoreLow: 'Low Risk',

        share: 'Share',
        shareSuccess: 'Trial extended by 7 days!',
        shareFail: 'Already shared today',

        downloadCard: 'Download Card',

        footerPolicy: 'Advisory only. Based on publicly available Shopee & Lazada MY resources. Not affiliated with Shopee/Lazada.',
        footerDisclaimer: 'Results are advisory only.',
        upgradePro: 'Upgrade to Pro →',

        limitBannerText: 'You have used all 5 free scans today. Upgrade to Pro for unlimited scans.',
        limitBannerBtn: 'Upgrade to Pro – RM59/mo',
        limitTitle: 'Daily Scan Limit Reached',
        firstTimeBannerText: 'Paste your Shopee or Lazada product link below to start scanning.',

        safeTitle: 'Looking Good!',
        safeDesc: 'No sensitive words detected.',
        riskTitle: 'Risk Detected',
        riskDescEmoji: 'Emoji found in title.',
        riskDescKeyword: 'Sensitive keyword detected.',
        copySafeTitle: 'Copy Safe Title',
        copied: 'Copied!',

        close: 'Close',
        continueScan: 'Scan Again',

        backHome: '← Back to Home',
        scanReport: 'Compliance Scan Report',
        productInfo: 'Product Information',
        riskStats: 'Risk Summary',
        severe: 'Severe',
        moderate: 'Moderate',
        minor: 'Minor',
        violationDetails: 'Violation Details',
        reportTime: 'Report generated',
        noReport: 'No report data available',
        goHome: 'Go to Home',

        trialExpired: 'Your 7-day free trial has expired.',
        upgradeNow: 'Upgrade now to keep your listings safe.',
        upgradeBtn: 'Upgrade to Pro (RM59/month)',

        login: 'Login',
        logout: 'Logout',
        guide: 'Guide',
        pendingActivation: 'Pending Activation',

        safeTitleLabel: 'Recommended Safe Title',
        safeTitleCopy: 'Copy',
        safeTitleLocked: 'Upgrade to unlock full Safe Title',
        safeTitleCopied: 'Copied!',
        previewOnly: 'PREVIEW ONLY',
        referenceTitleNote: 'Reference title only. Please verify before listing.',
        reportFalsePositive: 'Report False Positive',
        falsePositiveWordPlaceholder: 'Word you believe is a false positive',
        falsePositiveReasonPlaceholder: 'Why do you believe this is a false positive?',

        ruleSetLabel: 'Platform:',
        platformShopee: 'Shopee MY',
        platformLazada: 'Lazada MY',
        platformSwitchConfirm: 'Switch Platform?',
        platformSwitchConfirmMsg: 'Switching platform will reset the title, link and category. Cost and price will be kept. Continue?',
        lazadaDetectedToast: 'Lazada link detected, switched to Lazada platform',
        lazadaShippingHint: 'Estimated value, please adjust based on actual logistics',
        hygieneTips: 'Readability Tips',
        hygieneTitleLength: 'Title exceeds 128 characters - may be truncated',
        hygieneWordRepeat: 'Repeated word detected - consider rephrasing',
        hygieneAllCaps: 'Excessive uppercase - reduce for readability',

        'scan.form.cost_label': 'Est. Cost (RM)',
        'scan.form.price_label': 'Est. Price (RM)',
        'scan.supplier.empty': 'No suppliers saved.',
        'scan.supplier.go_dashboard': 'Go to Dashboard →',
        'scan.result.gross_profit': 'Est. Gross Profit: RM{{gp}} ({{margin}}%)',
        'scan.result.margin_note': '💡 Price shown is Shopee/Lazada listing price, actual may vary.',
        'scan.result.margin_high': 'High Margin',
        'scan.result.margin_medium': 'Medium Margin',
        'scan.result.margin_low': 'Low Margin',
        'scan.placeholder.margin_empty': 'Enter your estimated cost and price above to see gross profit and margin level after scanning.',
        'scan.banner.title': '💰 Profit Intelligence: Fee Breakdown + Opportunity Score',
        'scan.banner.body': '🔗 Paste Shopee/Lazada link → title auto-filled.<br/>✏️ Enter cost, price & shipping.<br/>📊 Full fee breakdown: commission, transaction, service & platform fees.<br/>🎯 Opportunity score: content compliance + profit health + title quality + violation risk.',
        'scan.advanced.toggle': 'Advanced Profit Settings',
        'scan.advanced.lock_title': 'Pro Feature',
        'scan.advanced.lock_desc': 'Upgrade to adjust shipping, seller type & cashback',
        'scan.advanced.lock_btn': 'Upgrade to Pro',
        'scan.form.shipping_fee_label': 'Buyer Shipping Fee (RM)',
        'scan.form.shipping_cost_label': 'Seller Shipping Cost (RM)',
        'scan.form.seller_type_label': 'Seller Type',
        'scan.form.seller_marketplace': 'Marketplace Seller',
        'scan.form.seller_mall': 'Shopee Mall Seller',
        'scan.form.cashback_label': 'Participate in Cashback Program',
        'scan.result.fee_breakdown_title': 'Fee Breakdown',
        'scan.result.platform_fees_group': 'Platform Fees',
        'scan.result.commission': 'Commission (incl. SST)',
        'scan.result.transaction_fee': 'Transaction Fee',
        'scan.result.service_fee': 'Service Fee',
        'scan.result.platform_fee': 'Platform Fee',
        'scan.result.total_fees': 'Total Platform Fees',
        'scan.result.net_profit': 'Net Profit',
        'scan.result.profit_margin': 'Profit Margin',
        'scan.result.break_even': 'Break-even Price',
        'scan.result.roi': 'ROI',
        'scan.result.healthy': 'Healthy',
        'scan.result.warning': 'Warning',
        'scan.result.danger': 'Danger',
        'scan.result.opp_score_title': 'Opportunity Score',
        'scan.result.opp_premium': 'Excellent Opportunity',
        'scan.result.opp_good': 'Caution Advised',
        'scan.result.opp_risky': 'Not Recommended',
        'scan.result.opp_blocked': 'Blocked',
        'scan.result.opp_compliance': 'Content Compliance',
        'scan.result.opp_profit': 'Profit Health',
        'scan.result.opp_competition': 'Title Quality',
        'scan.result.opp_risk': 'Violation Risk',
        'scan.result.break_even_hint': 'Minimum price to cover all costs and fees',
        'scan.result.target_price_title': 'Target Price Suggestion',
        'scan.result.gate_blocked': 'Blocked',
        'scan.result.gate_passed': 'Passed',
        'scan.rule_alert.text': '⚠️ Shopee MY updated: stricter monitoring on \'vape\', \'replica\' and similar terms. Review your listings.',

        'scan.limit_banner.guest': '⚠️ Free scans: 5/5 used today. Log in to continue, or sign up for 7-day Pro trial — no credit card needed.',
        'scan.limit_banner.guest_zh': '⚠️ 免费扫描：今日 5/5 已用完。登录继续使用，或注册领 7 天 Pro 试用（无需信用卡）。',
        'scan.limit_banner.logged': '⚠️ Free scans: 5/5 used today. Upgrade to Pro for unlimited scans + batch CSV (200 items), or WhatsApp us.',
        'scan.limit_banner.logged_zh': '⚠️ 免费扫描：今日 5/5 已用完。升级 Pro 享无限扫描 + 批量 CSV（200条），或 WhatsApp 联系。',
        'scan.limit_banner.login_btn': 'Log in',
        'scan.limit_banner.login_btn_zh': '登录',
        'scan.limit_banner.signup_btn': 'Sign up',
        'scan.limit_banner.signup_btn_zh': '注册',
        'scan.limit_banner.upgrade_btn': 'Upgrade',
        'scan.limit_banner.upgrade_btn_zh': '升级',
        'floating_wa_tooltip': 'WhatsApp us',

        batchUploadTitle: 'Batch Title Scan (Pro)',
        batchTemplateHint: 'CSV format: original_title (required), cost_rm (optional), price_rm (optional). Max 200 rows. Profit & margin will be calculated automatically.',
        batchSelectFile: 'Select CSV File',
        batchStartScan: 'Start Batch Scan',
        batchProcessing: 'Processing...',
        batchCompleted: 'Batch scan completed! Report downloaded.',
        batchFailed: 'Batch scan failed. Please try again.',
        batchProOnly: 'Batch scan available for Pro users only',
        batchProLockToast: '🔒 Batch scanning is a Pro feature.',
        advancedLockToast: '🔒 Advanced profit settings (shipping, seller type, cashback) are Pro features. Upgrade to unlock precise fee simulation.',
        batchUpgradeAction: 'Upgrade to Pro',
        batchHelpAction: 'Get help',
        batchUpgradeHint: 'Upgrade to Pro for unlimited batch scans (200 items per file).',
        batch_lock_trial: 'Unlock batch scan with 7-day free trial',
        primaryLabel: 'Primary',
        proLabel: 'PRO',
        urlParseHint: 'Only reads publicly displayed page text, not platform API data.',
        trial_modal_title: 'Activate 7-Day Pro Trial',
        trial_modal_input_placeholder: '+60123456789',
        trial_modal_success: 'Trial activated! Check your WhatsApp.',
        trial_error_wa_used: 'This WA number has already been used for trial.',
        trialActivate: 'Activate',
        scanCountLabel: "Today's scans",
        scanCountTextPattern: '{used}/{limit} ({remaining} left)',
        scanCountUnlimited: 'Unlimited scans',
        scanCountUsedUp: 'All 5 scans used today'
    },
    zh: {
        pageTitle: 'Shopee & Lazada MY 预审与利润智能平台',
        pageSubtitle: '合规预审、费用拆解、机会评分，安心上架。',
        productTitle: '商品标题',
        productInput: '商品标题或链接',
        titlePlaceholder: '例如：新款无线蓝牙耳机...',
        description: '商品描述',
        descPlaceholder: '输入详细描述...',
        productUrl: '商品链接',
        urlPlaceholder: 'https://shopee.my/...',
        category: '类目',
        categoryPlaceholder: '例如：Fashion > Men\'s Wear',
        productCategory: '商品类目',
        catGeneral: '通用（所有商品）',
        catElectronics: '电子产品',
        catBeauty: '美妆护肤',
        catFashion: '时尚服饰',
        catHome: '家居生活',
        catHealth: '健康保健',
        catBaby: '母婴玩具',
        catSports: '运动户外',
        catFood: '食品饮料',
        startScan: '开始检测',
        scanNow: '立即扫描',
        scanning: '检测中...',
        tabTextInput: '文本输入',
        tabUrlInput: '商品链接',
        fetchMetaBtn: '获取商品信息',
        batchUpload: '📥 批量上传 CSV',
        sampleCsv: '示例 CSV',
        export_csv: '导出 CSV',
        unlockTrial: '解锁 7 天免费试用',
        trialHint: '输入邮箱即可获得无限制检测，无需信用卡。',
        emailPlaceholder: 'your@email.com',
        unlock: '解锁试用',
        cancel: '取消',
        submit: '提交',

        trialRemaining: '剩余',
        days: '天',

        highRisk: '高风险',
        mediumRisk: '中等风险',
        lowRisk: '低风险 / 通过',
        issue: '问题',
        detectedIn: '发现于',
        why: '原因',
        action: '建议',
        title: '标题',
        desc: '描述',

        highRiskMsg: '检测到严重违规项，请立即修改。',
        mediumRiskMsg: '检测到中等风险，建议优化商品描述。',
        lowRiskMsg: '您的商品信息符合合规要求。',
        violationsFound: '项违规',

        complianceScore: '合规评分',
        scoreHigh: '高风险',
        scoreMedium: '中等',
        scoreLow: '低风险',

        share: '分享',
        shareSuccess: '试用已延长7天！',
        shareFail: '今天已分享过',

        downloadCard: '下载报告卡',

        footerPolicy: '仅供参考。基于 Shopee & Lazada 马来西亚公开卖家资源。与 Shopee/Lazada 无关联。',
        footerDisclaimer: '检测结果仅供参考。',
        upgradePro: '升级到 Pro →',

        limitBannerText: '今日 5 次免费扫描已用完。升级 Pro 享受无限扫描。',
        limitBannerBtn: '升级 Pro – RM59/月',
        limitTitle: '每日扫描次数已用完',
        firstTimeBannerText: '将您的 Shopee 或 Lazada 商品链接粘贴到下方开始检测。',

        safeTitle: '暂无风险！',
        safeDesc: '未检测到敏感词。',
        riskTitle: '检测到风险',
        riskDescEmoji: '标题中含有 Emoji。',
        riskDescKeyword: '检测到敏感关键词。',
        copySafeTitle: '复制安全标题',
        copied: '已复制！',

        close: '关闭',
        continueScan: '继续检测',

        backHome: '← 返回首页',
        scanReport: '合规检测报告',
        productInfo: '商品信息',
        riskStats: '风险统计',
        severe: '严重',
        moderate: '中等',
        minor: '轻微',
        violationDetails: '违规详情',
        reportTime: '报告生成时间',
        noReport: '暂无报告数据',
        goHome: '返回首页',

        trialExpired: '您的7天免费试用期已到期。',
        upgradeNow: '立即升级以继续保护您的商品列表。',
        upgradeBtn: '升级到 Pro (RM59/月)',

        login: '登录',
        logout: '登出',
        guide: '指南',
        pendingActivation: '待激活',

        safeTitleLabel: '推荐安全标题',
        safeTitleCopy: '复制',
        safeTitleLocked: '升级后解锁完整安全标题',
        safeTitleCopied: '已复制！',
        previewOnly: '仅供预览',
        referenceTitleNote: '仅供参考，上架前请人工复核。',
        reportFalsePositive: '报告误报',
        falsePositiveWordPlaceholder: '您认为是误报的词语',
        falsePositiveReasonPlaceholder: '您为什么认为这是误报？',

        ruleSetLabel: '平台：',
        platformShopee: 'Shopee MY',
        platformLazada: 'Lazada MY',
        platformSwitchConfirm: '切换平台？',
        platformSwitchConfirmMsg: '切换平台将重置标题、链接和类目。成本和售价将保留。是否继续？',
        lazadaDetectedToast: '检测到 Lazada 链接，已自动切换平台',
        lazadaShippingHint: '预估值，请根据实际物流单修改',
        hygieneTips: '可读性提示',
        hygieneTitleLength: '标题超过128字符 - 可能被截断',
        hygieneWordRepeat: '检测到重复词 - 建议重新表述',
        hygieneAllCaps: '过多大写字母 - 降低以提升可读性',

        'scan.form.cost_label': '预估成本 (RM)',
        'scan.form.price_label': '预估售价 (RM)',
        'scan.supplier.empty': '暂无供应商预设。',
        'scan.supplier.go_dashboard': '前往 Dashboard →',
        'scan.result.gross_profit': '预估毛利：RM{{gp}} ({{margin}}%)',
        'scan.result.margin_note': '💡 售价为 Shopee/Lazada 展示价，实际以订单为准。',
        'scan.result.margin_high': '高毛利',
        'scan.result.margin_medium': '中毛利',
        'scan.result.margin_low': '低毛利',
        'scan.placeholder.margin_empty': '在上方填入预估成本和售价，扫描后即可查看毛利计算结果和利润率等级。',
        'scan.banner.title': '💰 利润智能：费用拆解 + 机会评分',
        'scan.banner.body': '🔗 贴 Shopee/Lazada 链接 → 标题自动填入。<br/>✏️ 输入成本、售价和运费。<br/>📊 完整费用拆解：佣金、交易费、服务费、平台费。<br/>🎯 机会评分：内容合规 + 利润健康度 + 标题质量 + 违规风险。',
        'scan.advanced.toggle': '高级利润设置',
        'scan.advanced.lock_title': 'Pro 功能',
        'scan.advanced.lock_desc': '升级可调整运费、卖家类型与返现设置',
        'scan.advanced.lock_btn': '升级 Pro',
        'scan.form.shipping_fee_label': '买家运费 (RM)',
        'scan.form.shipping_cost_label': '卖家发货成本 (RM)',
        'scan.form.seller_type_label': '卖家类型',
        'scan.form.seller_marketplace': '普通卖家 (Marketplace)',
        'scan.form.seller_mall': '商城卖家 (Shopee Mall)',
        'scan.form.cashback_label': '参与返现计划',
        'scan.result.fee_breakdown_title': '费用拆解',
        'scan.result.platform_fees_group': '平台扣费',
        'scan.result.commission': '佣金（含SST）',
        'scan.result.transaction_fee': '交易手续费',
        'scan.result.service_fee': '服务费',
        'scan.result.platform_fee': '平台费',
        'scan.result.total_fees': '平台总费用',
        'scan.result.net_profit': '净利润',
        'scan.result.profit_margin': '利润率',
        'scan.result.break_even': '盈亏平衡售价',
        'scan.result.roi': '投资回报率',
        'scan.result.healthy': '健康',
        'scan.result.warning': '警告',
        'scan.result.danger': '危险',
        'scan.result.opp_score_title': '机会评分',
        'scan.result.opp_premium': '优秀机会',
        'scan.result.opp_good': '谨慎评估',
        'scan.result.opp_risky': '不建议',
        'scan.result.opp_blocked': '已拦截',
        'scan.result.opp_compliance': '内容合规',
        'scan.result.opp_profit': '利润健康度',
        'scan.result.opp_competition': '标题质量',
        'scan.result.opp_risk': '违规风险',
        'scan.result.break_even_hint': '覆盖所有成本和费用的最低售价',
        'scan.result.target_price_title': '目标利润率反推售价',
        'scan.result.gate_blocked': '已拦截',
        'scan.result.gate_passed': '已通过',
        'scan.rule_alert.text': '⚠️ Shopee MY 规则更新：加强对 \'vape\'、\'replica\' 等词的监控，建议检查标题。',

        'scan.limit_banner.guest': '⚠️ 免费扫描：今日 5/5 已用完。登录继续使用，或注册领 7 天 Pro 试用（无需信用卡）。',
        'scan.limit_banner.guest_zh': '⚠️ 免费扫描：今日 5/5 已用完。登录继续使用，或注册领 7 天 Pro 试用（无需信用卡）。',
        'scan.limit_banner.logged': '⚠️ 免费扫描：今日 5/5 已用完。升级 Pro 享无限扫描 + 批量 CSV（200条），或 WhatsApp 联系。',
        'scan.limit_banner.logged_zh': '⚠️ 免费扫描：今日 5/5 已用完。升级 Pro 享无限扫描 + 批量 CSV（200条），或 WhatsApp 联系。',
        'scan.limit_banner.login_btn': '登录',
        'scan.limit_banner.login_btn_zh': '登录',
        'scan.limit_banner.signup_btn': '注册',
        'scan.limit_banner.signup_btn_zh': '注册',
        'scan.limit_banner.upgrade_btn': '升级',
        'scan.limit_banner.upgrade_btn_zh': '升级',
        'floating_wa_tooltip': 'WhatsApp 联系',

        batchUploadTitle: '批量标题扫描（Pro）',
        batchTemplateHint: 'CSV 格式：original_title（必填），cost_rm（选填），price_rm（选填）。最多 200 行。毛利将自动计算。',
        batchSelectFile: '选择 CSV 文件',
        batchStartScan: '开始批量扫描',
        batchProcessing: '处理中...',
        batchCompleted: '批量扫描完成！报告已下载。',
        batchFailed: '批量扫描失败，请重试。',
        batchProOnly: '批量扫描仅限 Pro 用户使用',
        batchProLockToast: '🔒 批量扫描为 Pro 专属功能。',
        advancedLockToast: '🔒 高级利润设置（运费、卖家类型、返现）为 Pro 功能。升级解锁精准费用模拟。',
        batchUpgradeAction: '升级 Pro',
        batchHelpAction: '获取帮助',
        batchUpgradeHint: '升级 Pro 享无限批量扫描（每次最多200条）。',
        batch_lock_trial: '绑定 WA 激活试用，解锁批量扫描',
        primaryLabel: '主规则',
        proLabel: 'PRO',
        urlParseHint: '仅读取网页公开展示文本，非平台接口数据。',
        trial_modal_title: '激活 7 天 Pro 试用',
        trial_modal_input_placeholder: '+60123456789',
        trial_modal_success: '试用已激活，请查看 WhatsApp',
        trial_error_wa_used: '此 WA 号已激活过试用',
        trialActivate: '激活',
        scanCountLabel: '今日扫描次数',
        scanCountTextPattern: '{used}/{limit}（剩余 {remaining} 次）',
        scanCountUnlimited: '无限次扫描',
        scanCountUsedUp: '今日 5 次扫描已用完'
    }
};

// ============ Init ============
document.addEventListener('DOMContentLoaded', async () => {
    await checkLoginStatus();
    await checkScanHistory();
    await checkBatchPermission();
    await updateScanCountDisplay();

    showMarginIntroBanner();
    checkRulesCard();

    // Initialize floating WA button
    const floatingWABtn = document.getElementById('floatingWABtn');
    if (floatingWABtn) {
        const waLink = window.WHATSAPP_LINK || 'https://wa.me/60123456789';
        floatingWABtn.href = waLink;
    }

    const subscribedEmail = localStorage.getItem('subscribed_email');
    if (subscribedEmail) {
        hideSubscriptionForm();
    }

    applyLanguage(currentLang);

    const scanForm = document.getElementById('scanForm');
    if (scanForm) {
        scanForm.addEventListener('submit', function(e) { e.preventDefault(); handleScan(e); });
    }

    // P1-A: Platform selector event listeners
    const platformShopeeBtn = document.getElementById('platformShopeeBtn');
    const platformLazadaBtn = document.getElementById('platformLazadaBtn');
    if (platformShopeeBtn) {
        platformShopeeBtn.addEventListener('click', () => switchPlatform('shopee'));
    }
    if (platformLazadaBtn) {
        platformLazadaBtn.addEventListener('click', () => switchPlatform('lazada'));
    }

    // P1-A: Auto-detect platform on title input paste/type
    const titleInputEl = document.getElementById('title');
    if (titleInputEl) {
        titleInputEl.addEventListener('paste', () => {
            setTimeout(() => autoDetectPlatform(titleInputEl.value), 0);
        });
        titleInputEl.addEventListener('input', () => {
            const val = titleInputEl.value.trim();
            if (val.startsWith('http')) {
                autoDetectPlatform(val);
            }
        });
    }
    const trialForm = document.getElementById('trialForm');
    if (trialForm) {
        trialForm.addEventListener('submit', function(e) { e.preventDefault(); handleTrialStart(e); });
    }
    const modalClose = document.getElementById('modalClose');
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    const langToggle = document.getElementById('langToggle');
    if (langToggle) {
        langToggle.addEventListener('click', toggleLanguage);
    }
    const batchFile = document.getElementById('batchFile');
    if (batchFile) {
        batchFile.addEventListener('change', handleBatchUpload);
    }
    const csvFileInput = document.getElementById('csvFileInput');
    if (csvFileInput) {
        csvFileInput.addEventListener('change', handleCsvFileSelect);
    }

    const trialModal = document.getElementById('trialModal');
    if (trialModal) {
        trialModal.addEventListener('click', (e) => {
            if (e.target.id === 'trialModal') closeModal();
        });
    }
});



// ============ Batch Upload ============
function downloadSampleCsv() {
    const csvContent = 'original_title,cost_rm,price_rm\n"Wireless Bluetooth Earphone - Best Sound Quality",5.00,29.90\n"Premium Skin Care Serum - Whitening Formula",12.50,45.00';
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'sample_compliance.csv';
    link.click();
}

async function handleBatchUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    if (!trialToken) {
        openModal();
        return;
    }

    showLoading(true);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch('/api/scan-batch', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        if (res.status === 401) {
            alert(currentLang === 'zh' ? '请先登录' : 'Please login first');
            window.location.href = '/login';
            return;
        }

        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `compliance_batch_${Date.now()}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } else {
            const data = await res.json();
            alert(data.detail || (currentLang === 'zh' ? '批量检测失败' : 'Batch scan failed'));
        }
    } catch (err) {
        alert(currentLang === 'zh' ? '批量检测失败，请重试' : 'Batch scan failed. Please try again.');
        console.error(err);
    } finally {
        showLoading(false);
        document.getElementById('batchFile').value = '';
    }
}

// ============ CSV File Select (Pro Batch Upload) ============
function handleCsvFileSelect(e) {
    if (!batchIsPro) {
        showProLockToast();
        e.target.value = '';
        return;
    }
    selectedCsvFile = e.target.files[0];
    if (selectedCsvFile) {
        const fileNameDiv = document.getElementById('selectedFileName');
        fileNameDiv.classList.remove('hidden');
        const fileNameSpan = fileNameDiv.querySelector('span');
        if (fileNameSpan) {
            fileNameSpan.textContent = selectedCsvFile.name;
        }
    }
}

async function runBatchScan() {
    if (!selectedCsvFile) return;

    const batchProgress = document.getElementById('batchProgress');
    batchProgress.classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', selectedCsvFile);

    try {
        const response = await fetch('/api/scan-batch', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        if (response.status === 403) {
            showProLockToast();
            batchProgress.classList.add('hidden');
            return;
        }

        if (!response.ok) {
            const data = await response.json();
            if (data.detail && (data.detail.upgrade || data.detail.error === 'Pro required')) {
                showProLockToast();
            } else {
                showToast(data.detail || translations[currentLang].batchFailed, 'error');
            }
            batchProgress.classList.add('hidden');
            return;
        }

        // Download CSV report
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch_report_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);

        batchProgress.classList.add('hidden');
        showToast(translations[currentLang].batchCompleted, 'success');

    } catch (error) {
        console.error('Batch scan error:', error);
        const errorMsg = error.message || '';
        if (errorMsg.includes('Pro required') || errorMsg.includes('upgrade')) {
            showProLockToast();
        } else {
            showToast(translations[currentLang].batchFailed, 'error');
        }
        batchProgress.classList.add('hidden');
    }
}

function isProUser(data) {
    if (!data || !data.logged_in) return false;
    const now = new Date().getTime();
    return data.status === 'paid' || 
        (data.status === 'trial' && data.trial_end && new Date(data.trial_end).getTime() > now);
}

// ============ Batch Permission Check ============
async function checkBatchPermission() {
    try {
        const res = await fetch('/api/user/info');
        const data = await res.json();

        const batchUploadSection = document.getElementById('batchUploadSection');
        if (!batchUploadSection) return;

        if (data.logged_in) {
            batchIsPro = isProUser(data);
            if (batchIsPro) {
                batchUploadSection.classList.remove('hidden');
                updateBatchButtonsState();
            }
        }
    } catch (error) {
        console.error('Permission check failed:', error);
    }
}

function updateBatchButtonsState() {
    const selectBtn = document.getElementById('selectCsvBtn');
    const scanBtn = document.getElementById('batchScanBtn');
    const batchFreeActivate = document.getElementById('batchFreeActivate');

    if (batchIsPro) {
        // Pro 状态 - 正常样式，隐藏激活入口
        selectBtn.className = 'flex-1 py-2.5 rounded-lg bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-sm font-medium hover:bg-indigo-500/30 transition flex items-center justify-center gap-2';
        scanBtn.className = 'w-full py-2.5 rounded-lg btn-gradient text-white text-sm font-semibold flex items-center justify-center gap-2';
        if (batchFreeActivate) batchFreeActivate.classList.add('hidden');
    } else {
        // Free 状态 - 禁用样式，显示激活入口
        selectBtn.className = 'flex-1 py-2.5 rounded-lg bg-gray-600 border border-gray-500/30 text-gray-400 text-sm font-medium cursor-not-allowed transition flex items-center justify-center gap-2 opacity-80';
        scanBtn.className = 'w-full py-2.5 rounded-lg bg-gray-600 text-gray-400 text-sm font-semibold cursor-not-allowed flex items-center justify-center gap-2 opacity-80';
        if (batchFreeActivate) batchFreeActivate.classList.remove('hidden');
    }
}

function showProLockToast() {
    const t = translations[currentLang];
    showToast(
        t.batchProLockToast,
        'warning',
        [
            { text: t.batchUpgradeAction, onclick: () => handleUpgradeFromIndex('batch_lock_toast') },
            { text: t.batchHelpAction, url: WHATSAPP_LINK, target: '_blank' }
        ]
    );
}

function handleSelectCsvClick() {
    if (!batchIsPro) {
        showProLockToast();
        return;
    }
    document.getElementById('csvFileInput').click();
}

function handleBatchScanClick() {
    if (!batchIsPro) {
        showProLockToast();
        return;
    }
    runBatchScan();
}

// ============ Scan Count Display ============
async function updateScanCountDisplay() {
    try {
        const res = await fetch('/api/user/info');
        const data = await res.json();
        const indicator = document.getElementById('scanCountIndicator');
        const textEl = document.getElementById('scanCountText');
        if (!indicator || !textEl) return;

        const t = translations[currentLang];

        if (data.is_pro) {
            // Pro 用户：显示无限次
            textEl.textContent = t.scanCountUnlimited;
            indicator.classList.remove('hidden');
        } else if (data.scan_limit != null) {
            // Free/Guest 用户：显示剩余次数
            const used = data.scan_count_today || 0;
            const limit = data.scan_limit;
            const remaining = Math.max(0, limit - used);
            textEl.textContent = t.scanCountTextPattern
                .replace('{used}', used)
                .replace('{limit}', limit)
                .replace('{remaining}', remaining);
            indicator.classList.remove('hidden');
        }
    } catch (err) {
        console.error('Failed to fetch scan count:', err);
    }
}

// ============ Check Login Status ============
async function checkLoginStatus() {
    try {
        const res = await fetch('/api/user/info');
        const data = await res.json();
        
        if (data.logged_in) {
            trialToken = getCookie('session_token');
            trialEmail = data.email;
            userIsPro = isProUser(data);

            updateAuthButton(true, data.email);
            showPaidBar(data.email, data.status, data.plan_type, data.paid_until, data.trial_end, data.trial_remaining_days);
            updateAdvancedSettingsLock();
            // IntelliAudit 2.0 Pro: 加载当前平台偏好默认值
            loadPlatformPreferences(currentPlatform);
            attachPrefEditListeners();
            updateSupplierPickerVisibility();
        } else {
            trialToken = null;
            trialEmail = null;
            trialEnd = null;
            userIsPro = false;
            const bar = document.getElementById('trialBar');
            if (bar) bar.classList.add('hidden');
            updateAuthButton(false);
            updateAdvancedSettingsLock();
            hidePrefStatusRow();
            updateSupplierPickerVisibility();
        }
    } catch (err) {
        console.error('Failed to check login status:', err);
        trialToken = null;
        trialEmail = null;
        trialEnd = null;
        updateAuthButton(false);
    }
}

// ============ Check Scan History ============
async function checkScanHistory() {
    try {
        const res = await fetch('/api/user/info');
        const data = await res.json();
        
        const firstTimeBanner = document.getElementById('firstTimeBanner');
        if (!firstTimeBanner) return;

        if (!data.logged_in) {
            firstTimeBanner.classList.remove('hidden');
        }
    } catch (err) {
        console.error('Failed to check scan history:', err);
        const firstTimeBanner = document.getElementById('firstTimeBanner');
        if (firstTimeBanner) {
            firstTimeBanner.classList.remove('hidden');
        }
    }
}

// ============ Update Auth Button ============
function updateAuthButton(isLoggedIn, email = null) {
    const authButton = document.getElementById('authButton');
    if (!authButton) return;

    const t = translations[currentLang];

    if (isLoggedIn && email) {
        // 已登录：显示邮箱 + Pro后台入口 + Logout按钮
        authButton.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="text-green-400 text-xs sm:text-sm font-medium truncate max-w-[120px]">${email}</span>
                <a href="/dashboard" class="text-indigo-400 hover:text-indigo-300 text-xs sm:text-sm font-medium transition">
                    ${currentLang === 'zh' ? 'Pro后台' : 'Pro Dashboard'}
                </a>
                <button onclick="handleLogout()" class="text-red-400 hover:text-red-300 text-xs sm:text-sm font-medium transition">
                    ${t.logout}
                </button>
            </div>
        `;
    } else {
        // 未登录：显示Login链接
        authButton.innerHTML = `
            <a href="/login" data-i18n="login" class="text-indigo-400 hover:text-indigo-300 text-xs sm:text-sm font-medium transition">
                → ${t.login}
            </a>
        `;
    }
}

// ============ Logout ============
async function handleLogout() {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
    } catch (err) {
        console.error('Logout API call failed:', err);
    }
    // 清除所有相关 cookie（兜底）
    document.cookie = 'session_token=; Max-Age=0; path=/; SameSite=Lax';
    document.cookie = 'session_token=; Max-Age=0; path=/; domain=' + window.location.hostname + '; SameSite=Lax';
    // 清除 localStorage
    localStorage.removeItem('trial_token');
    localStorage.removeItem('trial_email');
    localStorage.removeItem('trial_end');
    localStorage.removeItem('scan_history');
    // 重置全局变量
    trialToken = null;
    trialEmail = null;
    trialEnd = null;
    // 刷新页面
    window.location.href = '/';
}

// ============ Paid Bar ============
function showPaidBar(email, status, planType, paidUntil, trialEnd, trialRemainingDays) {
    const bar = document.getElementById('trialBar');
    if (!bar) return;
    
    const t = translations[currentLang];
    document.getElementById('trialEmail').textContent = email;
    
    const remainingLabel = document.querySelector('[data-i18n="trialRemaining"]');
    const daysLabel = document.querySelector('[data-i18n="days"]');
    
    if (status === 'free') {
        document.getElementById('trialDays').textContent = t.pendingActivation || '待激活';
        if (remainingLabel) {
            remainingLabel.style.display = 'none';
        }
        if (daysLabel) {
            daysLabel.style.display = 'none';
        }
    } else {
        if (remainingLabel) {
            remainingLabel.style.display = 'inline';
        }
        if (daysLabel) {
            daysLabel.style.display = 'inline';
        }
        let remainingDays = trialRemainingDays || 0;
        if (status === 'paid' && paidUntil && !trialRemainingDays) {
            const end = new Date(paidUntil);
            const now = new Date();
            const diff = end - now;
            remainingDays = Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
        } else if (status === 'trial' && trialEnd && !trialRemainingDays) {
            const end = new Date(trialEnd);
            const now = new Date();
            const diff = end - now;
            remainingDays = Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
        }
        
        document.getElementById('trialDays').textContent = remainingDays;
        
        if (remainingLabel) {
            remainingLabel.textContent = t.trialRemaining;
        }
        if (daysLabel) {
            daysLabel.textContent = t.days;
        }
    }
    
    bar.classList.remove('hidden');
}

// ============ Language ============
function toggleLanguage() {
    currentLang = currentLang === 'en' ? 'zh' : 'en';
    localStorage.setItem('lang', currentLang);
    applyLanguage(currentLang);
    updateScanCountDisplay();
}

function applyLanguage(lang) {
    const t = translations[lang];
    const isZh = lang === 'zh';

    const langBtn = document.getElementById('langToggle');
    if (langBtn) {
        langBtn.innerHTML = `🌐 ${isZh ? 'EN' : '中'}`;
    }

    const authButton = document.getElementById('authButton');
    if (authButton) {
        const isLoggedIn = trialToken !== null || document.cookie.includes('session_token') || localStorage.getItem('trial_token') !== null;
        if (isLoggedIn) {
            const logoutBtn = authButton.querySelector('button');
            if (logoutBtn) {
                logoutBtn.textContent = t.logout;
            }
            const dashboardLink = authButton.querySelector('a[href="/dashboard"]');
            if (dashboardLink) {
                dashboardLink.textContent = isZh ? 'Pro后台' : 'Pro Dashboard';
            } else {
                authButton.innerHTML = `
                    <div class="flex items-center gap-3">
                        <span class="text-green-400 text-xs sm:text-sm font-medium truncate max-w-[120px]">${trialEmail || 'User'}</span>
                        <a href="/dashboard" class="text-indigo-400 hover:text-indigo-300 text-xs sm:text-sm font-medium transition">
                            ${isZh ? 'Pro后台' : 'Pro Dashboard'}
                        </a>
                        <button onclick="handleLogout()" class="text-red-400 hover:text-red-300 text-xs sm:text-sm font-medium transition">
                            ${t.logout}
                        </button>
                    </div>
                `;
            }
        } else {
            const loginLink = authButton.querySelector('a');
            if (loginLink) {
                loginLink.textContent = `→ ${t.login}`;
            }
        }
    }

    updateText('[data-i18n="pageTitle"]', t.pageTitle);
    updateText('[data-i18n="pageSubtitle"]', t.pageSubtitle);
    updateText('[data-i18n="productTitle"]', t.productTitle);
    updateText('[data-i18n="titlePlaceholder"]', t.titlePlaceholder, 'placeholder');
    updateText('[data-i18n="description"]', t.description);
    updateText('[data-i18n="descPlaceholder"]', t.descPlaceholder, 'placeholder');
    updateText('[data-i18n="productUrl"]', t.productUrl);
    updateText('[data-i18n="category"]', t.category);
    updateText('[data-i18n="categoryPlaceholder"]', t.categoryPlaceholder, 'placeholder');
    updateText('[data-i18n="productCategory"]', t.productCategory);
    updateText('[data-i18n="startScan"]', t.startScan);
    updateText('[data-i18n="scanNow"]', t.scanNow);
    updateText('[data-i18n="scanning"]', t.scanning);
    updateText('[data-i18n="tabTextInput"]', t.tabTextInput);
    updateText('[data-i18n="tabUrlInput"]', t.tabUrlInput);
    updateText('[data-i18n="fetchMetaBtn"]', t.fetchMetaBtn);
    updateText('[data-i18n="batchUpload"]', t.batchUpload);
    updateText('[data-i18n="sampleCsv"]', t.sampleCsv);
    updateText('[data-i18n="emailCaptureLabel"]', t.emailCaptureLabel);
    updateText('[data-i18n="subscribeBtn"]', t.subscribeBtn);
    updateText('[data-i18n="login"]', t.login);
    updateText('[data-i18n="unlockTrial"]', t.unlockTrial);
    updateText('[data-i18n="trialHint"]', t.trialHint);
    updateText('[data-i18n="emailPlaceholder"]', t.emailPlaceholder, 'placeholder');
    updateText('[data-i18n="unlock"]', t.unlock);
    updateText('[data-i18n="cancel"]', t.cancel);
    updateText('[data-i18n="trialRemaining"]', t.trialRemaining);
    updateText('[data-i18n="days"]', t.days);
    updateText('[data-i18n="guide"]', t.guide);
    updateText('[data-i18n="close"]', t.close);
    updateText('[data-i18n="continueScan"]', t.continueScan);
    updateText('[data-i18n="backHome"]', t.backHome);
    updateText('[data-i18n="scanReport"]', t.scanReport);
    updateText('[data-i18n="productInfo"]', t.productInfo);
    updateText('[data-i18n="riskStats"]', t.riskStats);
    updateText('[data-i18n="severe"]', t.severe);
    updateText('[data-i18n="moderate"]', t.moderate);
    updateText('[data-i18n="minor"]', t.minor);
    updateText('[data-i18n="violationDetails"]', t.violationDetails);
    updateText('[data-i18n="upgradePro"]', t.upgradePro);
    updateText('[data-i18n="footerPolicy"]', t.footerPolicy);
    updateText('[data-i18n="footerDisclaimer"]', t.footerDisclaimer);
    updateText('[data-i18n="limitBannerText"]', t.limitBannerText);
    updateText('[data-i18n="limitBannerBtn"]', t.limitBannerBtn);
    updateText('[data-i18n="firstTimeBannerText"]', t.firstTimeBannerText);
    updateText('[data-i18n="scan.banner.title"]', t['scan.banner.title']);
    updateText('[data-i18n="scan.banner.body"]', t['scan.banner.body'], 'html');
    updateText('[data-i18n="scan.advanced.toggle"]', t['scan.advanced.toggle']);
    updateText('[data-i18n="scan.advanced.lock_title"]', t['scan.advanced.lock_title']);
    updateText('[data-i18n="scan.advanced.lock_desc"]', t['scan.advanced.lock_desc']);
    updateText('[data-i18n="scan.advanced.lock_btn"]', t['scan.advanced.lock_btn']);
    updateText('[data-i18n="scan.form.shipping_fee_label"]', t['scan.form.shipping_fee_label']);
    updateText('[data-i18n="scan.form.shipping_cost_label"]', t['scan.form.shipping_cost_label']);
    updateText('[data-i18n="scan.form.seller_type_label"]', t['scan.form.seller_type_label']);
    updateText('[data-i18n="scan.form.cashback_label"]', t['scan.form.cashback_label']);
    updateText('[data-i18n="scan.rule_alert.text"]', t['scan.rule_alert.text']);
    updateText('[data-i18n="noReport"]', t.noReport);
    updateText('[data-i18n="goHome"]', t.goHome);
    updateText('[data-i18n="previewOnly"]', t.previewOnly);
    updateText('[data-i18n="referenceTitleNote"]', t.referenceTitleNote);
    updateText('[data-i18n="reportFalsePositive"]', t.reportFalsePositive);
    updateText('[data-i18n="falsePositiveWordPlaceholder"]', t.falsePositiveWordPlaceholder, 'placeholder');
    updateText('[data-i18n="falsePositiveReasonPlaceholder"]', t.falsePositiveReasonPlaceholder, 'placeholder');
    updateText('[data-i18n="submit"]', t.submit);

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        // Skip keys that are handled above
        if (key === 'scan.banner.body') return;
        // Skip input/textarea elements (they use placeholder, not textContent)
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return;
        if (key && t[key]) {
            el.textContent = t[key];
        }
    });

    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
        const key = el.getAttribute('data-i18n-ph');
        if (key && t[key]) {
            el.placeholder = t[key];
        }
    });

    const catSelect = document.getElementById('productCategory');
    if (catSelect) {
        catSelect.querySelectorAll('option').forEach(opt => {
            const key = opt.getAttribute('data-i18n');
            if (key && t[key]) {
                opt.textContent = t[key];
            }
        });
    }

    const sellerSelect = document.getElementById('seller_type');
    if (sellerSelect) {
        sellerSelect.querySelectorAll('option').forEach(opt => {
            const key = opt.getAttribute('data-i18n');
            if (key && t[key]) {
                opt.textContent = t[key];
            }
        });
    }

    
    updateText('[data-i18n="ruleSetLabel"]', t.ruleSetLabel);
    updateText('[data-i18n="platformShopee"]', t.platformShopee);
    updateText('[data-i18n="platformLazada"]', t.platformLazada);

    const titleInput = document.getElementById('title');
    const descInput = document.getElementById('description');
    const urlInput = document.getElementById('urlInput');
    const emailInput = document.getElementById('modalEmail');
    const captureEmail = document.getElementById('captureEmail');

    if (titleInput) titleInput.placeholder = t.titlePlaceholder;
    if (descInput) descInput.placeholder = t.descPlaceholder;
    if (urlInput) urlInput.placeholder = t.urlPlaceholder;
    if (emailInput) emailInput.placeholder = t.emailPlaceholder;
    if (captureEmail) captureEmail.placeholder = t.emailPlaceholder;
}

function updateText(selector, text, attr = 'text') {
    const el = document.querySelector(selector);
    if (el) {
        if (attr === 'placeholder') {
            el.placeholder = text;
        } else if (attr === 'html') {
            el.innerHTML = text;
        } else if (attr === 'text') {
            el.textContent = text;
        } else {
            el[attr] = text;
        }
    }
}

// ============ Trial Bar ============
function showTrialBar(email, days) {
    const bar = document.getElementById('trialBar');
    if (!bar) return;
    document.getElementById('trialEmail').textContent = email;
    document.getElementById('trialDays').textContent = days;
    bar.classList.remove('hidden');
}

function clearTrial() {
    localStorage.removeItem('trial_token');
    localStorage.removeItem('trial_email');
    localStorage.removeItem('trial_end');
    trialToken = null;
    trialEmail = null;
    trialEnd = null;
    const bar = document.getElementById('trialBar');
    if (bar) bar.classList.add('hidden');
}

function getRemainingDays(endStr) {
    const end = new Date(endStr);
    const now = new Date();
    const diff = end - now;
    return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

function showMarginIntroBanner() {
    const dismissed = localStorage.getItem('dismissed_margin_intro');
    if (dismissed !== 'true') {
        const banner = document.getElementById('marginIntroBanner');
        if (banner) {
            banner.classList.remove('hidden');
        }
    }
}

function dismissMarginBanner() {
    const banner = document.getElementById('marginIntroBanner');
    if (banner) {
        banner.classList.add('hidden');
    }
    localStorage.setItem('dismissed_margin_intro', 'true');
}

function checkRulesCard() {
    const dismissed = localStorage.getItem('hide_rule_alert');
    if (dismissed === 'true') {
        const card = document.getElementById('rulesSnapshotCard');
        if (card) {
            card.classList.add('hidden');
        }
    }
}

function dismissRulesCard() {
    const card = document.getElementById('rulesSnapshotCard');
    if (card) {
        card.classList.add('hidden');
    }
    localStorage.setItem('hide_rule_alert', 'true');
}

// ============ Advanced Settings Toggle ============
// IntelliAudit 2.0 Pro: Free 用户可展开 Advanced，仅 seller_type 禁用
// shipping_fee / shipping_cost / cashback 对 Free 可编辑
function updateAdvancedSettingsLock() {
    const toggle = document.getElementById('advancedToggle');
    const settings = document.getElementById('advancedSettings');
    const overlay = document.getElementById('advancedLockOverlay');
    if (!toggle || !settings) return;

    // 永久隐藏旧的整面板锁定遮罩（Free 现在可展开）
    if (overlay) {
        overlay.classList.add('hidden');
    }

    const proBadge = toggle.querySelector('.pro-badge');
    const sellerTypeBadge = settings.querySelector('.seller-type-pro-badge');
    if (!userIsPro) {
        // Free 用户：保留 PRO 标识（提示 seller_type 是 Pro 专属）
        if (!proBadge) {
            const badge = document.createElement('span');
            badge.className = 'pro-badge text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-medium ml-1';
            badge.textContent = 'PRO';
            toggle.querySelector('button').appendChild(badge);
        }
        if (sellerTypeBadge) sellerTypeBadge.classList.remove('hidden');
        // 仅禁用 seller_type（+ opacity-40），其余输入可编辑
        const sellerType = settings.querySelector('#seller_type');
        if (sellerType) {
            sellerType.disabled = true;
            sellerType.classList.add('opacity-40', 'cursor-not-allowed');
        }
        // 确保 shipping_fee / shipping_cost / cashback 可编辑
        ['shipping_fee', 'shipping_cost', 'cashback_enabled'].forEach(id => {
            const el = settings.querySelector('#' + id);
            if (el) {
                el.disabled = false;
                el.classList.remove('opacity-40', 'cursor-not-allowed');
            }
        });
    } else {
        // Pro 用户：移除 Pro 标识 + 全部启用
        if (proBadge) proBadge.remove();
        if (sellerTypeBadge) sellerTypeBadge.classList.add('hidden');
        settings.querySelectorAll('input, select').forEach(el => {
            el.disabled = false;
            el.classList.remove('opacity-40', 'cursor-not-allowed');
        });
    }
}

function toggleAdvanced() {
    const settings = document.getElementById('advancedSettings');
    const chevron = document.getElementById('advancedChevron');

    // IntelliAudit 2.0 Pro: Free 用户可展开 Advanced（不再拦截）
    // 仅 seller_type 仍禁用（在 updateAdvancedSettingsLock 中处理）

    if (settings.classList.contains('hidden')) {
        settings.classList.remove('hidden');
        chevron.style.transform = 'rotate(90deg)';
    } else {
        settings.classList.add('hidden');
        chevron.style.transform = 'rotate(0deg)';
    }
}

// ============ IntelliAudit 2.0 Pro: 平台偏好自动回填 ============
// 按平台隔离记忆：shipping_fee / shipping_cost / default_category / cashback / seller_type
// 状态标签：📌 使用默认 / ✏ 已修改 / 💾 已保存
let platformPrefsCache = {};  // {shopee: {...}, lazada: {...}}
let prefsLoadedForPlatform = { shopee: false, lazada: false };

async function loadPlatformPreferences(platform) {
    // 仅已登录 Pro 用户加载偏好默认值
    if (!userIsPro || !trialEmail) {
        hidePrefStatusRow();
        return;
    }
    try {
        const res = await fetch(`/api/user/preferences/platform?platform=${platform}`);
        if (!res.ok) { hidePrefStatusRow(); return; }
        const data = await res.json();
        if (!data.success) { hidePrefStatusRow(); return; }
        const prefs = data.preferences || {};
        platformPrefsCache[platform] = { ...prefs };
        prefsLoadedForPlatform[platform] = true;

        // 回填表单（不覆盖用户正在编辑的值，仅在为空或首次加载时填入）
        const shippingFee = document.getElementById('shipping_fee');
        const shippingCost = document.getElementById('shipping_cost');
        const categorySelect = document.getElementById('productCategory');
        const cashbackCheckbox = document.getElementById('cashback_enabled');
        const sellerType = document.getElementById('seller_type');

        if (shippingFee && prefs.shipping_fee != null) shippingFee.value = prefs.shipping_fee || '';
        if (shippingCost && prefs.shipping_cost != null) shippingCost.value = prefs.shipping_cost || '';
        if (categorySelect && prefs.default_category) categorySelect.value = prefs.default_category;

        // Cashback：Lazada 强制 false + 隐藏（由 applyPlatformUI 处理），Shopee 按偏好
        if (platform === 'shopee' && cashbackCheckbox && prefs.cashback != null) {
            cashbackCheckbox.checked = !!prefs.cashback;
        }
        // seller_type：Pro 用户按偏好；Free 用户保持禁用默认 marketplace
        if (userIsPro && sellerType && prefs.seller_type) {
            sellerType.value = prefs.seller_type;
        }

        updatePrefStatusTag('default');
    } catch (e) {
        console.warn('[Preferences] load failed:', e);
        hidePrefStatusRow();
    }
}

function updatePrefStatusTag(state) {
    const row = document.getElementById('prefStatusRow');
    const tag = document.getElementById('prefStatusTag');
    if (!row || !tag) return;
    if (!userIsPro) { hidePrefStatusRow(); return; }
    row.classList.remove('hidden');
    row.style.display = 'flex';
    const t = (translations[currentLang] || {});
    if (state === 'default') {
        tag.innerHTML = '📌 <span>' + (t.prefStatusDefault || 'Using saved default') + '</span>';
        tag.className = 'text-[10px] text-slate-400 flex items-center gap-1';
    } else if (state === 'edited') {
        tag.innerHTML = '✏ <span>' + (t.prefStatusEdited || 'Modified — click "Save as Default" to update') + '</span>';
        tag.className = 'text-[10px] text-amber-400 flex items-center gap-1';
    } else if (state === 'saved') {
        tag.innerHTML = '💾 <span>' + (t.prefStatusSaved || 'Saved as default') + '</span>';
        tag.className = 'text-[10px] text-green-400 flex items-center gap-1';
        setTimeout(() => updatePrefStatusTag('default'), 2000);
    }
}

function hidePrefStatusRow() {
    const row = document.getElementById('prefStatusRow');
    if (row) row.style.display = 'none';
}

// 给高级设置字段绑定 change/input 监听，触发 ✏ 状态
let prefListenersAttached = false;
function attachPrefEditListeners() {
    if (prefListenersAttached) return;
    const ids = ['shipping_fee', 'shipping_cost', 'productCategory', 'cashback_enabled', 'seller_type'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', checkPrefEdited);
            el.addEventListener('change', checkPrefEdited);
        }
    });
    prefListenersAttached = true;
}

// ============ Phase 2.3: 扫描页供应商选择器（🏭 图标）============
// Pro 用户：点击 🏭 弹出供应商列表，选择后仅填入成本（不覆盖类目）
let scanSuppliersCache = null;  // null=未加载, []=已加载但空

function updateSupplierPickerVisibility() {
    const btn = document.getElementById('supplierPickerBtn');
    if (!btn) return;
    // 仅 Pro 用户显示 🏭 按钮
    btn.classList.toggle('hidden', !userIsPro);
}

async function toggleSupplierPicker(event) {
    if (event) event.stopPropagation();
    const dropdown = document.getElementById('supplierDropdown');
    if (!dropdown) return;
    if (dropdown.classList.contains('hidden')) {
        // 打开前先加载
        await loadScanSuppliers();
        dropdown.classList.remove('hidden');
    } else {
        dropdown.classList.add('hidden');
    }
}

async function loadScanSuppliers() {
    if (!userIsPro) return;
    const loadingEl = document.getElementById('supplierDropdownLoading');
    const listEl = document.getElementById('supplierDropdownList');
    const emptyEl = document.getElementById('supplierDropdownEmpty');
    if (loadingEl) loadingEl.classList.remove('hidden');
    if (listEl) listEl.innerHTML = '';
    if (emptyEl) emptyEl.classList.add('hidden');
    try {
        const res = await fetch('/api/user/preferences/suppliers');
        if (!res.ok) { if (loadingEl) loadingEl.classList.add('hidden'); return; }
        const data = await res.json();
        scanSuppliersCache = data.suppliers || [];
        if (loadingEl) loadingEl.classList.add('hidden');
        if (scanSuppliersCache.length === 0) {
            if (emptyEl) emptyEl.classList.remove('hidden');
            return;
        }
        const isZh = currentLang === 'zh';
        if (listEl) {
            listEl.innerHTML = scanSuppliersCache.map((s, i) => `
                <button type="button" onclick="selectSupplier(${i})" class="w-full text-left px-3 py-2 hover:bg-white/5 transition border-b border-white/5 last:border-0">
                    <div class="text-white text-xs font-medium truncate">${escapeHtmlScan(s.name)}</div>
                    <div class="text-[10px] text-slate-500 mt-0.5 flex items-center gap-1.5">
                        <span class="px-1 py-0.5 rounded bg-slate-700/50 text-slate-400">${escapeHtmlScan(s.category || 'general')}</span>
                        <span class="text-emerald-400">RM ${(s.cost || 0).toFixed(2)}</span>
                    </div>
                </button>
            `).join('');
        }
    } catch (e) {
        console.error('loadScanSuppliers error:', e);
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

function selectSupplier(idx) {
    const s = scanSuppliersCache && scanSuppliersCache[idx];
    if (!s) return;
    // 仅填入成本，不覆盖类目（Phase 2.3 要求）
    const costInput = document.getElementById('cost_rm');
    if (costInput) {
        costInput.value = (s.cost || 0).toFixed(2);
        // 触发 input 事件以更新偏好编辑状态
        costInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    // 关闭下拉
    const dropdown = document.getElementById('supplierDropdown');
    if (dropdown) dropdown.classList.add('hidden');
    // Phase 4.3: 埋点 supplier_selected
    trackEvent('supplier_selected', {
        supplier_name: s.name,
        category: s.category || 'general',
        cost: s.cost || 0,
        platform: currentPlatform,
    });
}

function escapeHtmlScan(str) {
    if (str == null) return '';
    return String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
}

// 点击外部关闭供应商下拉
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('supplierDropdown');
    const btn = document.getElementById('supplierPickerBtn');
    if (dropdown && !dropdown.classList.contains('hidden')) {
        if (!dropdown.contains(e.target) && e.target !== btn) {
            dropdown.classList.add('hidden');
        }
    }
});

// 检测高级设置字段是否被用户修改（与缓存对比）
function checkPrefEdited() {
    if (!userIsPro) return;
    const platform = currentPlatform;
    const prefs = platformPrefsCache[platform];
    if (!prefs) return;
    const shippingFee = document.getElementById('shipping_fee')?.value;
    const shippingCost = document.getElementById('shipping_cost')?.value;
    const category = document.getElementById('productCategory')?.value;
    const cashback = document.getElementById('cashback_enabled')?.checked;
    const sellerType = document.getElementById('seller_type')?.value;

    const numEq = (a, b) => (parseFloat(a) || 0) === (parseFloat(b) || 0);
    const edited =
        !numEq(shippingFee, prefs.shipping_fee) ||
        !numEq(shippingCost, prefs.shipping_cost) ||
        (category !== (prefs.default_category || 'general')) ||
        (platform === 'shopee' && cashback !== !!prefs.cashback) ||
        (sellerType !== (prefs.seller_type || 'marketplace'));
    updatePrefStatusTag(edited ? 'edited' : 'default');
}

async function saveCurrentAsDefault() {
    if (!userIsPro) {
        showToast((translations[currentLang]?.advancedLockToast) || 'Pro only', 'warning');
        return;
    }
    const platform = currentPlatform;
    const payload = {
        platforms: {
            [platform]: {
                shipping_fee: parseFloat(document.getElementById('shipping_fee')?.value) || 0,
                shipping_cost: parseFloat(document.getElementById('shipping_cost')?.value) || 0,
                default_category: document.getElementById('productCategory')?.value || 'general',
                cashback: platform === 'shopee' ? !!document.getElementById('cashback_enabled')?.checked : false,
                seller_type: document.getElementById('seller_type')?.value || 'marketplace',
            }
        }
    };
    try {
        const res = await fetch('/api/user/preferences', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || 'Save failed', 'error');
            return;
        }
        const data = await res.json();
        platformPrefsCache[platform] = data.preferences?.platforms?.[platform] || platformPrefsCache[platform];
        updatePrefStatusTag('saved');
    } catch (e) {
        console.error('[Preferences] save failed:', e);
        showToast('Save failed', 'error');
    }
}

// ============ Modal ============
// V1.0: WA 号为注册必填项，无单独激活 Trial 流程。
// 所有弹窗入口统一跳转到 /login#register（注册页面）完成注册即自动激活 14 天 Trial。
function openModal() {
    window.location.href = '/login#register';
}

function closeModal() {
    // 已无弹窗。预留函数以兼容现有调用点。
}

// ============ Bind WA Modal ============
function openBindWaModal() {
    window.location.href = '/login#register';
}

function closeBindWaModal() {
    // 已无弹窗。预留函数以兼容现有调用点。
}

async function handleBindWa() {
    window.location.href = '/login#register';
}

// ============ Scan ============
function isShopeeUrl(text) {
    const trimmed = text.trim();
    if (!trimmed.startsWith('http')) return false;
    try {
        const url = new URL(trimmed);
        const hostname = url.hostname.toLowerCase();
        return hostname.includes('shopee.com') || hostname.includes('xiapibuy.com');
    } catch {
        return false;
    }
}

function isLazadaUrl(text) {
    const trimmed = text.trim();
    if (!trimmed.startsWith('http')) return false;
    try {
        const url = new URL(trimmed);
        const hostname = url.hostname.toLowerCase();
        return hostname.includes('lazada.com');
    } catch {
        return false;
    }
}

// ============ P1-A: Platform Switching Logic ============

// P2: Log platform-related events for analytics
async function logPlatformEvent(eventName, eventData = {}) {
    try {
        await fetch('/api/upgrade-clicked', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event_name: eventName, ...eventData })
        });
    } catch (e) {}
}

function showSimpleToast(message, duration = 3000) {
    const existing = document.getElementById('platformToast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'platformToast';
    toast.className = 'fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-lg bg-slate-800 border border-orange-500/50 text-sm text-white shadow-lg transition-all duration-300';
    toast.style.opacity = '0';
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.style.opacity = '1';
    });

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function isFormNonEmpty() {
    const title = document.getElementById('title')?.value?.trim();
    const cost = document.getElementById('cost_rm')?.value?.trim();
    const price = document.getElementById('price_rm')?.value?.trim();
    return (title && title.length > 0) || (cost && cost.length > 0) || (price && price.length > 0);
}

function applyPlatformUI(platform) {
    const shopeeBtn = document.getElementById('platformShopeeBtn');
    const lazadaBtn = document.getElementById('platformLazadaBtn');
    const cashbackWrapper = document.getElementById('cashbackWrapper');
    const cashbackCheckbox = document.getElementById('cashback_enabled');
    const shippingFeeInput = document.getElementById('shipping_fee');

    if (shopeeBtn && lazadaBtn) {
        if (platform === 'lazada') {
            shopeeBtn.className = 'platform-btn px-4 py-1.5 text-xs font-medium transition-colors bg-slate-800 text-slate-400 hover:text-white';
            lazadaBtn.className = 'platform-btn px-4 py-1.5 text-xs font-medium transition-colors bg-orange-600 text-white';
        } else {
            shopeeBtn.className = 'platform-btn px-4 py-1.5 text-xs font-medium transition-colors bg-orange-600 text-white';
            lazadaBtn.className = 'platform-btn px-4 py-1.5 text-xs font-medium transition-colors bg-slate-800 text-slate-400 hover:text-white';
        }
    }

    // Lazada: hide cashback, clear value
    if (cashbackWrapper) {
        if (platform === 'lazada') {
            cashbackWrapper.style.display = 'none';
            if (cashbackCheckbox) cashbackCheckbox.checked = false;
        } else {
            cashbackWrapper.style.display = '';
            if (cashbackCheckbox) cashbackCheckbox.checked = true;
        }
    }

    // Lazada: pre-fill shipping fee with RM 4.50 + hint
    if (shippingFeeInput) {
        if (platform === 'lazada') {
            if (!shippingFeeInput.value) {
                shippingFeeInput.value = '4.50';
            }
            shippingFeeInput.placeholder = '4.50';
        } else {
            if (shippingFeeInput.value === '4.50') {
                shippingFeeInput.value = '';
            }
            shippingFeeInput.placeholder = '0.00';
        }
    }
}

function switchPlatform(targetPlatform, skipConfirm = false) {
    if (targetPlatform === currentPlatform) return;

    const t = translations[currentLang];

    // Check if form has data and confirm
    if (!skipConfirm && isFormNonEmpty()) {
        const confirmed = confirm(`${t.platformSwitchConfirm}\n\n${t.platformSwitchConfirmMsg}`);
        if (!confirmed) return;
    }

    // P2: Log platform_switch event
    const previousPlatform = currentPlatform;
    currentPlatform = targetPlatform;

    logPlatformEvent('platform_switch', { from: previousPlatform, to: targetPlatform });

    // Reset platform-specific fields (keep cost and price)
    const titleInput = document.getElementById('title');
    const descInput = document.getElementById('description');
    const categorySelect = document.getElementById('productCategory');

    if (titleInput) titleInput.value = '';
    if (descInput) descInput.value = '';
    if (categorySelect) categorySelect.selectedIndex = 0;

    applyPlatformUI(currentPlatform);
    // IntelliAudit 2.0 Pro: 切换平台后加载该平台偏好默认值
    loadPlatformPreferences(currentPlatform);
}

// Auto-detect Lazada URL on paste and switch platform
function autoDetectPlatform(text) {
    if (isLazadaUrl(text) && currentPlatform !== 'lazada') {
        const t = translations[currentLang];
        currentPlatform = 'lazada';
        applyPlatformUI('lazada');
        showSimpleToast(t.lazadaDetectedToast);
    } else if (isShopeeUrl(text) && currentPlatform !== 'shopee') {
        currentPlatform = 'shopee';
        applyPlatformUI('shopee');
    }
}

async function handleScan(e) {
    e.preventDefault();

    let title = document.getElementById('title').value.trim();
    let description = document.getElementById('description').value.trim();
    let source_type = 'text';
    let shop_id = null;
    let item_id = null;

    // P1-A: Auto-detect platform from URL before scanning
    if (title.startsWith('http')) {
        autoDetectPlatform(title);
    }

    const productCategory = document.getElementById('productCategory').value || 'general';
    
    const costInput = document.getElementById('cost_rm');
    const priceInput = document.getElementById('price_rm');
    let cost_rm = costInput && costInput.value ? parseFloat(costInput.value) : null;
    let price_rm = priceInput && priceInput.value ? parseFloat(priceInput.value) : null;

    // Phase 1: Advanced profit settings
    const shippingFeeInput = document.getElementById('shipping_fee');
    const shippingCostInput = document.getElementById('shipping_cost');
    const sellerTypeSelect = document.getElementById('seller_type');
    const cashbackCheckbox = document.getElementById('cashback_enabled');
    let shipping_fee = shippingFeeInput && shippingFeeInput.value ? parseFloat(shippingFeeInput.value) : null;
    let shipping_cost = shippingCostInput && shippingCostInput.value ? parseFloat(shippingCostInput.value) : null;
    let seller_type = sellerTypeSelect ? sellerTypeSelect.value : 'marketplace';
    let cashback_enabled = cashbackCheckbox ? cashbackCheckbox.checked : true;

    if (!title) {
        alert(currentLang === 'zh' ? '请输入商品标题或链接' : 'Please enter product title or URL');
        return;
    }

    if (isShopeeUrl(title)) {
        const url = title;
        showLoading(true);
        
        try {
            const fetchRes = await fetch('/api/fetch-meta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const fetchData = await fetchRes.json();
            
            if (fetchData.success && fetchData.title) {
                title = fetchData.title;
                source_type = 'url';
                
                const urlMatch = url.match(/-i\.(\d+)\.(\d+)/);
                if (urlMatch) {
                    shop_id = urlMatch[1];
                    item_id = urlMatch[2];
                }
                
                if (fetchData.description) {
                    description = fetchData.description;
                    const descInput = document.getElementById('description');
                    if (descInput) {
                        descInput.value = description;
                    }
                }
                
                const titleInput = document.getElementById('title');
                if (titleInput) {
                    titleInput.value = title;
                }
            } else if (fetchData.limit_hit) {
                showLoading(false);
                openModal();
                return;
            } else if (!fetchData.title) {
                alert(currentLang === 'zh' ? '无法解析链接，请手动输入标题' : 'Cannot parse link. Please enter title manually.');
                showLoading(false);
                return;
            }
        } catch (err) {
            showLoading(false);
            alert(currentLang === 'zh' ? '链接解析失败，请手动输入标题' : 'Failed to parse link. Please enter title manually.');
            return;
        }
    } else if (isLazadaUrl(title)) {
        const url = title;
        showLoading(true);
        
        try {
            const fetchRes = await fetch('/api/fetch-meta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const fetchData = await fetchRes.json();
            
            if (fetchData.success && fetchData.title) {
                title = fetchData.title;
                source_type = 'url';
                
                const titleInput = document.getElementById('title');
                if (titleInput) {
                    titleInput.value = title;
                }
            } else if (fetchData.limit_hit) {
                showLoading(false);
                openModal();
                return;
            } else if (!fetchData.success && fetchData.error) {
                alert(fetchData.error);
                showLoading(false);
                return;
            } else if (!fetchData.title) {
                alert(currentLang === 'zh' ? 'Lazada链接格式不支持自动解析标题，请手动输入商品标题。' : 'Lazada link format does not support automatic title parsing. Please enter product title manually.');
                showLoading(false);
                return;
            }
        } catch (err) {
            showLoading(false);
            alert(currentLang === 'zh' ? '链接解析失败，请手动输入标题' : 'Failed to parse link. Please enter title manually.');
            return;
        }
    }

    showLoading(true);

    try {
        const res = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                token: trialToken || null, 
                title, 
                description, 
                category: productCategory, 
                platform: currentPlatform,
                cost_rm,
                price_rm,
                shipping_fee,
                shipping_cost,
                seller_type,
                cashback_enabled,
                source_type,
                shop_id,
                item_id
            })
        });

        if (!res.ok) {
            showLoading(false);
            alert(currentLang === 'zh' ? '服务器内部错误，请重试' : 'Server error. Please try again.');
            console.error('HTTP error:', res.status);
            return;
        }

        const data = await res.json();

        if (!data.success) {
            showLoading(false);
            if (data.needs_payment || data.error === 'DAILY_LIMIT') {
                showLimitBanner();
                showToast(
                    currentLang === 'zh' 
                        ? `今日免费扫描次数已用完（${data.scan_count_today || 5}/5），请升级或明日再来` 
                        : `Free scans used today (${data.scan_count_today || 5}/5). Upgrade or return tomorrow.`,
                    'warning',
                    [
                        { text: currentLang === 'zh' ? '登录/注册' : 'Login/Sign up', url: '/login#register' },
                        { text: currentLang === 'zh' ? '升级 Pro' : 'Upgrade to Pro', onclick: () => handleUpgradeFromIndex('scan_limit_toast') }
                    ]
                );
                return;
            }
            if (data.error === 'TRIAL_EXPIRED' || data.error === 'TRIAL_NOT_FOUND') {
                alert(currentLang === 'zh' ? '试用已过期，请重新解锁' : 'Trial expired. Please unlock again.');
                clearTrial();
                openModal();
            } else {
                openModal();
            }
            return;
        }

        try {
            data.title = title;
            data.description = description;
            data.product_category = productCategory;
            data.category = productCategory;
            data.lang = currentLang;
            data.cost_rm = cost_rm;
            data.price_rm = price_rm;
            data.shipping_fee = shipping_fee;
            data.shipping_cost = shipping_cost;
            data.seller_type = seller_type;
            data.cashback_enabled = cashback_enabled;
            data.scanned_at = new Date().toLocaleString();
            console.log('[DEBUG] Preparing to store data to sessionStorage, data keys:', Object.keys(data));
            sessionStorage.setItem('complianceReport', JSON.stringify(data));
            console.log('[DEBUG] Data stored successfully, about to redirect to /result');
        } catch (storeErr) {
            console.error('[DEBUG] Failed to store data:', storeErr);
            showLoading(false);
            alert('Scan result processing error: ' + storeErr.message);
            return;
        }

        // P2: Log lazada_scan event when scanning in Lazada mode
        if (currentPlatform === 'lazada') {
            logPlatformEvent('lazada_scan', { risk_level: data.risk_level, score: data.score });
        }
        
        document.getElementById('title').value = '';
        document.getElementById('description').value = '';
        document.getElementById('cost_rm').value = '';
        document.getElementById('price_rm').value = '';
        const sf = document.getElementById('shipping_fee');
        const sc = document.getElementById('shipping_cost');
        if (sf) sf.value = '';
        if (sc) sc.value = '';
        
        window.location.href = '/result';

    } catch (err) {
        showLoading(false);
        alert(currentLang === 'zh' ? '检测失败，请重试' : 'Scan failed. Please try again.');
        console.error(err);
    }
}

// ============ Trial Start ============
// V1.0: 无独立 WA 激活弹窗。点击"升级/试用"统一跳转注册页，注册即激活 14 天 Trial。
async function handleTrialStart(e) {
    if (e) e.preventDefault();
    window.location.href = '/login#register';
}

// ============ Loading ============
function showLoading(show) {
    document.getElementById('scanForm').classList.toggle('hidden', show);
    document.getElementById('loadingState').classList.toggle('hidden', !show);
    const btn = document.getElementById('submitBtn');
    if (btn) {
        btn.textContent = show ? translations[currentLang].scanning : translations[currentLang].startScan;
    }
}

// ============ Result ============
function showResult(data, productInfo) {
    const t = translations[currentLang];

    const reportData = {
        ...data,
        title: productInfo.title,
        description: productInfo.description,
        category: productInfo.category,
        scanned_at: new Date().toLocaleString(),
        summary: generateSummary(data, t),
        high_count: data.violations?.filter(v => v.level === 'high').length || 0,
        medium_count: data.violations?.filter(v => v.level === 'medium').length || 0,
        low_count: data.violations?.filter(v => v.level === 'low').length || 0,
        lang: currentLang
    };
    sessionStorage.setItem('complianceReport', JSON.stringify(reportData));

    window.location.href = '/result';
}

function generateSummary(data, t) {
    if (!data.violations?.length) {
        return t.lowRiskMsg;
    }

    const count = data.violations.length;

    if (data.risk_level === 'HIGH') {
        return `${count} ${t.violationsFound}. ${t.highRiskMsg}`;
    } else if (data.risk_level === 'MEDIUM') {
        return `${count} ${t.violationsFound}. ${t.mediumRiskMsg}`;
    }
    return `${count} ${t.violationsFound}. ${t.lowRiskMsg}`;
}

async function handleUpgradeFromIndex(position) {
    // P2: Log lazada_upgrade_click when upgrading from Lazada mode
    if (currentPlatform === 'lazada') {
        logPlatformEvent('lazada_upgrade_click', { position });
    }
    try {
        await fetch('/api/upgrade-clicked', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_page: 'index', button_position: position })
        });
    } catch (e) {}
    // 差异化跳转：未登录→注册页，已登录→定价页
    const isLoggedIn = document.body.dataset.loggedIn === 'true' || document.cookie.includes('session_token');
    window.location.href = isLoggedIn ? '/pricing/pay' : '/login#register';
}

function closeResultModal() {
    document.getElementById('resultModal').classList.add('hidden');
    document.getElementById('resultModal').classList.remove('flex');
}

// ============ Payment Banner ============
function showPaymentBanner() {
    const t = translations[currentLang];
    let banner = document.getElementById('paymentBanner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'paymentBanner';
        banner.className = 'fixed top-0 left-0 right-0 z-50 bg-red-600 text-white px-4 py-3 shadow-lg';
        banner.innerHTML = `
            <div class="max-w-2xl mx-auto flex items-center justify-between gap-3">
                <div class="flex items-center gap-2">
                    <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <p class="text-sm font-medium">${t.trialExpired} ${t.upgradeNow}</p>
                </div>
                <a href="https://billplz.com/bills/xxx?email=${encodeURIComponent(trialEmail || '')}" target="_blank"
                    class="shrink-0 px-3 py-1.5 bg-white text-red-600 rounded-lg text-xs font-bold hover:bg-gray-100 transition">
                    ${t.upgradeBtn}
                </a>
                <button onclick="document.getElementById('paymentBanner').classList.add('hidden')" class="shrink-0 text-white/70 hover:text-white ml-1">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        `;
        document.body.appendChild(banner);
    } else {
        banner.classList.remove('hidden');
    }
}

// ============ Limit Banner ============
function showLimitBanner() {
    // 达到限额时重置关闭状态，确保用户能看到提示
    localStorage.removeItem('dismissed_limit_banner');

    const limitBanner = document.getElementById('limitBanner');
    const limitBannerContent = document.getElementById('limitBannerContent');
    const limitBannerButtons = document.getElementById('limitBannerButtons');
    const limitBannerWA = document.getElementById('limitBannerWA');
    const limitBannerWADesktop = document.getElementById('limitBannerWADesktop');
    if (!limitBanner || !limitBannerContent) return;

    const t = translations[currentLang];
    const isLoggedIn = trialToken !== null || document.cookie.includes('session_token');
    const waLink = window.WHATSAPP_LINK || 'https://wa.me/60123456789';

    // Update WA links
    if (limitBannerWA) limitBannerWA.href = waLink;
    if (limitBannerWADesktop) limitBannerWADesktop.href = waLink;

    if (!isLoggedIn) {
        // Guest user banner
        const loginBtn = currentLang === 'zh' ? t['scan.limit_banner.login_btn_zh'] : t['scan.limit_banner.login_btn'];
        const signupBtn = currentLang === 'zh' ? t['scan.limit_banner.signup_btn_zh'] : t['scan.limit_banner.signup_btn'];
        const bannerText = currentLang === 'zh' ? t['scan.limit_banner.guest_zh'] : t['scan.limit_banner.guest'];

        limitBannerContent.textContent = bannerText;
        limitBannerButtons.innerHTML = `
            <button onclick="openLoginModal()" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-md transition whitespace-nowrap cursor-pointer">${loginBtn}</button>
            <button onclick="openRegisterModal()" class="px-3 py-1.5 bg-white hover:bg-amber-50 text-amber-800 border border-amber-300 text-sm font-medium rounded-md transition whitespace-nowrap cursor-pointer">${signupBtn}</button>
        `;
    } else {
        // Logged in user banner
        const upgradeBtn = currentLang === 'zh' ? t['scan.limit_banner.upgrade_btn_zh'] : t['scan.limit_banner.upgrade_btn'];
        const bannerText = currentLang === 'zh' ? t['scan.limit_banner.logged_zh'] : t['scan.limit_banner.logged'];

        limitBannerContent.textContent = bannerText;
        limitBannerButtons.innerHTML = `
            <a href="#" onclick="handleUpgradeFromIndex('limit_banner_logged'); return false;" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-md transition whitespace-nowrap text-center">${upgradeBtn}</a>
        `;
    }

    limitBanner.classList.remove('hidden');
}

function dismissLimitBanner() {
    const limitBanner = document.getElementById('limitBanner');
    if (limitBanner) {
        limitBanner.classList.add('hidden');
    }
    localStorage.setItem('dismissed_limit_banner', 'true');
}

function openLoginModal() {
    window.location.href = '/login';
}

function openRegisterModal() {
    window.location.href = '/login#register';
}

// ============ False Positive Modal ============
function openFalsePositiveModal(word) {
    const modal = document.getElementById('falsePositiveModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    document.getElementById('fpReportedWord').value = word;
    document.getElementById('fpReason').value = '';
    document.getElementById('fpEmail').value = '';
}

function closeFalsePositiveModal() {
    const modal = document.getElementById('falsePositiveModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

async function submitFalsePositive() {
    const reported_word = document.getElementById('fpReportedWord').value;
    const reason = document.getElementById('fpReason').value;
    const email = document.getElementById('fpEmail').value.trim();

    if (!reason) {
        alert(currentLang === 'zh' ? '请选择原因' : 'Please select a reason');
        return;
    }

    const body = {
        reported_word: reported_word,
        reason: reason,
        email: email || 'anonymous'  // 如果为空,存储 'anonymous'
    };

    try {
        const res = await fetch('/api/report-false-positive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await res.json();

        if (data.success) {
            alert(data.message);
            closeFalsePositiveModal();
        } else {
            alert('Submission failed: ' + data.message);
        }
    } catch (error) {
        console.error('Submit failed:', error);
        alert(currentLang === 'zh' ? '提交失败,请重试' : 'Submission failed. Please try again.');
    }
}
