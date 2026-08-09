"""
批量扫描 API 路由
- 上传 CSV 文件
- 创建批量任务
- 查询任务进度
- 获取扫描结果
"""
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timedelta
import csv
import io
import json
import re

from database import (
    get_db, create_batch_job, get_batch_job, update_batch_job_status,
    save_batch_job_items, update_batch_job_item, get_batch_job_items,
    get_user_batch_jobs, validate_trial,
    create_scan_session, add_scan_result, update_scan_session, get_scan_results,
    get_scan_session
)
from services.scanner import run_scan, calculate_score
from auth import is_pro_user, get_user_tier, get_effective_status
from config import WHITELIST_PATH

router = APIRouter(prefix="/api/batch", tags=["batch"])

# 批量预审分层限制
BATCH_LIMIT_FREE = 3       # Free 用户最多 3 条
BATCH_LIMIT_PRO = 100      # Trial / Pro 用户最多 100 条


async def get_current_user(request: Request):
    """获取当前登录用户"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    return {"trial_token": session_token}


async def process_batch_job(job_id: int, email: str, session_id: int):
    """处理批量扫描任务"""
    print(f"[BATCH PROCESS] Starting job {job_id} for {email}, session_id={session_id}")
    import aiosqlite
    import json
    from config import DATABASE_PATH
    from database import get_user_whitelist
    
    batch_db = None
    try:
        batch_db = await aiosqlite.connect(DATABASE_PATH)
        batch_db.row_factory = aiosqlite.Row
        
        try:
            items = await get_batch_job_items(batch_db, job_id)
            print(f"[BATCH PROCESS] Job {job_id} has {len(items)} items")
        except Exception as e:
            print(f"[BATCH PROCESS ERROR] Failed to get items: {str(e)}")
            raise
        
        global_whitelist = []
        try:
            with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
                global_whitelist = json.load(f)
        except Exception:
            pass
        
        user_whitelist_words = []
        try:
            user_whitelist = await get_user_whitelist(batch_db, email)
            if user_whitelist:
                user_whitelist_words = [w.strip().lower() for w in user_whitelist.split(",") if w.strip()]
        except Exception:
            pass
        
        risk_high = 0
        risk_medium = 0
        risk_low = 0
        total_margin = 0
        processed_count = 0
        
        for i, item in enumerate(items):
            title_to_scan = item["title"]
            
            for w_item in global_whitelist:
                word = w_item.get("word", "")
                if word:
                    title_to_scan = re.sub(re.escape(word), "___WL___", title_to_scan, flags=re.IGNORECASE)
            
            for word in user_whitelist_words:
                title_to_scan = re.sub(re.escape(word), "___WL___", title_to_scan, flags=re.IGNORECASE)
            
            violations, risk_level = run_scan(
                title=title_to_scan,
                description="",
                product_category=item.get("category", "general"),
                platform="shopee"
            )
            
            score = calculate_score(violations)
            
            if risk_level.value == 'HIGH':
                risk_high += 1
            elif risk_level.value == 'MEDIUM':
                risk_medium += 1
            elif risk_level.value == 'LOW':
                risk_low += 1
            
            violations_json = json.dumps([{"word": v.matched_word, "type": v.type.value, "level": v.level.value} for v in violations])
            
            margin_percent = None
            cost_rm = item.get("cost_rm")
            price_rm = item.get("price_rm")
            if cost_rm and price_rm and cost_rm > 0 and price_rm > 0:
                margin_percent = ((price_rm - cost_rm) / price_rm) * 100
                total_margin += margin_percent
            
            await update_batch_job_item(batch_db, item["id"], {
                "risk_level": risk_level.value.lower(),
                "violations": violations_json,
                "score": score
            })
            
            print(f"[BATCH PROCESS] Adding scan result for item {i+1}: title={item['title']}, session_id={session_id}")
            await add_scan_result(
                batch_db, session_id, item["title"],
                risk_level.value, cost_rm, price_rm, margin_percent, violations_json
            )
            
            await update_batch_job_status(batch_db, job_id, "processing", i + 1)
            processed_count = i + 1

        avg_margin = total_margin / len(items) if len(items) > 0 else 0
        print(f"[BATCH PROCESS] Job {job_id} completed. Processed {len(items)} items")
        await update_batch_job_status(batch_db, job_id, "completed", len(items))
        
        await update_scan_session(
            batch_db, session_id,
            status='done',
            total_count=len(items),
            risk_high=risk_high,
            risk_medium=risk_medium,
            risk_low=risk_low,
            avg_margin=avg_margin
        )
    except Exception as e:
        import traceback
        print(f"[BATCH ERROR] Job {job_id} failed: {str(e)}")
        print(f"[BATCH ERROR] Traceback: {traceback.format_exc()}")
        if batch_db:
            try:
                await update_batch_job_status(batch_db, job_id, "failed")
                if session_id:
                    try:
                        await update_scan_session(batch_db, session_id, status='partial')
                    except:
                        pass
            except:
                pass
    finally:
        if batch_db:
            await batch_db.close()


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db=Depends(get_db),
    user=Depends(get_current_user)
):
    """
    上传 CSV 文件并创建批量任务
    
    权限控制：仅 Pro 用户或有效试用用户可用
    """
    print(f"[BATCH UPLOAD] Called with user: {user}")
    
    if not user:
        print("[BATCH UPLOAD ERROR] No user found (no session_token cookie)")
        raise HTTPException(
            status_code=401,
            detail="Please log in to use batch scan"
        )

    is_valid, user_data = await validate_trial(db, user["trial_token"])
    print(f"[BATCH UPLOAD] validate_trial result: is_valid={is_valid}, user_data={user_data}")
    
    if not is_valid:
        print("[BATCH UPLOAD ERROR] Trial validation failed")
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid"
        )
    
    # 使用统一层级判断（实时处理 Trial 过期降级）
    tier = get_user_tier(user_data)
    print(f"[BATCH UPLOAD] User tier: {tier}, effective_status: {get_effective_status(user_data)}")
    
    # 根据层级确定批量扫描上限
    if tier == "free":
        batch_limit = BATCH_LIMIT_FREE
    else:
        batch_limit = BATCH_LIMIT_PRO

    if not file.filename.endswith('.csv'):
        print(f"[BATCH UPLOAD ERROR] File not CSV: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed"
        )

    try:
        content = await file.read()
        decoded = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        
        print(f"[BATCH UPLOAD] CSV fieldnames: {reader.fieldnames}")
        
        required_fields = {'title'}
        if not required_fields.issubset(reader.fieldnames):
            print(f"[BATCH UPLOAD ERROR] Missing required fields. Need: {required_fields}, Got: {reader.fieldnames}")
            raise HTTPException(
                status_code=400,
                detail="CSV must contain 'title' column"
            )

        items = []
        for row_num, row in enumerate(reader, start=2):
            title = row.get('title', '').strip()
            if not title:
                continue
            cost_rm = None
            price_rm = None
            try:
                cost_rm = float(row.get('cost_rm', 0) or 0)
            except:
                cost_rm = None
            try:
                price_rm = float(row.get('price_rm', 0) or 0)
            except:
                price_rm = None
            items.append({
                'row_num': row_num,
                'title': title,
                'url': row.get('url', '').strip(),
                'category': row.get('category', '').strip(),
                'cost_rm': cost_rm,
                'price_rm': price_rm
            })

        if len(items) > batch_limit:
            print(f"[BATCH UPLOAD ERROR] Too many items: {len(items)} > {batch_limit} (tier={tier})")
            raise HTTPException(
                status_code=400,
                detail={"error": "batch_limit_exceeded", "max": batch_limit, "tier": tier,
                        "message": f"Maximum {batch_limit} rows allowed for {tier} users"}
            )

        if len(items) == 0:
            print("[BATCH UPLOAD ERROR] No valid items")
            raise HTTPException(
                status_code=400,
                detail="No valid data found in CSV"
            )

        job_id = await create_batch_job(db, user_data["email"], file.filename, len(items))
        await save_batch_job_items(db, job_id, items)
        print(f"[BATCH UPLOAD SUCCESS] Created job {job_id} with {len(items)} items for {user_data['email']}")

        await update_batch_job_status(db, job_id, "processing", 0)
        
        email = user_data["email"]
        session_id = await create_scan_session(db, email, 'batch')

        import asyncio
        asyncio.create_task(process_batch_job(job_id, email, session_id))

        return {"success": True, "job_id": job_id, "total_items": len(items),
                "tier": tier, "batch_limit": batch_limit}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[BATCH UPLOAD EXCEPTION] {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process CSV: {str(e)}"
        )


@router.get("/job/{job_id}")
async def get_job_status(job_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """获取批量任务状态"""
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")

    job = await get_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_valid, user_data = await validate_trial(db, user["trial_token"])
    if not is_valid or job["email"] != user_data["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "job_id": job["id"],
        "status": job["status"],
        "total_items": job["total_items"],
        "processed_items": job["processed_items"],
        "progress": round((job["processed_items"] / job["total_items"]) * 100) if job["total_items"] > 0 else 0,
        "created_at": job["created_at"],
        "updated_at": job["updated_at"]
    }


@router.get("/job/{job_id}/results")
async def get_job_results(job_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """获取批量任务扫描结果"""
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")

    job = await get_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_valid, user_data = await validate_trial(db, user["trial_token"])
    if not is_valid or job["email"] != user_data["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    items = await get_batch_job_items(db, job_id)
    
    high_count = sum(1 for item in items if item.get('risk_level') == 'high')
    medium_count = sum(1 for item in items if item.get('risk_level') == 'medium')
    low_count = sum(1 for item in items if item.get('risk_level') == 'low')
    safe_count = sum(1 for item in items if item.get('risk_level') == 'safe' or not item.get('risk_level'))

    return {
        "job_id": job_id,
        "status": job["status"],
        "summary": {
            "total": len(items),
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "safe": safe_count
        },
        "items": items
    }


@router.post("/job/{job_id}/start")
async def start_batch_scan(job_id: int, db=Depends(get_db), user=Depends(get_current_user), background_tasks: BackgroundTasks = None):
    """启动批量扫描任务"""
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")

    job = await get_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_valid, user_data = await validate_trial(db, user["trial_token"])
    if not is_valid or job["email"] != user_data["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if job["status"] != "pending":
        raise HTTPException(status_code=400, detail="Job is not in pending state")

    await update_batch_job_status(db, job_id, "processing", 0)

    email = user_data["email"]
    session_id = await create_scan_session(db, email, 'batch')

    background_tasks.add_task(process_batch_job, job_id, email, session_id)

    return {"success": True, "message": "Batch scan started"}


@router.get("/download-template")
async def download_template():
    """下载 CSV 模板"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['title', 'url', 'category', 'cost_rm', 'price_rm'])
    writer.writerow(['New Wireless Bluetooth Earphone', 'https://shopee.com.my/product/123', 'electronics', '15.00', '39.90'])
    writer.writerow(['Premium Skin Care Serum', '', 'beauty', '8.50', '25.00'])
    
    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=batch_scan_template.csv"}
    )
    return response


