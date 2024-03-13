import datetime
from typing import Optional, List, Dict


from tinkoff.invest import AsyncClient
from tradingview_ta import TA_Handler, Interval, Analysis

# import tinkoff
# from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import (
    OrderState,
    OrderExecutionReportStatus,
)


from bot import TG_Bot
from config import Config
from markets.tinkoff.utils import (
    get_shares,
    buy_limit_order,
    place_stop_orders,
    moneyvalue_to_float,
    get_account_id,
)


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


def check_rsi_bollinger(analysis: Analysis):
    candle_close = analysis.indicators["close"]
    avarege = (analysis.indicators["BB.lower"] + analysis.indicators["BB.upper"]) / 2
    sko = (avarege - analysis.indicators["BB.lower"]) / 2
    rsi = analysis.indicators["RSI"]  # https://pastebin.com/1DjWv2Hd
    return (
        candle_close
        < (
            avarege
            - StrategyConfig.bolinger_mult
            * sko
            * StrategyConfig.strategy_bollinger_range
        )
        and rsi <= StrategyConfig.rsi_treshold
    )


async def analise_share(share: dict, purchases: dict):
    analysis = get_analysis(share["ticker"])
    if analysis is None:
        return
    candle_close = analysis.indicators["close"]
    if (
        check_rsi_bollinger(analysis)
        and not purchases[share["ticker"]].get("order_id", None)
        and (
            (not purchases[share["ticker"]].get("last_sell", None))
            or (
                (datetime.datetime.now() - purchases[share["ticker"]]["last_sell"])
                > datetime.timedelta(hours=2)
            )
        )
    ):
        quantity_lot = int(
            min(10000, purchases["available"]) // (candle_close * share["lot"])
        )
        if quantity_lot > 0:
            async with AsyncClient(Config.NIKITA_TOKEN) as client:
                buy_trade = await buy_limit_order(
                    share["figi"], candle_close, quantity_lot, client
                )
            purchases[share["ticker"]]["order_id"] = buy_trade.order_id
            # purchases["limit_orders"][buy_trade.order_id] = share["ticker"]


