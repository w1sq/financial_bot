import datetime
from typing import Optional, List, Dict

from tinkoff.invest import AsyncClient
from tradingview_ta import TA_Handler, Interval

from bot import TG_Bot
from config import Config
from markets.tinkoff.utils import get_all_shares


class StrategyConfig:
    bolinger_mult = 2
    bollinger_frame_count = 20
    rsi_count_frame = 14
    strategy_bollinger_range = 1.25
    rsi_treshold = 30
    take_profit = 0.4
    stop_los = 1


# declaration of utility containers


def get_analysis(symbol: str):
    data = TA_Handler(
        symbol=symbol,
        screener="russia",
        exchange="MOEX",
        interval=Interval.INTERVAL_1_HOUR,
    )
    analysis = data.get_analysis()
    return analysis


def bollinger_and_rsi_data(ticker: str, purchases: dict) -> Optional[Dict]:
    analysis = get_analysis(ticker)
    candle_close = analysis.indicators["close"]
    avarege = (analysis.indicators["BB.lower"] + analysis.indicators["BB.upper"]) / 2
    sko = (avarege - analysis.indicators["BB.lower"]) / 2
    rsi = analysis.indicators["RSI"]
    if (
        candle_close
        < (
            avarege
            - StrategyConfig.bolinger_mult
            * sko
            * StrategyConfig.strategy_bollinger_range
        )
        and rsi <= StrategyConfig.rsi_treshold
        and not purchases.get(ticker, None)
    ):
        _purchase = {
            "date_buy": analysis.time,
            "price_buy": candle_close,
            "date_sell": "-",
            "price_sell": "-",
            "profit": "-",
        }
        _purchase["ticker"] = ticker
        purchases[ticker] = _purchase
        _purchase["type"] = "ПОКУПКА"
        return _purchase
    elif purchases.get(ticker, None):
        _purchase = purchases[ticker]
        candle_open = analysis.indicators["open"]
        if (
            (
                candle_open
                > float(_purchase["price_buy"])
                * (100 + StrategyConfig.take_profit)
                / 100
            )
            or (
                candle_open
                < float(_purchase["price_buy"]) * (100 - StrategyConfig.stop_los) / 100
            )
        ) and _purchase["profit"] == "-":
            _purchase["date_sell"] = analysis.time
            _purchase["price_sell"] = candle_open
            _purchase["profit"] = candle_open - _purchase["price_buy"]
            purchases[ticker] = {}
            _purchase["type"] = "ПРОДАЖА"
            return _purchase
    return None


async def send_message(tg_bot: TG_Bot, trade: Dict):
    if trade["type"] == "ПРОДАЖА":
        message_text = f"СТРАТЕГИЯ НИКИТЫ {trade['type']}\n\nПокупка {trade['ticker']} {trade['date_buy']+datetime.timedelta(hours=3):%d-%m-%Y %H:%M} по цене {trade['price_buy']}\n\nПродажа {trade['date_sell']+datetime.timedelta(hours=3):%d-%m-%Y %H:%M} по цене {trade['price_sell']}\n\nПрибыль: {trade['profit']}"
    else:
        message_text = f"СТРАТЕГИЯ НИКИТЫ {trade['type']}\n\nПокупка {trade['ticker']} {trade['date_buy']+datetime.timedelta(hours=3):%d-%m-%Y %H:%M} по цене {trade['price_buy']}"
    await tg_bot.send_signal(
        message=message_text,
        strategy="nikita",
        volume=0,
    )


async def market_review_nikita(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    local_purchases = purchases["nikita"]
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        shares = await get_all_shares(client)
    time_now = datetime.datetime.now()
    if time_now.hour in Config.MOEX_WORKING_HOURS:
        for share in shares:
            trade = bollinger_and_rsi_data(share["ticker"], local_purchases)
            if trade is not None:
                await send_message(tg_bot, trade)
