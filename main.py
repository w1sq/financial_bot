"""Main script for project startup"""

import asyncio
import aiogram

from bot import TG_Bot
from db import DB
from db.storage import UserStorage
from config import Config

# from markets.tinkoff.scarping import market_review_scarping

from markets.tinkoff.nikita import market_review_nikita
from markets.tinkoff.andrey_absorbation import market_review_andrey
from markets.tinkoff.george import market_review_george
from markets.tinkoff.andrey_candles import market_review


class Launcher:
    """Class for launching all project subprocesses together"""

    def __init__(self):
        self.tg_bot: aiogram.Bot = None
        self.user_storage: UserStorage = None
        self.db: DB = None

    async def init_db(self):
        """Database startup"""
        self.db = DB(
            host=Config.HOST,
            port=Config.PORT,
            login=Config.LOGIN,
            password=Config.PASSWORD,
            database=Config.DATABASE,
        )
        await self.db.init()
        self.user_storage = UserStorage(self.db)
        await self.user_storage.init()
        return self.user_storage

    async def create_bot(self):
        self.user_storage = await self.init_db()
        self.tg_bot = TG_Bot(self.user_storage)

    async def main(self):
        """Bot startup function"""
        await self.tg_bot.init()
        await self.tg_bot.start()

    async def tasks_init(self):
        await self.create_bot()
        tasks = [
            # market_review_scarping(self.tg_bot),
            market_review(self.tg_bot),
            market_review_nikita(self.tg_bot),
            market_review_andrey(self.tg_bot),
            market_review_george(self.tg_bot),
            self.main(),
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    launcher = Launcher()
    asyncio.run(launcher.tasks_init())
