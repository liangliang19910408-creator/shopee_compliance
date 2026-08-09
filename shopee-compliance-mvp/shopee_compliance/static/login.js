/**
 * Compliance MY - Login / Register Page
 * 支持中英双语切换、Tab 切换、登录/注册、Loading Spinner、错误 Toast
 */

// ============ Translations ============
const translations = {
    en: {
        // Brand
        "brandTitle": "AI Pre-Audit & Profit Intelligence for Shopee & Lazada Sellers.",
        "brandSubtitle": "Pre-audit compliance, calculate profit margins, and scale with confidence.",
        "trust1": "Free 5 scans/day",
        "trust2": "Profit margin calculator",
        "trust3": "14-day Pro trial",

        // Top bar
        "backHome": "Back",

        // Tabs
        "tabLogin": "Login",
        "tabRegister": "Register",

        // Form
        "formTitle": "Welcome back",
        "formSubtitle": "Sign in to access your dashboard.",
        "registerTitle": "Create your account",
        "registerSubtitle": "Start scanning for free. No credit card.",
        "emailLabel": "Email",
        "whatsappLabel": "WhatsApp Number",
        "whatsappHint": "Malaysian number only. +60 prefix will be added automatically.",
        "passwordLabel": "Password",
        "confirmPasswordLabel": "Confirm Password",
        "passwordHint": "Min 8 characters, with letters and numbers",
        "forgotPassword": "Forgot password?",

        // Buttons
        "loginBtn": "Sign In",
        "registerBtn": "Create Account",
        "loading": "Please wait...",

        // Notes
        "freeNote": "Free plan available. No credit card required.",
        "footerDisclaimer": "By signing in, you agree to our Terms of Service and Privacy Policy.",

        // Toast
        "toastInvalid": "Invalid email or password",
        "toastEmpty": "Please enter email and password",
        "toastEmptyWa": "Please enter WhatsApp number",
        "toastInvalidWa": "Please enter a valid Malaysian WhatsApp number (9-11 digits)",
        "toastNetwork": "Network error. Please try again.",
        "toastPasswordMismatch": "Passwords do not match",
        "toastPasswordWeak": "Password must be at least 8 characters with letters and numbers",
        "toastRegisterSuccess": "Registration successful! You now have 14 days free trial.",
        "toastEmailExists": "Email already registered. Please login instead.",
        "toastWaExists": "This WhatsApp number has already been used."
    },
    zh: {
        // Brand
        "brandTitle": "AI预审与利润智能，Shopee & Lazada 卖家上架前必备。",
        "brandSubtitle": "上架前预审合规，铺货前算清利润，安心扩展。",
        "trust1": "免费 5 次扫描/天",
        "trust2": "利润率计算器",
        "trust3": "14 天 Pro 试用",

        // Top bar
        "backHome": "返回",

        // Tabs
        "tabLogin": "登录",
        "tabRegister": "注册",

        // Form
        "formTitle": "欢迎回来",
        "formSubtitle": "登录以访问您的仪表盘。",
        "registerTitle": "创建您的账户",
        "registerSubtitle": "免费开始扫描，无需信用卡。",
        "emailLabel": "邮箱",
        "whatsappLabel": "WhatsApp 号码",
        "whatsappHint": "仅限马来西亚号码，将自动添加 +60 前缀。",
        "passwordLabel": "密码",
        "confirmPasswordLabel": "确认密码",
        "passwordHint": "至少8位，需包含字母和数字",
        "forgotPassword": "忘记密码？",

        // Buttons
        "loginBtn": "登录",
        "registerBtn": "注册",
        "loading": "请稍候...",

        // Notes
        "freeNote": "提供免费版，无需信用卡。",
        "footerDisclaimer": "登录即表示您同意我们的服务条款和隐私政策。",

        // Toast
        "toastInvalid": "邮箱或密码错误",
        "toastEmpty": "请输入邮箱和密码",
        "toastEmptyWa": "请输入 WhatsApp 号码",
        "toastInvalidWa": "请输入有效的马来西亚 WhatsApp 号码（9-11 位数字）",
        "toastNetwork": "网络错误，请重试。",
        "toastPasswordMismatch": "两次密码输入不一致",
        "toastPasswordWeak": "密码至少8位，且需包含字母和数字",
        "toastRegisterSuccess": "注册成功！您已获得 14 天免费试用。",
        "toastEmailExists": "邮箱已注册，请直接登录。",
        "toastWaExists": "此 WhatsApp 号码已被使用。"
    }
};

