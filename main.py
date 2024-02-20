"""Main script for project startup"""

import asyncio
import aiogram

# import aioschedule as schedule

from bot import TG_Bot
from db import DB
from db.storage import UserStorage
from config import Config

# from markets.tinkoff.days import market_review
# from markets.tinkoff.scarping import market_review_scarping

from markets.tinkoff.hours_nikita import market_review_nikita
from markets.tinkoff.andrey import market_review_andrey


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

    # async def check_schedule():
    #     '''Aioschedule startup'''
    #     while True:
    #         await schedule.run_pending()
    #         await asyncio.sleep(1)

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
            # market_review(self.tg_bot),
            market_review_nikita(self.tg_bot),
            market_review_andrey(self.tg_bot),
            self.main(),
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # queue = asyncio.Queue()
    launcher = Launcher()
    # loop.run_until_complete(launcher.create_bot())
    # # binance = Binance(launcher.tg_bot, loop)
    # # loop.create_task(market_review(launcher.tg_bot))
    # loop.create_task(market_review_scarping(launcher.tg_bot))
    # # loop.create_task(binance.binance_review())
    # loop.run_until_complete(launcher.main())
    asyncio.run(launcher.tasks_init())
