"""Main script for project startup"""

import json
from typing import Dict

import asyncio
import aiogram

# from markets.tinkoff.scarping import market_review_scarping
from markets.tinkoff.nikita import (
    market_review_nikita,
    orders_check_nikita,
    stop_orders_check_nikita,
    fill_data_nikita,
)

from markets.tinkoff.andrey_absorbation import (
    market_review_andrey,
    fill_market_data_andrey,
    orders_check_andrey,
    stop_orders_check_andrey,
)
from markets.tinkoff.andrey_candles import market_review_candles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import TG_Bot
from db import DB
from db.storage import UserStorage
from config import Config


def serialize_purchases(purchases: Dict[str, Dict]):
    """Serialize purchases to file"""
    with open("purchases.json", "w", encoding="utf-8") as file:
        file.write(json.dumps(purchases))


def deserialize_purchases():
    """Deserialize purchases from file"""
    with open("purchases.json", "r", encoding="utf-8") as file:
        return json.loads(file.read())


class Launcher:
    """Class for launching all project subprocesses together"""

    def __init__(self):
        self.tg_bot: aiogram.Bot = None
        self.user_storage: UserStorage = None
        self.db: DB = None
        self.strategies_data = (
            deserialize_purchases()
        )  # {"nikita": { "available": 20000, "orders": {} },"andrey": { "available": 30000, "orders": {} },"george": {}}

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

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            market_review_nikita,
            "cron",
            hour="10-23",
            second="00",
            day_of_week="mon-fri",
            args=[self.tg_bot, self.strategies_data["nikita"]],
        )
        scheduler.add_job(
            orders_check_nikita,
            "cron",
            hour="10-23",
            second="00",
            args=[self.tg_bot, self.strategies_data["nikita"]],
        )
        scheduler.add_job(
            stop_orders_check_nikita,
            "cron",
            hour="10-23",
            second="00",
            args=[self.tg_bot, self.strategies_data["nikita"]],
        )
        scheduler.add_job(
            market_review_andrey,
            "cron",
            hour="11",
            args=[self.tg_bot, self.strategies_data["andrey"]],
        )
        scheduler.add_job(
            orders_check_andrey,
            "cron",
            second="00",
            hour="10-23",
            day_of_week="mon-fri",
            args=[self.tg_bot, self.strategies_data["andrey"]],
        )
        scheduler.add_job(
            stop_orders_check_andrey,
            "cron",
            second="00",
            hour="10-23",
            args=[self.tg_bot, self.strategies_data["andrey"]],
        )
        scheduler.add_job(
            market_review_candles,
            "cron",
            hour="1",
            args=[self.tg_bot],
        )
        scheduler.add_job(
            serialize_purchases,
            "cron",
            second="30",
            args=[self.strategies_data],
        )
        # scheduler.start()

        # await fill_data_nikita(self.strategies_data["nikita"])
        await fill_market_data_andrey(self.strategies_data["andrey"])
        tasks = [
            market_review_andrey(self.tg_bot, self.strategies_data["andrey"]),
            # market_review_candles(self.tg_bot),
            self.main(),
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    launcher = Launcher()
    loop.run_until_complete(launcher.tasks_init())
