import datetime

import asyncio
import tinkoff
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    AsyncClient,
    CandleInterval,
)

from bot import TG_Bot
from markets.tinkoff.candle_model import Candle, candle_type_analysis
from config import Config
from markets.tinkoff.utils import get_all_shares


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


async def market_review(tg_bot: TG_Bot):
    time_stamp = datetime.datetime.now().hour
    # time_stamp = 1
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        shares = await get_all_shares(client)
        while True:
            time_now = datetime.datetime.now()
            if time_now.hour == time_stamp:
                if datetime.datetime.today().weekday() == 1:
                    days_delta = 3
                elif 7 > datetime.datetime.today().weekday() > 1:
                    days_delta = 1
                else:
                    await asyncio.sleep(60 * 60)
                    continue
                hours_delta = 24 * days_delta
                last_day_data = {}
                for share in shares:
                    async for candle in client.get_all_candles(
                        figi=share["figi"],
                        from_=tinkoff.invest.utils.now()
                        - datetime.timedelta(hours=hours_delta + time_stamp),
                        to=tinkoff.invest.utils.now(),
                        interval=CandleInterval.CANDLE_INTERVAL_DAY,
                    ):
                        if (
                            time_now - candle.time.replace(tzinfo=None)
                        ).days > days_delta:
                            last_day_data[share["figi"]] = (
                                candle.volume,
                                float(quotation_to_decimal(candle.close)),
                            )
                            # print(share["ticker"] + " " + str(candle))
                        elif (
                            time_now - candle.time.replace(tzinfo=None)
                        ).days == 1 and share["figi"] in last_day_data:
                            # print(share["ticker"], candle)
                            candle_high_shadow_val = float(
                                quotation_to_decimal(
                                    candle.high - max(candle.open, candle.close)
                                )
                            )
                            candle_low_shadow_val = float(
                                quotation_to_decimal(
                                    min(candle.open, candle.close) - candle.low
                                )
                            )
                            price_delta = float(
                                quotation_to_decimal(candle.high - candle.low)
                            )
                            percent_price_delta = round(
                                (
                                    (
                                        float(quotation_to_decimal(candle.close))
                                        - last_day_data[share["figi"]][1]
                                    )
                                    / last_day_data[share["figi"]][1]
                                )
                                * 100,
                                2,
                            )
                            candle_body_val = abs(
                                float(quotation_to_decimal(candle.open))
                                - float(quotation_to_decimal(candle.close))
                            )
                            if price_delta == 0:
                                candle_low_shadow_perc = 0.0
                                candle_high_shadow_perc = 0.0
                                candle_body_perc = 0.0
                            else:
                                candle_high_shadow_perc = (
                                    100 * candle_high_shadow_val / price_delta
                                )
                                candle_low_shadow_perc = (
                                    100 * candle_low_shadow_val / price_delta
                                )
                                candle_body_perc = 100 * candle_body_val / price_delta
                            if candle.open > candle.close:
                                candle_color = "red"
                            else:
                                candle_color = "green"
                            custom_candle = Candle(
                                high_shadow_val=candle_high_shadow_val,
                                low_shadow_val=candle_low_shadow_val,
                                high_shadow_perc=candle_high_shadow_perc,
                                low_shadow_perc=candle_low_shadow_perc,
                                body_val=candle_body_val,
                                body_perc=candle_body_perc,
                                length=price_delta,
                                color=candle_color,
                                type="",
                            )
                            candle_type = candle_type_analysis(
                                custom_candle, candle.volume
                            )
                            custom_candle.type = candle_type
                            if share["ticker"] == "PIKK":
                                print(candle, custom_candle)
                            if candle_type not in [
                                "trash",
                                "green_middle",
                                "red_middle",
                            ]:
                                procent_volume = (
                                    candle.volume / last_day_data[share["figi"]][0]
                                )
                                if procent_volume >= 1:
                                    volume_smile = "🟢"
                                else:
                                    volume_smile = "🔴"
                                money_volume = (
                                    candle.volume
                                    * share["lot"]
                                    * (
                                        float(quotation_to_decimal(candle.low))
                                        + price_delta / 2
                                    )
                                )
                                if money_volume > 10**9:
                                    volume_string = (
                                        f"{round(money_volume/10**9, 2)} МЛРД"
                                    )
                                else:
                                    volume_string = f"{round(money_volume/10**6)} МЛН"
                                message_to_send = f"""
#{share["ticker"]} {percent_price_delta}% {volume_string} ₽
<b>{share["name"]}</b>

Определён тип свечи: {candle_type}
Изменение цены: {percent_price_delta}%
Объём: {volume_smile} {round(procent_volume*100, 2)}%
Время: {time_now:%Y-%m}-{candle.time.day}
Цена: {float(quotation_to_decimal(candle.close))} ₽"""
                                # print(message_to_send)
                                await tg_bot.send_signal(
                                    message_to_send, "andrey", money_volume
                                )
                await asyncio.sleep(20 * 60 * 60)
            else:
                await asyncio.sleep(30 * 60)
