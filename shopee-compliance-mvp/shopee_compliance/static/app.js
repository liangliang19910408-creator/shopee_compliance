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
            actionLink.href = action.url;
            actionLink.target = action.target || '_self';
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

// ============ Translations ============
const translations = {
    en: {
        pageTitle: 'Shopee MY Compliance Checker',
        pageSubtitle: 'Detect violations instantly. Avoid penalties & delisting.',
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

        footerPolicy: 'Advisory only. Based on publicly available Shopee MY resources. Not affiliated with Shopee/Lazada.',
        footerDisclaimer: 'Results are advisory only.',
        upgradePro: 'Upgrade to Pro →',

        limitBannerText: 'You have used all 10 free scans today. Upgrade to Pro for unlimited scans.',
        limitBannerBtn: 'Upgrade to Pro – RM29/mo',
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
        upgradeBtn: 'Upgrade to Pro (RM29/month)',

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

        ruleSetLabel: 'Rule Set:',
        platformShopee: 'Shopee MY',
        includeLazadaLabel: 'Include Lazada MY (Additional flags)',
        hygieneTips: 'Readability Tips',
        hygieneTitleLength: 'Title exceeds 128 characters - may be truncated',
        hygieneWordRepeat: 'Repeated word detected - consider rephrasing',
        hygieneAllCaps: 'Excessive uppercase - reduce for readability',

        'scan.form.cost_label': 'Est. Cost (RM)',
        'scan.form.price_label': 'Est. Price (RM)',
        'scan.result.gross_profit': 'Est. Gross Profit: RM{{gp}} ({{margin}}%)',
        'scan.result.margin_note': '💡 Price shown is Shopee listing price, actual may vary.',
        'scan.result.margin_high': 'High Margin',
        'scan.result.margin_medium': 'Medium Margin',
        'scan.result.margin_low': 'Low Margin',
        'scan.placeholder.margin_empty': 'Enter your estimated cost and price above to see gross profit and margin level after scanning.',
        'scan.banner.title': '💰 New: Gross Profit Calculator',
        'scan.banner.body': '🔗 Paste Shopee link → title auto-filled.<br/>✏️ Enter your cost and price.<br/>📊 Instant margin label: 🟢 High / 🟡 Medium / 🔴 Low.',
        'scan.rule_alert.text': '⚠️ Shopee MY updated: stricter monitoring on \'vape\', \'replica\' and similar terms. Review your listings.',

        'scan.limit_banner.guest': '⚠️ Free scans: 3/3 used today. Log in to continue, or sign up for 7-day Pro trial — no credit card needed.',
        'scan.limit_banner.guest_zh': '⚠️ 免费扫描：今日 3/3 已用完。登录继续使用，或注册领 7 天 Pro 试用（无需信用卡）。',
        'scan.limit_banner.logged': '⚠️ Free scans: 3/3 used today. Upgrade to Pro for unlimited scans + batch CSV (200 items), or WhatsApp us.',
        'scan.limit_banner.logged_zh': '⚠️ 免费扫描：今日 3/3 已用完。升级 Pro 享无限扫描 + 批量 CSV（200条），或 WhatsApp 联系。',
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
        trialActivate: 'Activate'
    },
    zh: {
        pageTitle: 'Shopee 合规检测',
        pageSubtitle: '输入商品信息，立即检测违规风险，避免店铺扣分与下架。',
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

        footerPolicy: '仅供参考。基于 Shopee 马来西亚公开卖家资源。与 Shopee/Lazada 无关联。',
        footerDisclaimer: '检测结果仅供参考。',
        upgradePro: '升级到 Pro →',

        limitBannerText: '今日 10 次免费扫描已用完。升级 Pro 享受无限扫描。',
        limitBannerBtn: '升级 Pro – RM29/月',
        limitTitle: '每日扫描次数已用完',
        firstTimeBannerText: '将您的 Shopee 商品链接粘贴到下方开始检测。',

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
        upgradeBtn: '升级到 Pro (RM29/月)',

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

        ruleSetLabel: '规则集：',
        platformShopee: 'Shopee MY',
        includeLazadaLabel: '包含 Lazada MY（附加规则）',
        hygieneTips: '可读性提示',
        hygieneTitleLength: '标题超过128字符 - 可能被截断',
        hygieneWordRepeat: '检测到重复词 - 建议重新表述',
        hygieneAllCaps: '过多大写字母 - 降低以提升可读性',

        'scan.form.cost_label': '预估成本 (RM)',
        'scan.form.price_label': '预估售价 (RM)',
        'scan.result.gross_profit': '预估毛利：RM{{gp}} ({{margin}}%)',
        'scan.result.margin_note': '💡 售价为 Shopee 展示价，实际以订单为准。',
        'scan.result.margin_high': '高毛利',
        'scan.result.margin_medium': '中毛利',
        'scan.result.margin_low': '低毛利',
        'scan.placeholder.margin_empty': '在上方填入预估成本和售价，扫描后即可查看毛利计算结果和利润率等级。',
        'scan.banner.title': '💰 新功能：毛利速算',
        'scan.banner.body': '🔗 贴 Shopee 链接 → 标题自动填入。<br/>✏️ 输入你的成本和售价。<br/>📊 即时利润率标签：🟢高 / 🟡中 / 🔴低。',
        'scan.rule_alert.text': '⚠️ Shopee MY 规则更新：加强对 \'vape\'、\'replica\' 等词的监控，建议检查标题。',

        'scan.limit_banner.guest': '⚠️ 免费扫描：今日 3/3 已用完。登录继续使用，或注册领 7 天 Pro 试用（无需信用卡）。',
        'scan.limit_banner.guest_zh': '⚠️ 免费扫描：今日 3/3 已用完。登录继续使用，或注册领 7 天 Pro 试用（无需信用卡）。',
        'scan.limit_banner.logged': '⚠️ 免费扫描：今日 3/3 已用完。升级 Pro 享无限扫描 + 批量 CSV（200条），或 WhatsApp 联系。',
        'scan.limit_banner.logged_zh': '⚠️ 免费扫描：今日 3/3 已用完。升级 Pro 享无限扫描 + 批量 CSV（200条），或 WhatsApp 联系。',
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
        trialActivate: '激活'
    }
};

