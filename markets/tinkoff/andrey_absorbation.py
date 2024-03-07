import datetime
from typing import Optional, List, Dict, Tuple

import asyncio
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle

from bot import TG_Bot
from config import Config
from markets.tinkoff.utils import get_shares


# declaration of utility containers

data: Dict[str, List[Tuple[HistoricCandle, float]]] = {}


class StrategyConfig:
    take_profit = 2
    stop_los = 1
    dynamic_border = True  # статичные или динамические границы ордеров
    dynamic_border_mult = 1.25  # насколько двигаем границу, при достижении профита, тут нужны пояснения от Андрея
    falling_indicator_frame_count = 5
    volume = 0  # поизучать
    comission = 0.05  # в процентах
    money_in_order = 100000  # виртуальная сумма для сделки


def analisys(ticker: str, candle_data: HistoricCandle) -> Optional[Dict]:
    if float(quotation_to_decimal(candle_data.high - candle_data.low)):
        candle_body_perc = (
            100
            * abs(float(quotation_to_decimal(candle_data.open - candle_data.close)))
            / float(quotation_to_decimal(candle_data.high - candle_data.low))
        )
    else:
        candle_body_perc = 0
    prev_candles = data[ticker]

    if len(prev_candles) < StrategyConfig.falling_indicator_frame_count:
        prev_candles.append((candle_data, candle_body_perc))
        return None
    prev_candle_data, prev_candle_data_body_perc = prev_candles[-1]

    _market_list = []

    for j in range(StrategyConfig.falling_indicator_frame_count):
        _market_list.append(
            float(quotation_to_decimal(prev_candles[len(prev_candles) - j - 1][0].open))
        )
    prev_candles.append((candle_data, candle_body_perc))
    if (
        (
            (
                (prev_candle_data.open <= prev_candle_data.close)
                & (candle_data.open > candle_data.close)
            )
            & (prev_candle_data_body_perc > 20)
            & (float(candle_body_perc) > 20)
        )
        & (prev_candle_data.open <= candle_data.open)
        & falling_indicator(_market_list)
    ):
        return {
            "ticker": ticker,
            "buy_date": candle_data.time,
            "buy_price": float(quotation_to_decimal(candle_data.close)),
            "number_of_shares": (
                float(StrategyConfig.money_in_order)
                * (100 - StrategyConfig.comission)
                / 100
            )
            / float(quotation_to_decimal(candle_data.close)),
            "money_in_order": float(StrategyConfig.money_in_order)
            * (100 - StrategyConfig.comission)
            / 100,
            "stop_los": float(quotation_to_decimal(candle_data.close))
            * float((100 - StrategyConfig.stop_los) / 100),
            "take_profit": float(quotation_to_decimal(candle_data.close))
            * float((100 + StrategyConfig.take_profit) / 100),
            "sell_date": "-",
            "sell_price": "-",
            "sell_volume(money)": "-",
            "profit(share)": "-",
            "profit(money)_minus_comission": "-",
            "comission(share)": float(quotation_to_decimal(candle_data.close))
            * StrategyConfig.comission
            / 100,
            "comission(money)": float(StrategyConfig.money_in_order)
            * StrategyConfig.comission
            / 100,
        }
    return None


# индикатор того, что рынок до появления сигнала - падающий
def falling_indicator(input_list: List[float]) -> bool:
    return (
        sum(input_list) / len(input_list) >= input_list[-1]
    )  # рынок "падающий" - если текущая цена ниже среднего за falling_indicator_frame_count дней


async def fill_data(shares: List[Dict], client: AsyncClient) -> List[Dict]:
    old_purchases = []
    for share in shares:
        data[share["ticker"]] = []
    for share in shares:
        async for candle in client.get_all_candles(
            figi=share["figi"],
            from_=datetime.datetime.combine(
                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                datetime.time(6, 0),
            ).replace(tzinfo=datetime.timezone.utc)
            - datetime.timedelta(days=6),
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            old_purchase = analisys(share["ticker"], candle)
            if old_purchase is not None:
                # print(purchase)
                old_purchases.append(old_purchase)
    return old_purchases


async def send_message(tg_bot: TG_Bot, purchase):
    await tg_bot.send_signal(
        message=f"СТРАТЕГИЯ АНДРЕЯ СИГНАЛ НА ПОКУПКУ\n\nПокупка #{purchase['ticker']} {purchase['buy_date']:%d-%m-%Y}\nЦена: {purchase['buy_price']} руб\nКоличество: {round(purchase['number_of_shares'])}\nСумма сделки: {purchase['money_in_order']} руб\nСтоп-лосс: {purchase['stop_los']} руб\nТейк-профит: {purchase['take_profit']} руб",
        strategy="andrey",
        volume=0,
    )


async def market_review_andrey(tg_bot: TG_Bot):
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        shares = await get_shares(client)
        old_purchases = await fill_data(shares, client)
        # print(len(purchases))
        for old_purchase in old_purchases:
            await send_message(tg_bot, old_purchase)
        await asyncio.sleep(30)
        work_hour = datetime.datetime.now().hour
        # work_hour = 1
        while True:
            if datetime.datetime.now().hour == work_hour:
                candles = []
                for share in shares:
                    async for candle in client.get_all_candles(
                        figi=share["figi"],
                        from_=now() - datetime.timedelta(days=1),
                        interval=CandleInterval.CANDLE_INTERVAL_DAY,
                    ):
                        candles.append((share["ticker"], candle))
                for candle in candles:
                    purchase = analisys(candle[0], candle[1])
                    if purchase is not None:
                        await send_message(tg_bot, purchase)
                await asyncio.sleep(60 * 60 * 23)
            else:
                await asyncio.sleep(60)
