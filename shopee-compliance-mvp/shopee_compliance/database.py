"""
SQLite 数据库初始化与操作 (aiosqlite)
支持 trial / paid / login / scan_history

注意：SQLite 不支持 MySQL 风格的 COMMENT 属性，字段注释通过 SQL 注释(--) 添加。
要在数据库工具中看到注释，需要删除旧表重新创建，新的 CREATE TABLE 语句会被存储在 sqlite_master 中。
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional
import uuid
import os

from config import DATABASE_PATH


async def migrate_db():
    """
    数据库迁移：删除旧表并重新创建，保留数据
    用于更新表结构和字段注释
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. 备份 trials 表数据
        cursor = await db.execute("SELECT * FROM trials")
        trials_data = await cursor.fetchall()
        
        # 2. 备份其他表数据
        tables_to_backup = ['login_tokens', 'scan_history', 'false_positives', 'event_logs', 'reactivation_logs']
        backup_data = {}
        for table in tables_to_backup:
            try:
                cursor = await db.execute(f"SELECT * FROM {table}")
                backup_data[table] = await cursor.fetchall()
            except:
                backup_data[table] = []
        
        # 3. 删除旧表
        await db.execute("DROP TABLE IF EXISTS trials")
        await db.execute("DROP TABLE IF EXISTS login_tokens")
        await db.execute("DROP TABLE IF EXISTS scan_history")
        await db.execute("DROP TABLE IF EXISTS false_positives")
        await db.execute("DROP TABLE IF EXISTS event_logs")
        await db.execute("DROP TABLE IF EXISTS reactivation_logs")
        await db.commit()
        
        # 4. 重新创建表（带注释）
        await init_db_tables(db)
        
        # 5. 迁移 trials 数据
        for row in trials_data:
            row_dict = dict(row)
            await db.execute("""
                INSERT INTO trials (
                    email, trial_token, trial_start, trial_end, scan_count, status,
                    paid_until, plan_type, last_shared_at, trial_status, subscription_status,
                    url_parse_count_today, last_url_parse_date, upgrade_pending_since,
                    billplz_bill_id, ip_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row_dict.get('email', ''),
                row_dict.get('trial_token', ''),
                row_dict.get('trial_start', ''),
                row_dict.get('trial_end', ''),
                row_dict.get('scan_count', 0),
                row_dict.get('status', 'trial'),
                row_dict.get('paid_until'),
                row_dict.get('plan_type'),
                row_dict.get('last_shared_at'),
                row_dict.get('trial_status', 'active'),
                row_dict.get('subscription_status', 'inactive'),
                row_dict.get('url_parse_count_today', 0),
                row_dict.get('last_url_parse_date'),
                row_dict.get('upgrade_pending_since'),
                row_dict.get('billplz_bill_id'),
                row_dict.get('ip_address')
            ))
        
        # 6. 迁移其他表数据
        for table, rows in backup_data.items():
            for row in rows:
                row_dict = dict(row)
                if table == 'login_tokens':
                    await db.execute("""
                        INSERT INTO login_tokens (id, email, token_uuid, expires_at, used_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (row_dict.get('id'), row_dict.get('email'), row_dict.get('token_uuid'),
                          row_dict.get('expires_at'), row_dict.get('used_at')))
                elif table == 'scan_history':
                    await db.execute("""
                        INSERT INTO scan_history (id, email, scan_time, source_type, title_snippet,
                            risk_level, score, raw_result_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (row_dict.get('id'), row_dict.get('email'), row_dict.get('scan_time'),
                          row_dict.get('source_type'), row_dict.get('title_snippet'),
                          row_dict.get('risk_level'), row_dict.get('score'), row_dict.get('raw_result_json')))
                elif table == 'false_positives':
                    await db.execute("""
                        INSERT INTO false_positives (id, email, reported_word, reason, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (row_dict.get('id'), row_dict.get('email'), row_dict.get('reported_word'),
                          row_dict.get('reason'), row_dict.get('status'), row_dict.get('created_at')))
                elif table == 'event_logs':
                    await db.execute("""
                        INSERT INTO event_logs (id, event_name, event_data, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (row_dict.get('id'), row_dict.get('event_name'), row_dict.get('event_data'),
                          row_dict.get('created_at')))
                elif table == 'reactivation_logs':
                    await db.execute("""
                        INSERT INTO reactivation_logs (id, email, sent_at)
                        VALUES (?, ?, ?)
                    """, (row_dict.get('id'), row_dict.get('email'), row_dict.get('sent_at')))
        
        await db.commit()
        print("[DB MIGRATION] 数据库迁移完成，表结构已更新")


async def init_db_tables(db):
    """创建所有数据库表（带中文注释）"""
    # 1. trials 表 — 用户试用/付费记录，email 为主键
    await db.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            email TEXT PRIMARY KEY,                    -- 用户邮箱（主键）
            trial_token TEXT UNIQUE NOT NULL,          -- 试用Token（唯一标识）
            trial_start TEXT NOT NULL,                 -- 试用开始时间
            trial_end TEXT NOT NULL,                   -- 试用结束时间
            scan_count INTEGER DEFAULT 0,              -- 总扫描次数
            status TEXT DEFAULT 'free',                -- 用户状态：free/trial/paid/trial_expired/cancelled
            paid_until TEXT,                           -- 付费到期时间
            plan_type TEXT,                            -- 套餐类型
            last_shared_at TEXT,                       -- 上次分享时间（用于限制分享频率）
            trial_status TEXT DEFAULT 'active',        -- 试用状态：active
            subscription_status TEXT DEFAULT 'inactive', -- 订阅状态：inactive/active
            url_parse_count_today INTEGER DEFAULT 0,   -- 今日URL解析次数（每日50次限制）
            last_url_parse_date TEXT,                  -- 上次URL解析日期（用于每日重置）
            scan_count_today INTEGER DEFAULT 0,        -- 今日扫描次数（每日10次限制）
            last_scan_date TEXT,                       -- 上次扫描日期（用于每日重置）
            upgrade_pending_since TEXT,                -- 升级意向时间（用户点击升级按钮的时间）
            billplz_bill_id TEXT,                      -- Billplz账单ID（关联支付记录）
            ip_address TEXT,                           -- 用户IP地址（用于匿名用户追踪）
            whitelist_words TEXT,                      -- 用户白名单词（逗号分隔）
            password_hash TEXT,                        -- 密码哈希（bcrypt，NULL表示未设置密码）
            wa_number TEXT,                            -- WhatsApp号码（E.164格式，如+60123456789）
            trial_activated_at TEXT,                   -- Trial激活时间（绑WA时间）
            trial_activated_wa TEXT,                   -- 激活Trial时使用的WA号（用于防刷验证）
            email_verified INTEGER DEFAULT 0,          -- 邮箱验证状态（0=未验证, 1=已验证，预留字段）
            registered_ip TEXT,                        -- 注册时IP地址（用于注册限流）
            is_admin INTEGER DEFAULT 0,                -- 管理员标记（0=普通用户, 1=管理员）
            paid_at TEXT                               -- 付费时间（用于统计今日付费转化）
        )
    """)

    # 2. 登录 Token 表（Magic Link 登录）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS login_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            email TEXT NOT NULL,                      -- 用户邮箱
            token_uuid TEXT UNIQUE NOT NULL,          -- 登录Token（唯一）
            expires_at TEXT NOT NULL,                 -- Token过期时间
            used_at TEXT                              -- Token使用时间（标记已使用）
        )
    """)

    # 3. 扫描历史表（记录用户每次扫描结果）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            email TEXT NOT NULL,                      -- 用户邮箱
            scan_time TEXT DEFAULT CURRENT_TIMESTAMP, -- 扫描时间
            source_type TEXT DEFAULT 'text',          -- 来源类型：text(粘贴标题)/url(链接解析)
            title_snippet TEXT,                       -- 标题片段
            risk_level TEXT,                          -- 风险等级：HIGH/MEDIUM/LOW
            score INTEGER DEFAULT 100,                -- 合规评分
            raw_result_json TEXT,                     -- 完整扫描结果JSON
            generated_safe_title TEXT,                -- 生成的安全标题
            platform TEXT DEFAULT 'shopee'            -- 平台：shopee/lazada
        )
    """)

    # 4. 误报申诉表（用户报告误报词，后台手动审核）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS false_positives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            email TEXT,                               -- 用户邮箱（匿名用户为anonymous）
            reported_word TEXT,                       -- 用户认为是误报的词语
            reason TEXT,                              -- 误报原因说明
            status TEXT DEFAULT 'pending',            -- 状态：pending(待审核)/approved(已通过)/rejected(已拒绝)
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
        )
    """)

    # 5. 埋点事件日志表（记录用户行为数据）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            event_name TEXT NOT NULL,                 -- 事件名称：scan_completed/email_captured/safe_title_copied等
            event_data TEXT,                          -- 事件数据（JSON格式）
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
        )
    """)

    # 6. 试用召回日志表（记录已发送召回邮件的用户，防止重复打扰）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS reactivation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            email TEXT NOT NULL,                      -- 用户邮箱
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP    -- 召回邮件发送时间
        )
    """)

    # 7. 批量任务主表（记录整体状态）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS batch_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            email TEXT NOT NULL,                      -- 用户邮箱
            filename VARCHAR(255),                    -- 上传文件名
            status VARCHAR(20) DEFAULT 'pending',    -- 任务状态：pending/processing/completed/failed
            total_items INT DEFAULT 0,               -- 总条数
            processed_items INT DEFAULT 0,           -- 已处理条数
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, -- 创建时间
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP  -- 更新时间
        )
    """)

    # 8. 批量任务明细表（记录每一条数据的扫描结果）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS batch_job_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            job_id INT NOT NULL,                     -- 关联的任务ID
            row_num INT,                             -- CSV行号
            title TEXT,                              -- 商品标题
            url TEXT,                                -- 商品链接
            category TEXT,                           -- 商品类目
            cost_rm REAL,                            -- 成本价 (RM)
            price_rm REAL,                           -- 售价 (RM)
            risk_level VARCHAR(10),                  -- 风险等级：high/medium/low/safe
            violations TEXT,                         -- 违规详情（JSON数组）
            score INT DEFAULT 100,                   -- 合规评分
            status VARCHAR(10) DEFAULT 'pending'     -- 处理状态：pending/success/error
        )
    """)

    # 9. 扫描会话表（记录扫描会话，单条和批量共用）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS scan_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            user_id TEXT NOT NULL,                   -- 用户标识（email或trial_token）
            mode VARCHAR(10) NOT NULL,               -- 模式：single/batch
            total_count INT DEFAULT 0,               -- 总条数（单条为1）
            risk_high INT DEFAULT 0,                 -- 高风险数量
            risk_medium INT DEFAULT 0,               -- 中风险数量
            risk_low INT DEFAULT 0,                  -- 低风险数量
            avg_margin REAL,                         -- 平均利润率
            status VARCHAR(20) DEFAULT 'processing', -- 状态：processing/done/failed/partial
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
        )
    """)

    # 10. 扫描结果表（记录每条扫描结果，关联会话）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            session_id INT,                          -- 关联会话ID（可为NULL）
            platform VARCHAR(20) DEFAULT 'Shopee',   -- 平台
            title TEXT,                              -- 商品标题
            description TEXT,                        -- 商品描述
            risk VARCHAR(10),                        -- 风险等级：HIGH/MEDIUM/LOW/SAFE
            cost_rm REAL,                            -- 成本价 (RM)
            price_rm REAL,                           -- 售价 (RM)
            margin REAL,                             -- 利润率
            violations TEXT,                         -- 违规详情（JSON数组）
            scanned_at TEXT DEFAULT CURRENT_TIMESTAMP -- 扫描时间
        )
    """)

    # IntelliAudit 2.0: 机会评分历史表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS opportunity_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            score INTEGER,
            score_level TEXT,
            compliance_score INTEGER,
            profit_score INTEGER,
            competition_score INTEGER,
            risk_score INTEGER,
            profit_margin REAL,
            net_profit REAL,
            gate_passed INTEGER DEFAULT 1,
            gate_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_opp_scores_user_created
        ON opportunity_scores(user_id, created_at DESC)
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_opp_scores_session
        ON opportunity_scores(session_id)
    """)

    # wa_number 唯一索引（仅非NULL值，防止并发注册重复绑定）
    await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trials_wa_number 
        ON trials(wa_number) WHERE wa_number IS NOT NULL AND wa_number != ''
    """)

    # 为 scan_results 添加索引（批量扫描时一个session_id对应多条记录）
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_scan_results_session_id 
        ON scan_results(session_id)
    """)

    # Admin 1.0: 用户反馈表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            email TEXT NOT NULL,                      -- 提交反馈的用户邮箱
            content TEXT NOT NULL,                    -- 反馈内容
            status TEXT DEFAULT 'pending',            -- 状态：pending(未处理) / adopted(已采纳) / dismissed(已忽略)
            reward_days INTEGER DEFAULT 0,            -- 奖励天数（0=未奖励, 7=奖励7天Pro）
            rewarded_at TEXT,                         -- 奖励时间
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 提交时间
        )
    """)

    # Admin 1.0: 系统全局开关表（键值对，用于支付熔断等）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS system_flags (
            key TEXT PRIMARY KEY,                     -- 开关名称（如 payment_disabled）
            value TEXT DEFAULT '0',                   -- 开关值（'0'=关闭, '1'=开启）
            reason TEXT,                              -- 操作原因
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP -- 更新时间
        )
    """)

    # Admin 1.0: 管理员操作日志表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            admin_email TEXT NOT NULL,                -- 操作管理员邮箱
            action TEXT NOT NULL,                     -- 操作类型（adopt_feedback / toggle_payment 等）
            target TEXT,                              -- 操作目标（如反馈ID）
            detail TEXT,                              -- 操作详情（JSON）
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 操作时间
        )
    """)

    # P0-4: PLG 会话缓存表 — 存储未登录用户的扫描结果，支持刷新恢复和数据认领
    await db.execute("""
        CREATE TABLE IF NOT EXISTS session_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键
            session_id TEXT NOT NULL,                 -- 会话ID（UUID，通过Cookie传递）
            scan_data TEXT NOT NULL,                  -- 完整扫描结果JSON
            scan_timestamp TEXT NOT NULL,             -- 扫描时间（ISO格式）
            source_type TEXT DEFAULT 'text',          -- 来源类型：text/url
            title_snippet TEXT,                       -- 标题片段（用于快速预览）
            risk_level TEXT,                          -- 风险等级：HIGH/MEDIUM/LOW
            score INTEGER DEFAULT 100,                -- 合规评分
            claimed_by TEXT,                          -- 认领者邮箱（NULL=未认领）
            claimed_at TEXT,                          -- 认领时间
            ip_address TEXT,                          -- 扫描时IP地址
            platform TEXT DEFAULT 'shopee',           -- 平台：shopee/lazada
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
        )
    """)

    # P0-4: 为 session_cache 创建索引
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_cache_session_id
        ON session_cache(session_id)
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_cache_created_at
        ON session_cache(created_at)
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_cache_claimed_by
        ON session_cache(claimed_by)
    """)

    # IntelliAudit 2.0 Pro: 用户偏好配置表（单行 JSON 存储）
    # JSON 结构:
    # {
    #   "platforms": {
    #     "shopee": {shipping_fee, shipping_cost, default_category, cashback, seller_type, target_profit_margin, min_profit_threshold},
    #     "lazada": {...}
    #   },
    #   "global": {default_currency, locked_exchange_rate, default_cost, suppliers:[{name, category, cost}]}
    # }
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            email TEXT PRIMARY KEY,                     -- 用户邮箱（主键，关联 trials.email）
            preferences_json TEXT NOT NULL DEFAULT '{}', -- 偏好配置（JSON 字符串）
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP   -- 最后更新时间
        )
    """)


async def init_db():
    """初始化数据库表"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await init_db_tables(db)
        
        # 迁移：为已存在的表添加缺失字段
        try:
            await db.execute("ALTER TABLE scan_results ADD COLUMN cost_rm REAL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE scan_results ADD COLUMN price_rm REAL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE scan_results ADD COLUMN margin REAL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE scan_results ADD COLUMN description TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE batch_job_items ADD COLUMN cost_rm REAL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE batch_job_items ADD COLUMN price_rm REAL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE scan_history ADD COLUMN shop_id TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE scan_history ADD COLUMN item_id TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE scan_results ADD COLUMN shop_id TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE scan_results ADD COLUMN item_id TEXT")
        except:
            pass
        
        try:
            await db.execute("ALTER TABLE trials ADD COLUMN margin_count_today INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE trials ADD COLUMN last_margin_date TEXT")
        except:
            pass
        
        # IntelliAudit 2.0: 新增字段迁移
        try:
            await db.execute("ALTER TABLE trials ADD COLUMN email_verified INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE trials ADD COLUMN registered_ip TEXT")
        except:
            pass
        
        # Admin 1.0: 新增字段迁移
        try:
            await db.execute("ALTER TABLE trials ADD COLUMN is_admin INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE trials ADD COLUMN paid_at TEXT")
        except:
            pass
        
        # Admin 1.0: 初始化默认管理员（需手动设置邮箱）
        try:
            # 设置第一个管理员（部署时修改此邮箱）
            await db.execute("""
                UPDATE trials SET is_admin = 1 WHERE email = 'admin@compliancemy.com'
            """)
        except:
            pass
        
        # Admin 1.0: 初始化支付开关为正常状态
        try:
            await db.execute("""
                INSERT OR IGNORE INTO system_flags (key, value, reason) 
                VALUES ('payment_disabled', '0', 'init')
            """)
        except:
            pass
        
        # wa_number 唯一索引（仅非NULL值，防止并发注册重复绑定）
        try:
            await db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_trials_wa_number 
                ON trials(wa_number) WHERE wa_number IS NOT NULL AND wa_number != ''
            """)
        except Exception as e:
            print(f"[DB MIGRATION] wa_number unique index: {e}")
        
        # 为 scan_results 添加索引（批量扫描时一个session_id对应多条记录）
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_scan_results_session_id ON scan_results(session_id)")
        except Exception as e:
            print(f"Error creating index: {e}")
        
        # P0-4: scan_history 表扩展 — 添加 session_id 字段（关联 PLG 会话）
        try:
            await db.execute("ALTER TABLE scan_history ADD COLUMN session_id TEXT")
        except:
            pass

        # P2: Lazada 双平台支持 — 添加 platform 字段
        try:
            await db.execute("ALTER TABLE scan_history ADD COLUMN platform TEXT DEFAULT 'shopee'")
        except:
            pass
        try:
            await db.execute("ALTER TABLE session_cache ADD COLUMN platform TEXT DEFAULT 'shopee'")
        except:
            pass
        
        await db.commit()


async def get_db():
    """获取数据库连接的依赖"""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# ============ Trials 操作（email 为主键）===========

async def create_trial(db: aiosqlite.Connection, email: str) -> dict:
    """创建试用记录（status='trial'）"""
    now = datetime.utcnow()
    trial_end = now + timedelta(days=7)

    existing = await get_trial_by_email(db, email)
    if existing:
        existing_end = datetime.fromisoformat(existing["trial_end"])
        if existing_end > now and existing["status"] in ("trial", "paid"):
            return existing

    trial_token = str(uuid.uuid4())

    await db.execute("""
        INSERT OR REPLACE INTO trials
        (email, trial_token, trial_start, trial_end, scan_count, status, paid_until, plan_type)
        VALUES (?, ?, ?, ?, COALESCE((SELECT scan_count FROM trials WHERE email=?), 0), 'trial', NULL, NULL)
    """, (email, trial_token, now.isoformat(), trial_end.isoformat(), email))
    await db.commit()

    return {
        "trial_token": trial_token,
        "trial_end": trial_end.isoformat(),
        "email": email,
        "status": "trial"
    }


async def get_trial_by_token(db: aiosqlite.Connection, token: str) -> Optional[dict]:
    """根据 token 获取试用记录"""
    cursor = await db.execute("SELECT * FROM trials WHERE trial_token = ?", (token,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_trial_by_email(db: aiosqlite.Connection, email: str) -> Optional[dict]:
    """根据邮箱获取试用记录（email 是主键）"""
    cursor = await db.execute("SELECT * FROM trials WHERE email = ?", (email,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def check_wa_used(db: aiosqlite.Connection, wa_number: str) -> bool:
    """检查 WA 号是否已用于激活 Trial（该 WA 号绑定过的账号曾试用过）"""
    cursor = await db.execute("""
        SELECT * FROM trials 
        WHERE trial_activated_wa = ?
    """, (wa_number,))
    row = await cursor.fetchone()
    return row is not None


async def check_email_activated_trial(db: aiosqlite.Connection, email: str) -> bool:
    """检查账户是否曾经激活过试用"""
    cursor = await db.execute("""
        SELECT * FROM trials 
        WHERE email = ? AND trial_activated_at IS NOT NULL
    """, (email,))
    row = await cursor.fetchone()
    return row is not None


async def bind_wa_and_activate_trial(db: aiosqlite.Connection, email: str, wa_number: str) -> bool:
    """绑定 WA 号并激活 Trial（14天有效期）"""
    now = datetime.utcnow()
    trial_end = now + timedelta(days=14)
    
    await db.execute("""
        UPDATE trials 
        SET wa_number = ?, 
            status = 'trial', 
            trial_status = 'active',
            trial_end = ?, 
            trial_start = ?,
            trial_activated_at = ?,
            trial_activated_wa = ?
        WHERE email = ? AND (status = 'free' OR status = 'trial' OR status = 'trial_expired')
    """, (wa_number, trial_end.isoformat(), now.isoformat(), now.isoformat(), wa_number, email))
    await db.commit()
    return True


async def get_trials_expiring_within_24h(db: aiosqlite.Connection):
    """获取24小时内即将到期的trial用户"""
    now = datetime.utcnow()
    in_24h = now + timedelta(hours=24)
    
    cursor = await db.execute("""
        SELECT email, wa_number, trial_end 
        FROM trials 
        WHERE status = 'trial' 
          AND wa_number IS NOT NULL 
          AND wa_number != ''
          AND trial_end > ? 
          AND trial_end <= ?
    """, (now.isoformat(), in_24h.isoformat()))
    
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_expired_trials(db: aiosqlite.Connection):
    """获取已过期的trial用户"""
    now = datetime.utcnow()
    
    cursor = await db.execute("""
        SELECT email, wa_number, trial_end 
        FROM trials 
        WHERE status = 'trial' 
          AND trial_end <= ?
    """, (now.isoformat(),))
    
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def expire_trials(db: aiosqlite.Connection):
    """批量将已过期的trial用户状态改为free"""
    now = datetime.utcnow()
    
    await db.execute("""
        UPDATE trials 
        SET status = 'free', 
            trial_status = 'inactive'
        WHERE status = 'trial' 
          AND trial_end <= ?
    """, (now.isoformat(),))
    await db.commit()


async def increment_scan_count(db: aiosqlite.Connection, email: str):
    """增加扫描计数（以 email 为准，仅记录总次数，不做限制）"""
    await db.execute("UPDATE trials SET scan_count = scan_count + 1 WHERE email = ?", (email,))
    await db.commit()


async def increment_scan_count_today(db: aiosqlite.Connection, email: str) -> int:
    """增加当日扫描计数，每日重置，返回当前当日扫描次数（通过email查询）"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    cursor = await db.execute(
        "SELECT scan_count_today, last_scan_date FROM trials WHERE email = ?",
        (email,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return 0
    
    count = row["scan_count_today"] or 0
    last_date = row["last_scan_date"]
    
    if last_date != today:
        await db.execute(
            "UPDATE trials SET scan_count_today = 1, last_scan_date = ? WHERE email = ?",
            (today, email)
        )
        await db.commit()
        return 1
    else:
        count += 1
        await db.execute(
            "UPDATE trials SET scan_count_today = ? WHERE email = ?",
            (count, email)
        )
        await db.commit()
        return count


async def increment_scan_count_today_by_ip(db: aiosqlite.Connection, ip_address: str) -> int:
    """增加当日扫描计数，每日重置，返回当前当日扫描次数（通过ip_address查询，用于匿名用户）"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    cursor = await db.execute(
        "SELECT scan_count_today, last_scan_date FROM trials WHERE ip_address = ? AND (email IS NULL OR email = '')",
        (ip_address,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return 0
    
    count = row["scan_count_today"] or 0
    last_date = row["last_scan_date"]
    
    if last_date != today:
        await db.execute(
            "UPDATE trials SET scan_count_today = 1, last_scan_date = ? WHERE ip_address = ? AND (email IS NULL OR email = '')",
            (today, ip_address)
        )
        await db.commit()
        return 1
    else:
        count += 1
        await db.execute(
            "UPDATE trials SET scan_count_today = ? WHERE ip_address = ? AND (email IS NULL OR email = '')",
            (count, ip_address)
        )
        await db.commit()
        return count


async def extend_trial(db: aiosqlite.Connection, email: str, days: int = 7) -> dict:
    """延长试用时间"""
    user = await get_trial_by_email(db, email)
    if not user:
        return None
    
    current_end = datetime.fromisoformat(user["trial_end"])
    new_end = current_end + timedelta(days=days)
    
    await db.execute(
        "UPDATE trials SET trial_end = ?, last_shared_at = ? WHERE email = ?",
        (new_end.isoformat(), datetime.utcnow().isoformat(), email)
    )
    await db.commit()
    
    return {"trial_end": new_end.isoformat(), "days_extended": days}


async def can_share(db: aiosqlite.Connection, email: str) -> bool:
    """检查是否可以分享（24小时内只能分享1次，且只能延长试用用户）"""
    user = await get_trial_by_email(db, email)
    if not user:
        return False
    
    # 只能延长试用用户（不是付费用户）
    if user["status"] == "paid":
        return False
    
    last_shared = user.get("last_shared_at")
    if not last_shared:
        return True
    
    last_shared_time = datetime.fromisoformat(last_shared)
    hours_since = (datetime.utcnow() - last_shared_time).total_seconds() / 3600
    
    return hours_since >= 24


async def save_user_whitelist(db: aiosqlite.Connection, email: str, words: str):
    """保存用户白名单词"""
    await db.execute("UPDATE trials SET whitelist_words = ? WHERE email = ?", (words, email))
    await db.commit()


async def get_user_whitelist(db: aiosqlite.Connection, email: str) -> str:
    """获取用户白名单词"""
    cursor = await db.execute("SELECT whitelist_words FROM trials WHERE email = ?", (email,))
    row = await cursor.fetchone()
    return row[0] if row else ""


async def validate_trial(db: aiosqlite.Connection, token: str) -> tuple:
    """
    校验试用/付费状态
    先通过 token 查到 email，再以 email 为准查 status 和 paid_until
    返回: (is_valid, trial_data or error_code)
    """
    trial = await get_trial_by_token(db, token)
    if not trial:
        return False, "TRIAL_NOT_FOUND"

    email = trial["email"]
    # 以 email 为准重新查询（确保拿到最新状态）
    user = await get_trial_by_email(db, email)
    if not user:
        return False, "TRIAL_NOT_FOUND"

    now = datetime.utcnow()

    # free 状态：永久免费，直接返回有效
    if user["status"] == "free":
        return True, user

    # paid 状态：检查 paid_until
    if user["status"] == "paid":
        if user["paid_until"]:
            paid_until = datetime.fromisoformat(user["paid_until"])
            if paid_until > now:
                return True, user
            else:
                await db.execute(
                    "UPDATE trials SET status = 'trial_expired' WHERE email = ?",
                    (email,)
                )
                await db.commit()
                return False, "NEEDS_PAYMENT"
        return True, user

    # trial_expired：可以使用免费扫描功能
    if user["status"] == "trial_expired":
        return True, user
    
    # cancelled：完全禁用
    if user["status"] == "cancelled":
        return False, "NEEDS_PAYMENT"

    # trial 状态：检查 trial_end
    trial_end = datetime.fromisoformat(user["trial_end"])
    if trial_end <= now:
        await db.execute(
            "UPDATE trials SET status = 'trial_expired' WHERE email = ?",
            (email,)
        )
        await db.commit()
        return False, "NEEDS_PAYMENT"

    return True, user


async def upgrade_to_paid(db: aiosqlite.Connection, email: str, plan_type: str, months: int = 1) -> dict:
    """升级用户为付费状态"""
    now_iso = datetime.utcnow().isoformat()
    paid_until = (datetime.utcnow() + timedelta(days=30 * months)).strftime("%Y-%m-%d")
    await db.execute("""
        UPDATE trials
        SET status = 'paid', paid_until = ?, plan_type = ?, paid_at = COALESCE(paid_at, ?)
        WHERE email = ?
    """, (paid_until, plan_type, now_iso, email))
    await db.commit()
    return {"paid_until": paid_until, "plan_type": plan_type}


# ============ Login Tokens 操作 ============

async def create_login_token(db: aiosqlite.Connection, email: str) -> str:
    """生成登录 Magic Link Token"""
    token_uuid = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    await db.execute("""
        INSERT INTO login_tokens (email, token_uuid, expires_at)
        VALUES (?, ?, ?)
    """, (email, token_uuid, expires_at))
    await db.commit()
    return token_uuid


async def validate_login_token(db: aiosqlite.Connection, token_uuid: str) -> Optional[dict]:
    """验证登录 Token，若有效则标记为已使用"""
    cursor = await db.execute("""
        SELECT * FROM login_tokens
        WHERE token_uuid = ? AND used_at IS NULL AND expires_at > ?
    """, (token_uuid, datetime.utcnow().isoformat()))
    row = await cursor.fetchone()
    if row:
        await db.execute("""
            UPDATE login_tokens SET used_at = ? WHERE token_uuid = ?
        """, (datetime.utcnow().isoformat(), token_uuid))
        await db.commit()
        return dict(row)
    return None


# ============ Scan History 操作 ============

async def save_scan_history(
    db: aiosqlite.Connection,
    user_email: str,
    title_snippet: str,
    risk_level: str,
    score: int,
    raw_result_json: str,
    source_type: str = 'text',
    generated_safe_title: str = None,
    shop_id: str = None,
    item_id: str = None,
    platform: str = "shopee"
):
    """保存扫描历史"""
    await db.execute("""
        INSERT INTO scan_history
        (email, title_snippet, risk_level, score, raw_result_json, source_type, scan_time, generated_safe_title, shop_id, item_id, platform)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_email, title_snippet, risk_level, score, raw_result_json, source_type, datetime.utcnow().isoformat(), generated_safe_title, shop_id, item_id, platform))
    await db.commit()