// ============ Init ============
document.addEventListener('DOMContentLoaded', async () => {
    await checkLoginStatus();
    await checkScanHistory();
    await checkBatchPermission();

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
            { text: t.batchUpgradeAction, url: '/pricing/pay#pro' },
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

// ============ Check Login Status ============
async function checkLoginStatus() {
    try {
        const res = await fetch('/api/user/info');
        const data = await res.json();
        
        if (data.logged_in) {
            trialToken = getCookie('session_token');
            trialEmail = data.email;

            updateAuthButton(true, data.email);
            showPaidBar(data.email, data.status, data.plan_type, data.paid_until, data.trial_end, data.trial_remaining_days);
        } else {
            trialToken = null;
            trialEmail = null;
            trialEnd = null;
            const bar = document.getElementById('trialBar');
            if (bar) bar.classList.add('hidden');
            updateAuthButton(false);
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

    
    updateText('[data-i18n="ruleSetLabel"]', t.ruleSetLabel);
    updateText('[data-i18n="platformShopee"]', t.platformShopee);
    updateText('[data-i18n="includeLazadaLabel"]', t.includeLazadaLabel);

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

// ============ Modal ============
function openModal() {
    document.getElementById('trialModal').classList.remove('hidden');
    document.getElementById('trialModal').classList.add('flex');
    document.getElementById('modalEmail').focus();
}

function closeModal() {
    document.getElementById('trialModal').classList.add('hidden');
    document.getElementById('trialModal').classList.remove('flex');
    document.getElementById('modalEmail').value = '';
}

// ============ Bind WA Modal ============
function openBindWaModal() {
    document.getElementById('bindWaModal').classList.remove('hidden');
    document.getElementById('bindWaModal').classList.add('flex');
    document.getElementById('waNumberInput').focus();
    document.getElementById('bindWaError').classList.add('hidden');
}

function closeBindWaModal() {
    document.getElementById('bindWaModal').classList.add('hidden');
    document.getElementById('bindWaModal').classList.remove('flex');
    document.getElementById('waNumberInput').value = '';
    document.getElementById('bindWaError').classList.add('hidden');
}

async function handleBindWa() {
    const waNumber = document.getElementById('waNumberInput').value.trim();
    const errorDiv = document.getElementById('bindWaError');
    const t = translations[currentLang];

    if (!waNumber) {
        errorDiv.textContent = 'Please enter your WhatsApp number';
        errorDiv.classList.remove('hidden');
        return;
    }

    try {
        const res = await fetch('/api/bind-wa', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ wa_number: waNumber }),
            credentials: 'include'
        });

        const data = await res.json();

        if (res.ok && data.success) {
            closeBindWaModal();
            showToast(t.trial_modal_success || 'Trial activated! Check your WhatsApp.', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            let errorMsg = data.detail || 'Failed to activate trial';
            if (errorMsg.includes('already been used')) {
                errorMsg = t.trial_error_wa_used || 'This WA number has already been used for trial.';
            }
            errorDiv.textContent = errorMsg;
            errorDiv.classList.remove('hidden');
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please try again.';
        errorDiv.classList.remove('hidden');
    }
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

async function handleScan(e) {
    e.preventDefault();

    let title = document.getElementById('title').value.trim();
    let description = document.getElementById('description').value.trim();
    let source_type = 'text';
    let shop_id = null;
    let item_id = null;

    const productCategory = document.getElementById('productCategory').value || 'general';
    const includeLazada = document.getElementById('includeLazada').checked;
    
    const costInput = document.getElementById('cost_rm');
    const priceInput = document.getElementById('price_rm');
    let cost_rm = costInput && costInput.value ? parseFloat(costInput.value) : null;
    let price_rm = priceInput && priceInput.value ? parseFloat(priceInput.value) : null;

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
                include_lazada: includeLazada,
                cost_rm,
                price_rm,
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

        data.title = title;
        data.description = description;
        data.product_category = productCategory;
        data.category = productCategory;
        data.lang = currentLang;
        data.cost_rm = cost_rm;
        data.price_rm = price_rm;
        data.scanned_at = new Date().toLocaleString();
        sessionStorage.setItem('complianceReport', JSON.stringify(data));
        
        document.getElementById('title').value = '';
        document.getElementById('description').value = '';
        document.getElementById('cost_rm').value = '';
        document.getElementById('price_rm').value = '';
        
        window.location.href = '/result';

    } catch (err) {
        showLoading(false);
        alert(currentLang === 'zh' ? '检测失败，请重试' : 'Scan failed. Please try again.');
        console.error(err);
    }
}

// ============ Trial Start ============
async function handleTrialStart(e) {
    e.preventDefault();

    const email = document.getElementById('modalEmail').value.trim();
    if (!email) return;

    try {
        const res = await fetch('/api/trial/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        const data = await res.json();

        if (data.success) {
            localStorage.setItem('trial_token', data.token);
            localStorage.setItem('trial_email', email);
            localStorage.setItem('trial_end', data.trial_end);
            trialToken = data.token;
            trialEmail = email;
            trialEnd = data.trial_end;

            closeModal();
            showTrialBar(email, 7);

            document.getElementById('scanForm').dispatchEvent(new Event('submit'));
        } else {
            alert(data.message || (currentLang === 'zh' ? '解锁失败，请重试' : 'Unlock failed. Please try again.'));
        }

    } catch (err) {
        alert(currentLang === 'zh' ? '解锁失败，请重试' : 'Unlock failed. Please try again.');
        console.error(err);
    }
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
    try {
        await fetch('/api/upgrade-clicked', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_page: 'index', button_position: position })
        });
    } catch (e) {}
    window.location.href = '/pricing/pay#pro';
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
    const dismissed = localStorage.getItem('dismissed_limit_banner');
    if (dismissed === 'true') {
        return;
    }

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
            <a href="/pricing/#pro" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-md transition whitespace-nowrap text-center">${upgradeBtn}</a>
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
