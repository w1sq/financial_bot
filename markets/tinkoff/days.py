import datetime

import asyncio
import tinkoff
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    AsyncClient,
    CandleInterval,
)


from bot import TG_Bot
from candle_model import Candle, candle_type_analysis


async def get_all_shares():
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        shares = []
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]:
                    shares.append(
                        {
                            "name": item.name,
                            "ticker": item.ticker,
                            "class_code": item.class_code,
                            "figi": item.figi,
                            "uid": item.uid,
                            "type": method,
                            "min_price_increment": float(
                                quotation_to_decimal(item.min_price_increment)
                            ),
                            "scale": 9 - len(str(item.min_price_increment.nano)) + 1,
                            "lot": item.lot,
                            "api_trade_available_flag": item.api_trade_available_flag,
                            "currency": item.currency,
                            "exchange": item.exchange,
                            "buy_available_flag": item.buy_available_flag,
                            "sell_available_flag": item.sell_available_flag,
                            "short_enabled_flag": item.short_enabled_flag,
                            "klong": float(quotation_to_decimal(item.klong)),
                            "kshort": float(quotation_to_decimal(item.kshort)),
                        }
                    )
        return shares


# TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw" #readonly
TOKEN = "t.Gb6EBFHfF-eQqwR8LXYn6l7A5AM6aFh1vX9QMOmrZJ2V6OEhZdNZuW4dpThKlEH504oN2Og6HLdMXyltEBK5QQ"  # full access


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


async def market_review(tg_bot: TG_Bot):
    shares = await get_all_shares()
    time_stamp = datetime.datetime.now().hour
    # time_stamp = 1
    async with AsyncClient(TOKEN) as client:
        while True:
            time_now = datetime.datetime.now()
            if time_now.hour == time_stamp:
                if datetime.datetime.today().weekday() == 1:
                    hours_delta = 72
                    days_delta = 3
                else:
                    days_delta = 1
                    hours_delta = 24
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
                                    message_to_send, "andrey", candle.volume
                                )
                await asyncio.sleep(20 * 60 * 60)
            else:
                await asyncio.sleep(30 * 60)


if __name__ == "__main__":
    print(asyncio.run(get_all_shares()))