async def get_scan_history(db: aiosqlite.Connection, user_email: str, page: int = 1, page_size: int = 10) -> tuple:
    """获取用户扫描历史（支持分页）"""
    offset = (page - 1) * page_size
    cursor = await db.execute("""
        SELECT * FROM scan_history WHERE email = ? ORDER BY scan_time DESC LIMIT ? OFFSET ?
    """, (user_email, page_size, offset))
    rows = await cursor.fetchall()

    cursor = await db.execute("SELECT COUNT(*) as total FROM scan_history WHERE email = ?", (user_email,))
    total_row = await cursor.fetchone()
    total = total_row["total"] if total_row else 0

    return [dict(r) for r in rows], total


async def find_comparison_scan(
    db: aiosqlite.Connection,
    user_email: str,
    title: str,
    item_id: str = None,
    shop_id: str = None,
    limit: int = 20,
) -> list:
    """
    IntelliAudit 2.0 Pro Phase 3.1: 查找可对比的历史扫描。
    优先级：item_id 精确匹配 > shop_id + 标题前缀 > 仅标题前缀。
    返回最近的若干条候选（dict 列表），由调用方计算 Jaccard 相似度后择优。
    """
    candidates = []
    # 1. item_id 精确匹配（最强信号）
    if item_id:
        cursor = await db.execute("""
            SELECT * FROM scan_history
            WHERE email = ? AND item_id = ? AND item_id IS NOT NULL AND item_id != ''
            ORDER BY scan_time DESC LIMIT ?
        """, (user_email, item_id, limit))
        candidates = [dict(r) for r in await cursor.fetchall()]
    # 2. shop_id + 标题前缀
    if not candidates and shop_id:
        title_prefix = (title or "")[:30]
        cursor = await db.execute("""
            SELECT * FROM scan_history
            WHERE email = ? AND shop_id = ?
              AND substr(title_snippet, 1, 30) = substr(?, 1, 30)
            ORDER BY scan_time DESC LIMIT ?
        """, (user_email, shop_id, title_prefix, limit))
        candidates = [dict(r) for r in await cursor.fetchall()]
    # 3. 标题前缀兜底
    if not candidates and title:
        title_prefix = title[:30]
        cursor = await db.execute("""
            SELECT * FROM scan_history
            WHERE email = ? AND substr(title_snippet, 1, 30) = substr(?, 1, 30)
            ORDER BY scan_time DESC LIMIT ?
        """, (user_email, title_prefix, limit))
        candidates = [dict(r) for r in await cursor.fetchall()]
    return candidates


