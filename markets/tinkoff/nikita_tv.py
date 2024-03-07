import datetime
from typing import Optional, List, Dict

from tinkoff.invest import AsyncClient
from tradingview_ta import TA_Handler, Interval

from bot import TG_Bot
from config import Config
from markets.tinkoff.utils import get_shares, trade_by_ticker, moneyvalue_to_float


class StrategyConfig:
    bolinger_mult = 2
    bollinger_frame_count = 20
    rsi_count_frame = 14
    strategy_bollinger_range = 1.25
    rsi_treshold = 30
    take_profit = 0.4
    stop_los = 1


def get_analysis(symbol: str):
    try:
        data = TA_Handler(
            symbol=symbol,
            screener="russia",
            exchange="MOEX",
            interval=Interval.INTERVAL_1_HOUR,
        )
        analysis = data.get_analysis()
        return analysis
    except Exception:
        return None


async def bollinger_and_rsi_data(share: dict, purchases: dict) -> Optional[Dict]:
    analysis = get_analysis(share["ticker"])
    if analysis is None:
        return None

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
        and not purchases.get(share["ticker"], None)
    ):
        quantity_lot = int(
            min(6000, purchases["available"]) // (candle_close * share["lot"])
        )
        if quantity_lot > 0:
            purchase = {
                "date_buy": analysis.time.strftime("%d-%m-%Y %H:%M"),
                "date_sell": "-",
                "price_sell": "-",
                "profit": "-",
            }
            purchase["ticker"] = share["ticker"]
            purchases[share["ticker"]] = purchase
            purchase["type"] = 1
            buy_trade = await trade_by_ticker(
                share["ticker"], 1, quantity_lot, Config.NIKITA_TOKEN
            )
            print("ABOBA", buy_trade)
            purchase["quantity"] = buy_trade.lots_executed * share["lot"]
            purchase["price_buy"] = moneyvalue_to_float(buy_trade.executed_order_price)
            purchase["buy_commission"] = moneyvalue_to_float(
                buy_trade.initial_commission
            )
            purchases["available"] -= (
                purchase["quantity"] * purchase["price_buy"]
                + purchase["buy_commission"]
            )
            return purchase
    elif purchases.get(share["ticker"], None):
        purchase = purchases[share["ticker"]]
        if not purchase.get("price_buy", None):
            purchases.pop(share["ticker"])
        candle_open = analysis.indicators["open"]
        if (
            (
                candle_open
                > float(purchase["price_buy"])
                * (100 + StrategyConfig.take_profit)
                / 100
            )
            or (
                candle_open
                < float(purchase["price_buy"]) * (100 - StrategyConfig.stop_los) / 100
            )
        ) and purchase["profit"] == "-":
            purchase["date_sell"] = analysis.time.strftime("%d-%m-%Y %H:%M")
            purchases[share["ticker"]] = {}
            purchase["type"] = 2
            sell_trade = await trade_by_ticker(
                share["ticker"],
                2,
                int(purchase["quantity"] / share["lot"]),
                Config.NIKITA_TOKEN,
            )
            purchase["price_sell"] = moneyvalue_to_float(
                sell_trade.executed_order_price
            )
            purchase["sell_commission"] = moneyvalue_to_float(
                sell_trade.initial_commission
            )
            purchase["profit"] = (
                purchase["price_sell"]
                - purchase["price_buy"]
                - purchase["sell_commission"]
                - purchase["buy_commission"]
            ) * purchase["quantity"]
            purchases["available"] += (
                purchase["quantity"] * purchase["price_sell"]
                - purchase["sell_commission"]
            )
            return purchase
    return None


async def send_message(tg_bot: TG_Bot, trade: Dict):
    if trade["type"] == 2:
        message_text = f"СТРАТЕГИЯ НИКИТЫ ПРОДАЖА\n\nПокупка {trade['ticker']} {trade['date_buy']} по цене {trade['price_buy']} с коммисией {trade['buy_commission']}\nКол-во: {trade['quantity']}\n\nПродажа {trade['date_sell']} по цене {trade['price_sell']} с коммисией {trade['sell_commission']}\n\nПрибыль: {trade['profit']}"
    else:
        message_text = f"СТРАТЕГИЯ НИКИТЫ ПОКУПКА\n\nПокупка {trade['ticker']} {trade['date_buy']} по цене {trade['price_buy']} с коммисией {trade['buy_commission']}\nКол-во: {trade['quantity']}"
    await tg_bot.send_signal(
        message=message_text,
        strategy="nikita",
        volume=0,
    )


async def market_review_nikita(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    local_purchases = purchases["nikita"]
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        shares = await get_shares(client)
    time_now = datetime.datetime.now()
    if time_now.hour in Config.MOEX_WORKING_HOURS:
        for share in shares:
            trade = await bollinger_and_rsi_data(share, local_purchases)
            if trade is not None:
                await send_message(tg_bot, trade)
