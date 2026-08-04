"""
数据库迁移脚本：添加 password_hash 字段
运行方式：python3 migrate_password.py
"""
import aiosqlite
import asyncio
from config import DATABASE_PATH


async def migrate_add_password_hash():
    """为 trials 表添加 password_hash 字段"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. 检查 password_hash 字段是否已存在
        cursor = await db.execute("PRAGMA table_info(trials)")
        columns = await cursor.fetchall()
        column_names = [col['name'] for col in columns]
        
        if 'password_hash' in column_names:
            print("[MIGRATION] password_hash 字段已存在，无需迁移")
            return
        
        # 2. 添加 password_hash 字段
        print("[MIGRATION] 正在添加 password_hash 字段...")
        await db.execute("ALTER TABLE trials ADD COLUMN password_hash TEXT")
        await db.commit()
        
        # 3. 验证字段已添加
        cursor = await db.execute("PRAGMA table_info(trials)")
        columns = await cursor.fetchall()
        column_names = [col['name'] for col in columns]
        
        if 'password_hash' in column_names:
            print("[MIGRATION] ✅ password_hash 字段已成功添加")
        else:
            print("[MIGRATION] ❌ 添加字段失败")


if __name__ == "__main__":
    asyncio.run(migrate_add_password_hash())