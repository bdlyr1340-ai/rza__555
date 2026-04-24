import asyncpg
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self._create_tables()

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    registered_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS frida_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    device_id TEXT,
                    status TEXT,
                    result TEXT,
                    executed_at TIMESTAMP DEFAULT NOW()
                )
            ''')

    async def add_user(self, user_id, username, first_name):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO NOTHING
            ''', user_id, username, first_name)

    async def log_frida_run(self, user_id, device_id, status, result):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO frida_logs (user_id, device_id, status, result)
                VALUES ($1, $2, $3, $4)
            ''', user_id, device_id, status, result)

db = Database()