async def orders_check_nikita(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        active_orders = await client.orders.get_orders(
            account_id=await get_account_id(client)
        )
        active_orders_dict = {
            active_order.order_id: active_order for active_order in active_orders.orders
        }
        for ticker in purchases.keys():
            order_id = purchases[ticker].get("order_id", None)
            if not order_id or "|" in order_id:
                continue
            analysis = get_analysis(ticker)
            if analysis is None:
                continue
            if order_id in active_orders_dict.keys() and not check_rsi_bollinger(
                analysis
            ):
                order = active_orders_dict[order_id]
                if order.lots_executed > 0:
                    purchase_text = f"Покупка {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nКол-во: {order.lots_executed}"
                    messages_to_send.append(
                        "СТРАТЕГИЯ НИКИТЫ ПОКУПКА\n\n" + purchase_text
                    )
                    take_profit_price = (
                        moneyvalue_to_float(order.average_position_price)
                        * (100 + StrategyConfig.take_profit)
                        / 100
                    )
                    stop_loss_price = (
                        moneyvalue_to_float(order.average_position_price)
                        * (100 - StrategyConfig.stop_los)
                        / 100
                    )
                    take_profit_price -= take_profit_price % 0.02
                    stop_loss_price -= stop_loss_price % 0.02
                    take_profit_response, stop_loss_response = await place_stop_orders(
                        order.figi,
                        take_profit_price,
                        stop_loss_price,
                        order.lots_executed,
                        client,
                    )
                    stop_orders_id_string = (
                        take_profit_response.stop_order_id
                        + "|"
                        + stop_loss_response.stop_order_id,
                    )
                    purchases[ticker]["order_id"] = stop_orders_id_string
                    purchases[ticker]["order_data"] = (
                        purchase_text,
                        take_profit_price,
                        stop_loss_price,
                        order.lots_executed,
                    )
                    purchases["available"] -= moneyvalue_to_float(
                        order.executed_order_price
                    )
                else:
                    messages_to_send.append(
                        f"СТРАТЕГИЯ НИКИТЫ ОТМЕНА\n\nОтмена {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                await client.orders.cancel_order(order.order_id)
        for ticker in purchases.keys():
            order_id = purchases[ticker].get("order_id", None)
            if not order_id or "|" in order_id:
                continue
            order: OrderState = await client.orders.get_order_state(
                account_id=await get_account_id(client), order_id=order_id
            )
            if (
                order.execution_report_status
                == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
            ):
                purchase_text = f"Покупка {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nКол-во: {order.lots_executed}"
                messages_to_send.append("СТРАТЕГИЯ НИКИТЫ ПОКУПКА\n\n" + purchase_text)
                take_profit_price = (
                    moneyvalue_to_float(order.average_position_price)
                    * (100 + StrategyConfig.take_profit)
                    / 100
                )
                stop_loss_price = (
                    moneyvalue_to_float(order.average_position_price)
                    * (100 - StrategyConfig.stop_los)
                    / 100
                )
                take_profit_price -= take_profit_price % 0.02
                stop_loss_price -= stop_loss_price % 0.02
                take_profit_response, stop_loss_response = await place_stop_orders(
                    order.figi,
                    take_profit_price,
                    stop_loss_price,
                    order.lots_executed,
                    client,
                )
                stop_orders_id_string = str(
                    take_profit_response.stop_order_id
                    + "|"
                    + stop_loss_response.stop_order_id,
                )
                purchases[ticker]["order_id"] = stop_orders_id_string
                purchases[ticker]["order_data"] = (
                    purchase_text,
                    take_profit_price,
                    stop_loss_price,
                    order.lots_executed,
                )
                purchases["available"] -= moneyvalue_to_float(
                    order.executed_order_price
                )
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="nikita",
            volume=0,
        )


async def stop_orders_check_nikita(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        active_stop_orders = await client.stop_orders.get_stop_orders(
            account_id=await get_account_id(client)
        )
        active_stop_orders_ids = [
            stop_order.stop_order_id for stop_order in active_stop_orders.stop_orders
        ]
        for ticker in purchases.keys():
            order_id = purchases[ticker].get("order_id", None)
            if not order_id or "|" not in order_id:
                continue
            take_profit_order_id, stop_loss_order_id = order_id.split("|")
            if (
                take_profit_order_id not in active_stop_orders_ids
                or stop_loss_order_id not in active_stop_orders_ids
            ):
                (purchase_text, take_profit_price, stop_loss_price, lots_traded) = (
                    purchases[ticker]["order_data"]
                )
                if take_profit_order_id not in active_stop_orders_ids:
                    await client.orders.cancel_order(stop_loss_order_id)
                    price_sell = take_profit_price
                    profit = lots_traded * (
                        take_profit_price
                        / ((100 + StrategyConfig.take_profit) / 100)
                        * (StrategyConfig.take_profit / 100)
                    )
                    purchases["available"] += lots_traded * take_profit_price
                elif stop_loss_order_id not in active_stop_orders_ids:
                    await client.orders.cancel_order(take_profit_order_id)
                    price_sell = stop_loss_price
                    profit = -lots_traded * (
                        stop_loss_price
                        / ((100 - StrategyConfig.stop_los) / 100)
                        * (StrategyConfig.stop_los / 100)
                    )
                    purchases["available"] += lots_traded * stop_loss_price
                messages_to_send.append(
                    f"СТРАТЕГИЯ НИКИТЫ ПРОДАЖА\n\n{purchase_text}\n\nПродажа {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} по цене {price_sell}\n\nПрибыль: {profit}"
                )
                purchases[ticker]["last_sell"] = datetime.datetime.now()
                purchases[ticker]["order_id"] = None
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="nikita",
            volume=0,
        )


async def market_review_nikita(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        shares = await get_shares(client)
    time_now = datetime.datetime.now()
    if time_now.hour in Config.MOEX_WORKING_HOURS:
        for share in shares:
            if share["ticker"] not in purchases.keys():
                purchases[share["ticker"]] = {}
            await analise_share(share, purchases)