# ============ P0-4/P1/P2: Session Cache 操作（PLG 会话缓存）===========
# 会话缓存过期时间（分钟）— 30分钟
SESSION_CACHE_TTL_MINUTES = 30


async def save_session_cache(
    db: aiosqlite.Connection,
    session_id: str,
    scan_data: str,
    scan_timestamp: str,
    source_type: str = "text",
    title_snippet: str = None,
    risk_level: str = None,
    score: int = 100,
    ip_address: str = None,
    platform: str = "shopee"
) -> int:
    """
    P1-2: 保存扫描结果到会话缓存（未登录用户）
    每个会话只保留最新一条扫描结果（覆盖旧记录）
    """
    # 先删除该 session_id 的旧记录（只保留最新）
    await db.execute("DELETE FROM session_cache WHERE session_id = ?", (session_id,))

    cursor = await db.execute("""
        INSERT INTO session_cache (
            session_id, scan_data, scan_timestamp, source_type,
            title_snippet, risk_level, score, ip_address, platform
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, scan_data, scan_timestamp, source_type,
          title_snippet, risk_level, score, ip_address, platform))
    await db.commit()
    return cursor.lastrowid


async def get_session_cache(db: aiosqlite.Connection, session_id: str) -> Optional[dict]:
    """
    P1-3: 从会话缓存中获取最新扫描结果
    返回 None 如果不存在或已过期
    """
    cursor = await db.execute("""
        SELECT * FROM session_cache
        WHERE session_id = ? AND claimed_by IS NULL
        ORDER BY created_at DESC LIMIT 1
    """, (session_id,))
    row = await cursor.fetchone()
    if not row:
        return None

    row_dict = dict(row)

    # 检查是否过期
    created_at_str = row_dict.get("created_at", "")
    if created_at_str:
        try:
            # SQLite CURRENT_TIMESTAMP 格式: 'YYYY-MM-DD HH:MM:SS'
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.utcnow()
            age_minutes = (now - created_at).total_seconds() / 60
            if age_minutes > SESSION_CACHE_TTL_MINUTES:
                return None
            row_dict["expires_in_minutes"] = max(0, int(SESSION_CACHE_TTL_MINUTES - age_minutes))
        except (ValueError, TypeError):
            pass

    return row_dict


async def claim_session_cache(
    db: aiosqlite.Connection,
    session_id: str,
    email: str
) -> Optional[dict]:
    """
    P2-1: 认领会话数据 — 将未登录会话的扫描数据转移到注册用户名下
    幂等设计：已认领的记录再次认领返回成功但不重复操作
    并发安全：使用 UPDATE ... WHERE claimed_by IS NULL 确保只认领一次
    """
    # 1. 查询该 session_id 未认领的记录
    cursor = await db.execute("""
        SELECT * FROM session_cache
        WHERE session_id = ? AND claimed_by IS NULL
        ORDER BY created_at DESC LIMIT 1
    """, (session_id,))
    row = await cursor.fetchone()

    if not row:
        # 检查是否已经被该用户认领过（幂等返回）
        cursor = await db.execute("""
            SELECT * FROM session_cache
            WHERE session_id = ? AND claimed_by = ?
            ORDER BY claimed_at DESC LIMIT 1
        """, (session_id, email))
        already_claimed = await cursor.fetchone()
        if already_claimed:
            return {"already_claimed": True, "data": dict(already_claimed)}
        return None  # 不存在或已过期

    row_dict = dict(row)

    # 2. 原子性认领（并发安全：WHERE claimed_by IS NULL 确保只认领一次）
    now_iso = datetime.utcnow().isoformat()
    cursor = await db.execute("""
        UPDATE session_cache
        SET claimed_by = ?, claimed_at = ?
        WHERE session_id = ? AND claimed_by IS NULL
    """, (email, now_iso, session_id))

    if cursor.rowcount == 0:
        # 并发竞争：被其他请求抢先认领
        cursor = await db.execute("""
            SELECT * FROM session_cache
            WHERE session_id = ? AND claimed_by = ?
            ORDER BY claimed_at DESC LIMIT 1
        """, (session_id, email))
        claimed_by_other = await cursor.fetchone()
        if claimed_by_other and dict(claimed_by_other).get("claimed_by") == email:
            return {"already_claimed": True, "data": dict(claimed_by_other)}
        return None

    await db.commit()
    row_dict["claimed_by"] = email
    row_dict["claimed_at"] = now_iso
    return {"claimed": True, "data": row_dict}


async def cleanup_expired_session_cache(db: aiosqlite.Connection) -> int:
    """
    P0-4: 清理过期的会话缓存记录
    删除超过 TTL 且未被认领的记录
    """
    cutoff = (datetime.utcnow() - timedelta(minutes=SESSION_CACHE_TTL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    cursor = await db.execute("""
        DELETE FROM session_cache
        WHERE claimed_by IS NULL AND created_at < ?
    """, (cutoff,))
    await db.commit()
    return cursor.rowcount


# ============ Admin 1.0: 管理员操作 ============

async def is_admin(db: aiosqlite.Connection, email: str) -> bool:
    """检查用户是否为管理员"""
    cursor = await db.execute("SELECT is_admin FROM trials WHERE email = ?", (email,))
    row = await cursor.fetchone()
    return row is not None and row["is_admin"] == 1


async def get_dashboard_stats(db: aiosqlite.Connection) -> dict:
    """获取仪表盘统计数据（7个核心数字 + 昨日对比）"""
    from globals import MYT
    from datetime import timezone

    now_myt = datetime.now(MYT)
    today = now_myt.strftime("%Y-%m-%d")
    yesterday = (now_myt - timedelta(days=1)).strftime("%Y-%m-%d")

    stats = {}

    # 1. 总注册用户（有 email 的用户）
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM trials WHERE email != '' AND email IS NOT NULL")
    stats["total_users"] = (await cursor.fetchone())["cnt"]

    # 2. Trial 用户
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM trials WHERE status = 'trial'")
    stats["trial_users"] = (await cursor.fetchone())["cnt"]

    # 3. Pro 用户（paid 且未过期）
    now_iso = datetime.utcnow().isoformat()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM trials WHERE status = 'paid' AND paid_until > ?", (now_iso,))
    stats["pro_users"] = (await cursor.fetchone())["cnt"]

    # 4. Free 用户
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM trials WHERE status IN ('free', 'trial_expired')")
    stats["free_users"] = (await cursor.fetchone())["cnt"]

    # 5. 待处理反馈
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM user_feedback WHERE status = 'pending'")
    stats["pending_feedback"] = (await cursor.fetchone())["cnt"]

    # 6. 今日新增注册（按 MYT 日期匹配 trial_start 的日期部分）
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM trials 
        WHERE email != '' AND email IS NOT NULL 
        AND substr(trial_start, 1, 10) = ?
    """, (today,))
    stats["today_new_users"] = (await cursor.fetchone())["cnt"]

    # 7. 今日付费转化（paid_at 日期等于今天）
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM trials 
        WHERE status = 'paid' AND paid_at IS NOT NULL 
        AND substr(paid_at, 1, 10) = ?
    """, (today,))
    stats["today_conversions"] = (await cursor.fetchone())["cnt"]

    # === 昨日对比 ===
    # 昨日新增注册
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM trials 
        WHERE email != '' AND email IS NOT NULL 
        AND substr(trial_start, 1, 10) = ?
    """, (yesterday,))
    stats["yesterday_new_users"] = (await cursor.fetchone())["cnt"]

    # 昨日付费转化
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM trials 
        WHERE status = 'paid' AND paid_at IS NOT NULL 
        AND substr(paid_at, 1, 10) = ?
    """, (yesterday,))
    stats["yesterday_conversions"] = (await cursor.fetchone())["cnt"]

    # 昨日待处理反馈（用创建时间）
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM user_feedback 
        WHERE status = 'pending' AND substr(created_at, 1, 10) = ?
    """, (yesterday,))
    stats["yesterday_pending_feedback"] = (await cursor.fetchone())["cnt"]

    return stats


