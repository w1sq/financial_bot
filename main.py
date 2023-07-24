'''Main script for project startup'''

import asyncio
import aioschedule as schedule

from bot import TG_Bot
from db import DB
from db.storage import UserStorage
from config import Config


async def init_db():
    '''Database startup'''
    db = DB(host=Config.HOST, port=Config.PORT, login=Config.LOGIN, password=Config.PASSWORD, database = Config.DATABASE)
    await db.init()
    user_storage = UserStorage(db)
    await user_storage.init()
    return user_storage

async def check_schedule():
    '''Aioschedule startup'''
    while True:
        await schedule.run_pending()
        await asyncio.sleep(1)

async def main():
    '''Main startup function'''
    user_storage = await init_db()
    tg_bot = TG_Bot(user_storage)
    await tg_bot.init()
    await tg_bot.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(check_schedule())
    loop.run_until_complete(main())