// ============ State ============
let currentLang = localStorage.getItem("lang") || "en";
let currentTab = "login"; // "login" | "register"
let isSubmitting = false;

// P2-2: Cookie 读取工具函数（用于读取 plg_session_id 进行数据认领）
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// ============ Initialize ============
document.addEventListener("DOMContentLoaded", () => {
    const hash = window.location.hash.toLowerCase();
    if (hash === '#register') {
        switchTab('register');
    } else {
        switchTab('login');
    }

    applyLanguage();
    setupForm();
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

    // Update form header based on tab
    updateFormHeader();
}

function toggleLanguage() {
    currentLang = currentLang === "en" ? "zh" : "en";
    localStorage.setItem("lang", currentLang);
    applyLanguage();
}

// ============ Tab Switching ============
function switchTab(tab) {
    currentTab = tab;
    const tabLogin = document.getElementById("tabLogin");
    const tabRegister = document.getElementById("tabRegister");
    const confirmPasswordRow = document.getElementById("confirmPasswordRow");
    const confirmPasswordInput = document.getElementById("confirmPassword");
    const waRow = document.getElementById("whatsappRow");
    const waInput = document.getElementById("wa_number");
    const forgotRow = document.getElementById("forgotRow");

    if (tab === "login") {
        tabLogin.classList.add("active");
        tabRegister.classList.remove("active");
        if (confirmPasswordRow) confirmPasswordRow.classList.add("hidden");
        if (confirmPasswordInput) confirmPasswordInput.removeAttribute("required");
        if (waRow) waRow.classList.add("hidden");
        if (waInput) waInput.removeAttribute("required");
        if (forgotRow) forgotRow.style.display = "flex";
    } else {
        tabRegister.classList.add("active");
        tabLogin.classList.remove("active");
        if (confirmPasswordRow) confirmPasswordRow.classList.remove("hidden");
        if (confirmPasswordInput) confirmPasswordInput.setAttribute("required", "");
        if (waRow) waRow.classList.remove("hidden");
        if (waInput) waInput.setAttribute("required", "");
        if (forgotRow) forgotRow.style.display = "none";
    }

    updateFormHeader();
}

function updateFormHeader() {
    const t = translations[currentLang];
    const formTitle = document.querySelector('[data-i18n="formTitle"]');
    const formSubtitle = document.querySelector('[data-i18n="formSubtitle"]');
    const submitText = document.getElementById("submitBtnText");

    if (currentTab === "login") {
        formTitle.textContent = t.formTitle;
        formSubtitle.textContent = t.formSubtitle;
        submitText.textContent = t.loginBtn;
        submitText.setAttribute("data-i18n", "loginBtn");
    } else {
        formTitle.textContent = t.registerTitle;
        formSubtitle.textContent = t.registerSubtitle;
        submitText.textContent = t.registerBtn;
        submitText.setAttribute("data-i18n", "registerBtn");
    }
}

// ============ Form Submit ============
function setupForm() {
    const form = document.getElementById("authForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (isSubmitting) return;

        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value;
        const t = translations[currentLang];

        if (!email || !password) {
            showToast(t.toastEmpty);
            return;
        }

        let wa_number = null;

        // 注册时的额外验证
        if (currentTab === "register") {
            const confirmPassword = document.getElementById("confirmPassword")?.value;
            const waRaw = (document.getElementById("wa_number")?.value || "").trim();

            if (!waRaw) {
                showToast(t.toastEmptyWa);
                return;
            }

            // 标准化 WA 号：去除空格、横线、+60 前缀等，仅保留数字
            const digitsOnly = waRaw.replace(/\D/g, "").replace(/^60/, "");
            const waRegex = /^\d{9,11}$/;
            if (!waRegex.test(digitsOnly)) {
                showToast(t.toastInvalidWa);
                return;
            }
            wa_number = "+60" + digitsOnly;

            if (!confirmPassword) {
                showToast(t.toastEmpty);
                return;
            }

            if (password !== confirmPassword) {
                showToast(t.toastPasswordMismatch);
                return;
            }

            // 密码格式校验（≥8位，含字母+数字）
            const passwordRegex = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;
            if (!passwordRegex.test(password)) {
                showToast(t.toastPasswordWeak);
                return;
            }
        }

        setSubmitting(true);

        try {
            const endpoint = currentTab === "login" ? "/api/auth/login" : "/api/auth/register";
            const body = currentTab === "register"
                ? { email, password, wa_number }
                : { email, password };
            const res = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });

            const data = await res.json().catch(() => ({}));

            if (res.ok && (data.success || data.token)) {
                // 注册成功提示
                if (currentTab === "register") {
                    showToast(t.toastRegisterSuccess);
                    // 给用户看到提示的时间
                    await new Promise(resolve => setTimeout(resolve, 1500));
                }

                // P0-2: Fixed field mapping — backend returns email/trial_token, not token/user
                if (data.trial_token) {
                    localStorage.setItem("trial_token", data.trial_token);
                }
                if (data.email) {
                    localStorage.setItem("trial_email", data.email);
                    localStorage.setItem("user_email", data.email);
                }
                if (data.trial_end) {
                    localStorage.setItem("trial_end", data.trial_end);
                }

                // P2-2: If registering, pass session_id for data claiming
                let redirectTo = "/scan";
                if (currentTab === "register") {
                    // Check for session cookie for data claiming
                    const sid = getCookie("plg_session_id");
                    if (sid) {
                        redirectTo = `/dashboard?claimed=${encodeURIComponent(sid)}`;
                    } else {
                        redirectTo = "/dashboard";
                    }
                } else if (data.redirect) {
                    redirectTo = data.redirect;
                }
                window.location.href = redirectTo;
            } else if (res.status === 409) {
                // 邮箱已存在 / WA 号已存在
                const code = data.code;
                if (code === "WA_EXISTS") {
                    showToast(t.toastWaExists);
                } else {
                    showToast(t.toastEmailExists);
                    setTimeout(() => switchTab('login'), 1500);
                }
                setSubmitting(false);
            } else {
                showToast(data.message || t.toastInvalid);
                setSubmitting(false);
            }
        } catch (err) {
            console.error(err);
            showToast(t.toastNetwork);
            setSubmitting(false);
        }
    });
}

function setSubmitting(loading) {
    isSubmitting = loading;
    const btn = document.getElementById("submitBtn");
    const spinner = document.getElementById("submitSpinner");
    const text = document.getElementById("submitBtnText");
    const t = translations[currentLang];

    if (loading) {
        btn.disabled = true;
        spinner.classList.remove("hidden");
        text.textContent = t.loading;
    } else {
        btn.disabled = false;
        spinner.classList.add("hidden");
        text.textContent = currentTab === "login" ? t.loginBtn : t.registerBtn;
    }
}

// ============ Toast ============
let toastTimer = null;
function showToast(message) {
    const toast = document.getElementById("errorToast");
    const text = document.getElementById("toastText");
    if (!toast || !text) return;

    text.textContent = message;
    toast.classList.add("show");

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

// ============ Forgot Password ============
function handleForgot() {
    const t = translations[currentLang];
    const email = document.getElementById("email").value.trim();
    const message = currentLang === "en"
        ? `Password reset link will be sent to ${email || "your email"}.`
        : `密码重置链接将发送到 ${email || "您的邮箱"}。`;

    showToast(message);
}