async def submit_feedback(db: aiosqlite.Connection, email: str, content: str) -> dict:
    """用户提交反馈"""
    now = datetime.utcnow().isoformat()
    cursor = await db.execute("""
        INSERT INTO user_feedback (email, content, status, created_at)
        VALUES (?, ?, 'pending', ?)
    """, (email, content, now))
    await db.commit()
    return {"id": cursor.lastrowid, "email": email, "content": content}


async def get_feedback_list(db: aiosqlite.Connection, status: str = None, limit: int = 100, offset: int = 0) -> list:
    """获取反馈列表（支持按状态筛选）"""
    if status:
        cursor = await db.execute("""
            SELECT f.*, t.status as user_status, t.paid_until, t.trial_end, t.wa_number
            FROM user_feedback f
            LEFT JOIN trials t ON f.email = t.email
            WHERE f.status = ?
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
        """, (status, limit, offset))
    else:
        cursor = await db.execute("""
            SELECT f.*, t.status as user_status, t.paid_until, t.trial_end, t.wa_number
            FROM user_feedback f
            LEFT JOIN trials t ON f.email = t.email
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_feedback_by_id(db: aiosqlite.Connection, feedback_id: int) -> Optional[dict]:
    """获取单条反馈"""
    cursor = await db.execute("""
        SELECT f.*, t.status as user_status, t.paid_until, t.trial_end, t.wa_number
        FROM user_feedback f
        LEFT JOIN trials t ON f.email = t.email
        WHERE f.id = ?
    """, (feedback_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def check_recent_reward(db: aiosqlite.Connection, email: str, days: int = 7) -> bool:
    """检查用户在指定天数内是否已被奖励过（防刷：7天内限一次）"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM user_feedback 
        WHERE email = ? AND reward_days > 0 AND rewarded_at > ?
    """, (email, cutoff))
    count = (await cursor.fetchone())["cnt"]
    return count > 0


async def adopt_feedback_and_reward(db: aiosqlite.Connection, feedback_id: int, reward_days: int = 7) -> dict:
    """
    采纳反馈并奖励用户（智能延期）

    规则：
    - Free 用户 → 直接升级为 Pro（status='paid'），到期时间 = now + 7天
    - Trial 用户 → 升级为 Pro（status='paid'），到期时间 = max(trial_end, now) + 7天
    - Pro 用户 → 到期时间 = max(paid_until, now) + 7天（顺延不覆盖）

    返回: {success, email, new_paid_until, reward_days, message}
    """
    feedback = await get_feedback_by_id(db, feedback_id)
    if not feedback:
        return {"success": False, "message": "反馈不存在"}

    if feedback["status"] != "pending":
        return {"success": False, "message": f"反馈已处理（当前状态: {feedback['status']}）"}

    email = feedback["email"]
    now = datetime.utcnow()
    reward_days_td = timedelta(days=reward_days)

    # 获取用户当前状态
    cursor = await db.execute("SELECT status, paid_until, trial_end FROM trials WHERE email = ?", (email,))
    user = await cursor.fetchone()
    if not user:
        return {"success": False, "message": "用户不存在"}

    user_status = user["status"]
    paid_until_str = user["paid_until"]
    trial_end_str = user["trial_end"]

    # 智能延期计算
    if user_status == "paid" and paid_until_str:
        # 已是 Pro：在现有到期时间基础上顺延
        try:
            current_end = datetime.fromisoformat(paid_until_str)
            base = max(current_end, now)
        except (ValueError, TypeError):
            base = now
        new_paid_until = base + reward_days_td
    elif user_status == "trial" and trial_end_str:
        # Trial 用户：从 max(trial_end, now) 开始延期，升级为 paid
        try:
            current_end = datetime.fromisoformat(trial_end_str)
            base = max(current_end, now)
        except (ValueError, TypeError):
            base = now
        new_paid_until = base + reward_days_td
    else:
        # Free 用户：直接升级为 Pro，从现在开始 7 天
        new_paid_until = now + reward_days_td

    new_paid_until_str = new_paid_until.isoformat()
    now_str = now.isoformat()

    # 更新用户状态为 Pro
    await db.execute("""
        UPDATE trials 
        SET status = 'paid', 
            paid_until = ?,
            paid_at = COALESCE(paid_at, ?),
            plan_type = COALESCE(plan_type, 'feedback_reward')
        WHERE email = ?
    """, (new_paid_until_str, now_str, email))

    # 更新反馈状态
    await db.execute("""
        UPDATE user_feedback 
        SET status = 'adopted', reward_days = ?, rewarded_at = ?
        WHERE id = ?
    """, (reward_days, now_str, feedback_id))

    await db.commit()

    return {
        "success": True,
        "email": email,
        "new_paid_until": new_paid_until_str,
        "reward_days": reward_days,
        "message": f"已采纳反馈，用户 {email} 获得 {reward_days} 天 Pro 权限，到期时间: {new_paid_until_str}",
    }


async def dismiss_feedback(db: aiosqlite.Connection, feedback_id: int) -> dict:
    """忽略反馈（不奖励）"""
    feedback = await get_feedback_by_id(db, feedback_id)
    if not feedback:
        return {"success": False, "message": "反馈不存在"}

    if feedback["status"] != "pending":
        return {"success": False, "message": "反馈已处理"}

    await db.execute("UPDATE user_feedback SET status = 'dismissed' WHERE id = ?", (feedback_id,))
    await db.commit()
    return {"success": True, "message": "反馈已忽略"}


async def get_system_flag(db: aiosqlite.Connection, key: str) -> str:
    """获取系统开关值"""
    cursor = await db.execute("SELECT value FROM system_flags WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else "0"


async def set_system_flag(db: aiosqlite.Connection, key: str, value: str, reason: str = None) -> dict:
    """设置系统开关值"""
    now = datetime.utcnow().isoformat()
    await db.execute("""
        INSERT INTO system_flags (key, value, reason, updated_at) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = ?, reason = ?, updated_at = ?
    """, (key, value, reason, now, value, reason, now))
    await db.commit()
    return {"key": key, "value": value, "reason": reason, "updated_at": now}


async def log_admin_action(db: aiosqlite.Connection, admin_email: str, action: str, target: str = None, detail: str = None):
    """记录管理员操作日志"""
    await db.execute("""
        INSERT INTO admin_logs (admin_email, action, target, detail, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (admin_email, action, target, detail, datetime.utcnow().isoformat()))
    await db.commit()


async def get_safe_titles(db: aiosqlite.Connection, user_email: str) -> list:
    """获取用户的安全标题库"""
    cursor = await db.execute("""
        SELECT title_snippet, generated_safe_title, scan_time FROM scan_history
        WHERE email = ? AND generated_safe_title IS NOT NULL AND generated_safe_title != ''
        ORDER BY scan_time DESC LIMIT 100
    """, (user_email,))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ============ Scan Sessions & Results 操作 ============

async def create_scan_session(db: aiosqlite.Connection, user_id: str, mode: str) -> int:
    """创建扫描会话"""
    await db.execute("""
        INSERT INTO scan_sessions (user_id, mode, status, created_at)
        VALUES (?, ?, 'processing', ?)
    """, (user_id, mode, datetime.utcnow().isoformat()))
    await db.commit()
    cursor = await db.execute("SELECT last_insert_rowid()")
    row = await cursor.fetchone()
    return row[0]


async def add_scan_result(db: aiosqlite.Connection, session_id: int, title: str, risk: str,
                          cost_rm: float = None, price_rm: float = None, margin: float = None, 
                          violations: str = None, platform: str = 'Shopee', description: str = None,
                          shop_id: str = None, item_id: str = None):
    """添加扫描结果"""
    await db.execute("""
        INSERT INTO scan_results (session_id, platform, title, description, risk, cost_rm, price_rm, margin, violations, scanned_at, shop_id, item_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, platform, title, description, risk, cost_rm, price_rm, margin, violations, datetime.utcnow().isoformat(), shop_id, item_id))
    await db.commit()


async def update_scan_session(db: aiosqlite.Connection, session_id: int, **kwargs):
    """更新扫描会话状态"""
    set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [session_id]
    await db.execute(f"UPDATE scan_sessions SET {set_clause} WHERE id = ?", values)
    await db.commit()


async def get_scan_sessions(db: aiosqlite.Connection, user_id: str, page: int = 1, page_size: int = 10) -> tuple:
    """获取用户扫描会话列表（按时间倒序）"""
    offset = (page - 1) * page_size
    cursor = await db.execute("""
        SELECT * FROM scan_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, (user_id, page_size, offset))
    rows = await cursor.fetchall()
    
    cursor = await db.execute("SELECT COUNT(*) as total FROM scan_sessions WHERE user_id = ?", (user_id,))
    total_row = await cursor.fetchone()
    total = total_row[0] if total_row else 0
    
    return [dict(r) for r in rows], total


async def get_scan_session(db: aiosqlite.Connection, session_id: int) -> dict:
    """获取单个扫描会话"""
    cursor = await db.execute("SELECT * FROM scan_sessions WHERE id = ?", (session_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_scan_results(db: aiosqlite.Connection, session_id: int) -> list:
    """获取会话下的所有扫描结果"""
    cursor = await db.execute("SELECT * FROM scan_results WHERE session_id = ? ORDER BY id", (session_id,))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_today_scan_count(db: aiosqlite.Connection, user_id: str) -> int:
    """获取用户今日扫描次数（按会话计数）"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor = await db.execute("""
        SELECT COUNT(*) as count FROM scan_sessions 
        WHERE user_id = ? AND created_at LIKE ?
    """, (user_id, f"{today}%"))
    row = await cursor.fetchone()
    return row[0] if row else 0


# ============ URL Parse Count 操作（基于IP的每日50次限制）===========

async def increment_url_parse_count(db: aiosqlite.Connection, email: str) -> bool:
    """增加用户今日URL解析次数，超过10次返回False"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    cursor = await db.execute("""
        SELECT url_parse_count_today, last_url_parse_date FROM trials WHERE email = ?
    """, (email,))
    row = await cursor.fetchone()
    
    if row:
        last_date = row['last_url_parse_date']
        count = row['url_parse_count_today'] or 0
        
        if last_date != today:
            count = 1
            await db.execute("""
                UPDATE trials SET url_parse_count_today = 1, last_url_parse_date = ? WHERE email = ?
            """, (today, email))
        else:
            if count >= 10:
                return False
            count += 1
            await db.execute("""
                UPDATE trials SET url_parse_count_today = ? WHERE email = ?
            """, (count, email))
        await db.commit()
        return True
    return False


# ============ False Positives 操作（误报申诉）===========

async def report_false_positive(db: aiosqlite.Connection, email: str, reported_word: str, reason: str):
    """提交误报申诉"""
    await db.execute("""
        INSERT INTO false_positives (email, reported_word, reason)
        VALUES (?, ?, ?)
    """, (email, reported_word, reason))
    await db.commit()


async def get_false_positives(db: aiosqlite.Connection, status: str = None) -> list:
    """获取误报申诉列表"""
    if status:
        cursor = await db.execute("""
            SELECT * FROM false_positives WHERE status = ? ORDER BY created_at DESC
        """, (status,))
    else:
        cursor = await db.execute("""
            SELECT * FROM false_positives ORDER BY created_at DESC
        """)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_false_positive_status(db: aiosqlite.Connection, fp_id: int, status: str):
    """更新误报申诉状态"""
    await db.execute("""
        UPDATE false_positives SET status = ? WHERE id = ?
    """, (status, fp_id))
    await db.commit()


# ============ 埋点事件日志操作 ============

async def log_event(db: aiosqlite.Connection, event_name: str, event_data: dict):
    """
    记录埋点事件
    event_name: scan_completed / email_captured / safe_title_copied
    event_data: dict，会被JSON序列化
    """
    import json as _json
    await db.execute("""
        INSERT INTO event_logs (event_name, event_data)
        VALUES (?, ?)
    """, (event_name, _json.dumps(event_data, ensure_ascii=False)))
    await db.commit()
    # 同时打印到控制台日志
    print(f"[EVENT] {event_name}: {event_data}")


# ============ 试用召回操作 ============

async def get_trial_expired_over_7_days(db: aiosqlite.Connection) -> list:
    """
    获取过期满7天的试用用户
    status='trial_expired' 且 trial_end 在 7 天之前
    """
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    cursor = await db.execute("""
        SELECT * FROM trials
        WHERE status = 'trial_expired' AND trial_end <= ?
    """, (cutoff,))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def was_reactivation_sent_recently(db: aiosqlite.Connection, email: str, days: int = 7) -> bool:
    """检查是否在最近 N 天内已发送过召回邮件，避免重复打扰"""
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cursor = await db.execute("""
        SELECT COUNT(*) as cnt FROM reactivation_logs
        WHERE email = ? AND sent_at >= ?
    """, (email, cutoff))
    row = await cursor.fetchone()
    return row['cnt'] > 0


async def record_reactivation_sent(db: aiosqlite.Connection, email: str):
    """记录召回邮件已发送"""
    await db.execute("""
        INSERT INTO reactivation_logs (email) VALUES (?)
    """, (email,))
    await db.commit()


# ============ Batch Jobs 操作 ============

async def create_batch_job(db: aiosqlite.Connection, email: str, filename: str, total_items: int) -> int:
    """创建批量任务"""
    cursor = await db.execute("""
        INSERT INTO batch_jobs (email, filename, status, total_items)
        VALUES (?, ?, 'pending', ?)
    """, (email, filename, total_items))
    await db.commit()
    return cursor.lastrowid


async def get_batch_job(db: aiosqlite.Connection, job_id: int) -> Optional[dict]:
    """获取批量任务信息"""
    cursor = await db.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_batch_job_status(db: aiosqlite.Connection, job_id: int, status: str, processed_items: int = None):
    """更新批量任务状态"""
    if processed_items is not None:
        await db.execute("""
            UPDATE batch_jobs SET status = ?, processed_items = ?, updated_at = ? WHERE id = ?
        """, (status, processed_items, datetime.utcnow().isoformat(), job_id))
    else:
        await db.execute("""
            UPDATE batch_jobs SET status = ?, updated_at = ? WHERE id = ?
        """, (status, datetime.utcnow().isoformat(), job_id))
    await db.commit()


async def save_batch_job_items(db: aiosqlite.Connection, job_id: int, items: list):
    """批量保存任务明细"""
    for item in items:
        await db.execute("""
            INSERT INTO batch_job_items (job_id, row_num, title, url, category, cost_rm, price_rm)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, item['row_num'], item['title'], item.get('url', ''), item.get('category', ''), 
              item.get('cost_rm'), item.get('price_rm')))
    await db.commit()


async def update_batch_job_item(db: aiosqlite.Connection, item_id: int, result: dict):
    """更新单个任务明细的扫描结果"""
    import json as _json
    await db.execute("""
        UPDATE batch_job_items
        SET risk_level = ?, violations = ?, score = ?, status = ?
        WHERE id = ?
    """, (
        result.get('risk_level', 'safe'),
        _json.dumps(result.get('violations', []), ensure_ascii=False),
        result.get('score', 100),
        'success',
        item_id
    ))
    await db.commit()


async def get_batch_job_items(db: aiosqlite.Connection, job_id: int) -> list:
    """获取批量任务的所有明细"""
    cursor = await db.execute("SELECT * FROM batch_job_items WHERE job_id = ? ORDER BY row_num", (job_id,))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_user_batch_jobs(db: aiosqlite.Connection, email: str, page: int = 1, page_size: int = 10) -> tuple:
    """获取用户的批量任务列表（支持分页）"""
    offset = (page - 1) * page_size
    cursor = await db.execute("""
        SELECT * FROM batch_jobs WHERE email = ? ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, (email, page_size, offset))
    rows = await cursor.fetchall()

    cursor = await db.execute("SELECT COUNT(*) as total FROM batch_jobs WHERE email = ?", (email,))
    total_row = await cursor.fetchone()
    total = total_row["total"] if total_row else 0

    return [dict(r) for r in rows], total


# ============ User Preferences 操作（IntelliAudit 2.0 Pro 配置中心）===========

# 默认偏好配置模板
DEFAULT_PREFERENCES = {
    "platforms": {
        "shopee": {
            "shipping_fee": 0.0,
            "shipping_cost": 0.0,
            "default_category": "general",
            "cashback": True,
            "seller_type": "marketplace",
            "target_profit_margin": 20.0,
            "min_profit_threshold": 2.0,
        },
        "lazada": {
            "shipping_fee": 0.0,
            "shipping_cost": 0.0,
            "default_category": "general",
            "cashback": False,
            "seller_type": "marketplace",
            "target_profit_margin": 20.0,
            "min_profit_threshold": 2.0,
        },
    },
    "global": {
        "default_currency": "RM",
        "locked_exchange_rate": None,
        "default_cost": None,
        "suppliers": [],
    },
}


async def get_user_preferences(db: aiosqlite.Connection, email: str) -> dict:
    """
    获取用户偏好配置。若不存在则返回默认模板（不写入数据库）。
    返回完整的 preferences JSON 字典（合并默认值）。
    """
    import json as _json
    cursor = await db.execute(
        "SELECT preferences_json FROM user_preferences WHERE email = ?",
        (email,)
    )
    row = await cursor.fetchone()
    if not row:
        # 返回默认模板的深拷贝
        return _json.loads(_json.dumps(DEFAULT_PREFERENCES))

    try:
        stored = _json.loads(row["preferences_json"]) if row["preferences_json"] else {}
    except (ValueError, TypeError):
        stored = {}

    # 合并默认值（确保新增字段有默认值，向后兼容）
    merged = _json.loads(_json.dumps(DEFAULT_PREFERENCES))
    for platform in ("shopee", "lazada"):
        if platform in stored.get("platforms", {}):
            merged["platforms"][platform].update(stored["platforms"][platform])
    if "global" in stored:
        merged["global"].update(stored["global"])
    return merged


async def save_user_preferences(db: aiosqlite.Connection, email: str, preferences: dict) -> dict:
    """
    保存（或更新）用户偏好配置。UPSERT 语义。
    返回保存后的完整配置（合并默认值）。
    """
    import json as _json
    now_iso = datetime.utcnow().isoformat()
    # 先读取现有值做合并（确保不丢失未提交的字段）
    current = await get_user_preferences(db, email)

    # 按平台合并 platforms
    if "platforms" in preferences:
        for platform in ("shopee", "lazada"):
            if platform in preferences["platforms"]:
                current["platforms"][platform].update(preferences["platforms"][platform])

    # 合并 global
    if "global" in preferences:
        g = preferences["global"]
        if "suppliers" in g:
            # suppliers 是数组，整体替换
            current["global"]["suppliers"] = g["suppliers"]
        for k in ("default_currency", "locked_exchange_rate", "default_cost"):
            if k in g:
                current["global"][k] = g[k]

    preferences_json = _json.dumps(current, ensure_ascii=False)
    await db.execute("""
        INSERT INTO user_preferences (email, preferences_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            preferences_json = excluded.preferences_json,
            updated_at = excluded.updated_at
    """, (email, preferences_json, now_iso))
    await db.commit()
    return current


async def get_platform_preference(db: aiosqlite.Connection, email: str, platform: str) -> dict:
    """
    获取指定平台的偏好配置子集。
    若 platform 非法或用户无配置，返回默认平台的配置。
    """
    prefs = await get_user_preferences(db, email)
    return prefs.get("platforms", {}).get(platform, prefs["platforms"]["shopee"])
