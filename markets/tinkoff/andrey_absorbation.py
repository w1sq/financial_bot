import datetime
from typing import Optional, List, Dict, Tuple

import asyncio
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle

from bot import TG_Bot
from config import Config
from markets.tinkoff.utils import get_shares


# declaration of utility containers

# data: Dict[str, List[Tuple[HistoricCandle, float]]] = {}


class StrategyConfig:
    take_profit = 2
    stop_los = 1
    dynamic_border = True  # статичные или динамические границы ордеров
    dynamic_border_mult = 1.25  # насколько двигаем границу, при достижении профита, тут нужны пояснения от Андрея
    falling_indicator_frame_count = 5
    volume = 0  # поизучать
    comission = 0.05  # в процентах
    money_in_order = 100000  # виртуальная сумма для сделки


def get_candle_body_perc(candle: HistoricCandle) -> float:
    if float(quotation_to_decimal(candle.high - candle.low)):
        return (
            100
            * abs(float(quotation_to_decimal(candle.open - candle.close)))
            / float(quotation_to_decimal(candle.high - candle.low))
        )
    else:
        return 0


def analisys(ticker: str, current_candle: HistoricCandle, data: dict) -> Optional[Dict]:
    if not data[ticker]:
        data[ticker] = (
            current_candle,
            [float(quotation_to_decimal(current_candle.open))],
        )
        return None
    prev_candle, market_data = data[ticker]
    market_data.append(float(quotation_to_decimal(current_candle.open)))

    if len(market_data) < StrategyConfig.falling_indicator_frame_count:
        return None

    if len(market_data) > StrategyConfig.falling_indicator_frame_count:
        market_data = market_data[1:]

    data[ticker] = (current_candle, market_data)

    current_candle_body_perc = get_candle_body_perc(current_candle)
    prev_candle_body_perc = get_candle_body_perc(prev_candle)
    falling_market_indicator = falling_indicator(market_data)
    if (
        (
            (
                (prev_candle.open <= prev_candle.close)
                & (current_candle.open > current_candle.close)
            )
            & (prev_candle_body_perc > 20)
            & (current_candle_body_perc > 20)
        )
        & (prev_candle.open <= current_candle.open)
        & falling_market_indicator
    ):
        return {
            "ticker": ticker,
            "buy_date": current_candle.time.strftime("%d-%m-%Y"),
            "buy_price": float(quotation_to_decimal(current_candle.close)),
            # "number_of_shares": (
            #     float(StrategyConfig.money_in_order)
            #     * (100 - StrategyConfig.comission)
            #     / 100
            # )
            # / float(quotation_to_decimal(current_candle.close)),
            # "money_in_order": float(StrategyConfig.money_in_order)
            # * (100 - StrategyConfig.comission)
            # / 100,
            # "stop_los": float(quotation_to_decimal(current_candle.close))
            # * float((100 - StrategyConfig.stop_los) / 100),
            # "take_profit": float(quotation_to_decimal(current_candle.close))
            # * float((100 + StrategyConfig.take_profit) / 100),
            # "sell_date": "-",
            # "sell_price": "-",
            # "sell_volume(money)": "-",
            # "profit(share)": "-",
            # "profit(money)_minus_comission": "-",
            # "comission(share)": float(quotation_to_decimal(current_candle.close))
            # * StrategyConfig.comission
            # / 100,
            # "comission(money)": float(StrategyConfig.money_in_order)
            # * StrategyConfig.comission
            # / 100,
        }
    return None


# индикатор того, что рынок до появления сигнала - падающий
def falling_indicator(input_list: List[float]) -> bool:
    return (
        sum(input_list) / len(input_list) >= input_list[-1]
    )  # рынок "падающий" - если текущая цена ниже среднего за falling_indicator_frame_count дней


async def fill_data(data: dict, shares: List[Dict], client: AsyncClient) -> List[Dict]:
    old_purchases = []
    for share in shares:
        data["market_data"][share["ticker"]] = ()
    for share in shares:
        async for candle in client.get_all_candles(
            figi=share["figi"],
            from_=datetime.datetime.combine(
                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                datetime.time(6, 0),
            ).replace(tzinfo=datetime.timezone.utc)
            - datetime.timedelta(days=10),
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            old_purchase = analisys(share["ticker"], candle, data["market_data"])
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


async def market_review_andrey(tg_bot: TG_Bot, data: Dict[str, Dict]):
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        shares = await get_shares(client)
        old_purchases = await fill_data(data, shares, client)
        print(old_purchases)
        print("END")
        # for old_purchase in old_purchases:
        #     await send_message(tg_bot, old_purchase)
        # await asyncio.sleep(30)
        # time_now = datetime.datetime.now()
        # if time_now.hour in Config.MOEX_WORKING_HOURS:
        #     candles = []
        #     for share in shares:
        #         async for candle in client.get_all_candles(
        #             figi=share["figi"],
        #             from_=now() - datetime.timedelta(days=1),
        #             interval=CandleInterval.CANDLE_INTERVAL_DAY,
        #         ):
        #             candles.append((share["ticker"], candle))
        #     for candle in candles:
        #         purchase = analisys(candle[0], candle[1], data)
        #         if purchase is not None:
        #             await send_message(tg_bot, purchase)
