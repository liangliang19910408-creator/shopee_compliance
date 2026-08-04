import sys
sys.path.insert(0, '/Users/bibox/shopee-compliance-mvp/shopee_compliance')
import asyncio
import aiosqlite
from config import DATABASE_PATH

async def main():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        print("=== 免费用户记录 ===")
        cursor = await db.execute("SELECT * FROM trials WHERE (email IS NULL OR email = '')")
        rows = await cursor.fetchall()
        for row in rows:
            print(dict(row))
        
        print("\n=== scan_sessions 记录 ===")
        cursor = await db.execute("SELECT * FROM scan_sessions ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        for row in rows:
            print(dict(row))

asyncio.run(main())
