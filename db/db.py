from typing import List, Any

import asyncpg

class DB():
    def __init__(self, host:str, port:str, login:str, password:str, database:str, pool_size:int=10):
        self._host = host
        self._port = port
        self._login = login
        self._password = password
        self._database = database
        self._pool_size = pool_size

    async def init(self):
        self._pool = await asyncpg.create_pool(f"postgres://{self._login}:{self._password}@{self._host}:{self._port}/{self._database}")

    async def execute(self, query, *params):
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                return await conn.execute(query, *params)

    async def fetchrow(self, query, *params) -> List:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                return await conn.fetchrow(query, *params)

    async def fetch(self, query, *params) -> List[List]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                return await conn.fetch(query, *params)

    async def fetchval(self, query, *params) -> Any:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                return await conn.fetchval(query, *params)
