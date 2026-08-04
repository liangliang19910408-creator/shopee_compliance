import sys
sys.path.insert(0, '/Users/bibox/shopee-compliance-mvp/shopee_compliance')
import asyncio
import aiosqlite
from config import DATABASE_PATH

async def check():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        rows = await cursor.fetchall()
        for row in rows:
            print(f"\n{'='*60}")
            print(row[0])

asyncio.run(check())
