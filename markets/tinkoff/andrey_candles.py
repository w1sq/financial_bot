import datetime
from typing import Dict

import asyncio
import tinkoff
from tinkoff.invest import (
    AsyncClient,
    CandleInterval,
)

from bot import TG_Bot
from markets.tinkoff.candle_model import CustomCandle
from config import Config
from markets.tinkoff.utils import get_shares


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


async def market_review_candles(tg_bot: TG_Bot):
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        time_now = datetime.datetime.now()
        shares = await get_shares(client)
        if time_now.weekday() == 1:
            days_delta = 3
        elif 7 > time_now.weekday() > 1:
            days_delta = 1
        else:
            return
        hours_delta = 24 * days_delta
        last_day_data: Dict[str:CustomCandle] = {}
        for share in shares:
            async for candle in client.get_all_candles(
                figi=share["figi"],
                from_=tinkoff.invest.utils.now()
                - datetime.timedelta(hours=hours_delta + time_now.hour),
                to=tinkoff.invest.utils.now(),
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                custom_candle = CustomCandle(candle)
                if (time_now - candle.time.replace(tzinfo=None)).days > days_delta:
                    last_day_data[share["figi"]] = custom_candle
                    # print(share["ticker"] + " " + str(candle))
                elif (time_now - candle.time.replace(tzinfo=None)).days == 1 and share[
                    "figi"
                ] in last_day_data:
                    # print(share["ticker"], candle)
                    custom_candle.calc_type()
                    prev_custom_candle: CustomCandle = last_day_data[share["figi"]]
                    if custom_candle.type not in [
                        "trash",
                        "green_middle",
                        "red_middle",
                    ]:
                        procent_volume = (
                            custom_candle.volume / prev_custom_candle.volume
                        )
                        if procent_volume >= 1:
                            volume_smile = "🟢"
                        else:
                            volume_smile = "🔴"
                        money_volume = (
                            custom_candle.volume
                            * share["lot"]
                            * (custom_candle.low + custom_candle.length / 2)
                        )
                        if money_volume > 10**9:
                            volume_string = f"{round(money_volume/10**9, 2)} МЛРД"
                        else:
                            volume_string = f"{round(money_volume/10**6)} МЛН"
                        percent_price_delta = round(
                            (
                                (custom_candle.close - prev_custom_candle.close)
                                / prev_custom_candle.close
                            )
                            * 100,
                            2,
                        )
                        message_to_send = f"""
#{share["ticker"]} {percent_price_delta}% {volume_string} ₽
<b>{share["name"]}</b>

Определён тип свечи: {custom_candle.type}
Изменение цены: {percent_price_delta}%
Объём: {volume_smile} {round(procent_volume*100, 2)}%
Время: {candle.time.strftime("%d-%m-%Y")}
Цена: {custom_candle.close} ₽"""
                        # print(message_to_send)
                        await tg_bot.send_signal(
                            message_to_send, "andrey", money_volume
                        )