@router.get("/session/{session_id}")
async def get_batch_session(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """获取批量扫描会话详情和结果"""
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")

    session = await get_scan_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    is_valid, user_data = await validate_trial(db, user["trial_token"])
    if not is_valid or session["user_id"] != user_data["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    results = await get_scan_results(db, session_id)

    return {
        "session": session,
        "results": results
    }


@router.get("/session/{session_id}/export")
async def export_batch_session(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """导出批量扫描会话结果为 CSV"""
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")

    session = await get_scan_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    is_valid, user_data = await validate_trial(db, user["trial_token"])
    if not is_valid or session["user_id"] != user_data["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    results = await get_scan_results(db, session_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Title', 'Platform', 'Risk Level (风险等级)', 'Violations (违规词)',
        'Cost(RM)', 'Price(RM)', 'Gross Profit(RM) (毛利)', 'Margin(利润率%)', 'Scanned At'
    ])

    for item in results:
        violations = item.get('violations', '')
        if isinstance(violations, str):
            try:
                violations = json.loads(violations)
            except:
                violations = []

        violations_formatted = []
        for v in violations:
            v_type = v.get('type', 'banned_word')
            type_label = "banned" if v_type == "banned_word" else "category"
            violations_formatted.append(f"{v.get('matched_word', v.get('word', ''))} ({type_label})")
        violations_str = ", ".join(violations_formatted)

        scan_time = item.get('scanned_at', '')
        if scan_time:
            try:
                scan_dt = datetime.fromisoformat(scan_time.replace('Z', '+00:00'))
                scan_dt = scan_dt + timedelta(hours=8)
                scan_time_str = scan_dt.strftime('%Y-%m-%d %H:%M')
            except:
                scan_time_str = scan_time[:16].replace('T', ' ') if scan_time else ''
        else:
            scan_time_str = ''

        writer.writerow([
            item.get('title', ''),
            item.get('platform', 'Shopee'),
            item.get('risk', ''),
            violations_str,
            item.get('cost_rm', '') if item.get('cost_rm') else '',
            item.get('price_rm', '') if item.get('price_rm') else '',
            round(item.get('price_rm', 0) - item.get('cost_rm', 0), 2) if item.get('cost_rm') and item.get('price_rm') else '',
            item.get('margin', '') if item.get('margin') else '',
            scan_time_str
        ])

    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batch_session_{session_id}.csv"}
    )
    return response


@router.get("/job/{job_id}/download-results")
async def download_results(job_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """下载批量扫描结果 CSV"""
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")

    job = await get_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_valid, user_data = await validate_trial(db, user["trial_token"])
    if not is_valid or job["email"] != user_data["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    items = await get_batch_job_items(db, job_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Platform', 'Risk Level (风险等级)', 'Violations (违规词)', 'Cost(RM)', 'Price(RM)', 'Gross Profit(RM) (毛利)', 'Margin(利润率%)', 'Scanned At'])
    
    for item in items:
        violations = item.get('violations', [])
        if isinstance(violations, str):
            try:
                violations = json.loads(violations)
            except:
                violations = []
        
        violations_formatted = []
        for v in violations:
            v_type = v.get('type', 'banned_word')
            type_label = "banned" if v_type == "banned_word" else "category"
            violations_formatted.append(f"{v.get('matched_word', v.get('word', ''))} ({type_label})")
        violations_str = ", ".join(violations_formatted)
        
        risk_level = item.get('risk_level', 'safe')
        risk_level_upper = risk_level.upper() if risk_level else "SAFE"
        
        scan_time = job.get('created_at', '')
        if scan_time:
            try:
                scan_dt = datetime.fromisoformat(scan_time.replace('Z', '+00:00'))
                scan_dt = scan_dt + timedelta(hours=8)
                scan_time_str = scan_dt.strftime('%Y-%m-%d %H:%M')
            except:
                scan_time_str = scan_time[:16].replace('T', ' ')
        else:
            scan_time_str = ''
        
        cost_rm = item.get('cost_rm')
        price_rm = item.get('price_rm')
        gross_profit = ''
        if cost_rm and price_rm:
            try:
                gross_profit = round(float(price_rm) - float(cost_rm), 2)
            except:
                gross_profit = ''
        
        writer.writerow([
            item.get('title', ''),
            'Shopee',
            risk_level_upper,
            violations_str,
            cost_rm if cost_rm else '',
            price_rm if price_rm else '',
            gross_profit,
            '',
            scan_time_str
        ])

    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batch_results_{job_id}.csv"}
    )
    return response
