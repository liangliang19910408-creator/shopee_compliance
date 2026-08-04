"""
页面路由 - 首页、结果页、登录页、仪表盘
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import WA_LINK

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")


def no_cache_response(content: str) -> HTMLResponse:
    """返回不缓存的 HTML 响应"""
    response = HTMLResponse(content=content)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing 首页"""
    template = templates.get_template("landing.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request):
    """扫描页"""
    template = templates.get_template("index.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)





@router.get("/result", response_class=HTMLResponse)
async def result_page(request: Request):
    """结果页"""
    template = templates.get_template("result.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页"""
    template = templates.get_template("login.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """用户仪表盘"""
    template = templates.get_template("dashboard.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/pricing/pay", response_class=HTMLResponse)
async def pricing_pay_page(request: Request):
    """付费/升级页面"""
    template = templates.get_template("pricing_pay.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    """跨境店选品指南页面（静态聚合页，重定向到带斜杠的目录以正确解析相对资源）"""
    return RedirectResponse(url="/guide/", status_code=302)


@router.get("/guide-native", response_class=HTMLResponse)
async def guide_native_page(request: Request):
    """本土店选品指南页面"""
    template = templates.get_template("guide-native.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """隐私政策页面"""
    template = templates.get_template("privacy.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    """服务条款页面"""
    template = templates.get_template("terms.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)


@router.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    """支付成功页（轮询订阅状态）"""
    template = templates.get_template("success.html")
    content = template.render({"request": request, "wa_link": WA_LINK})
    return no_cache_response(content)
