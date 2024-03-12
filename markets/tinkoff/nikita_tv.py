import datetime
from typing import Optional, List, Dict


from tinkoff.invest import AsyncClient
from tradingview_ta import TA_Handler, Interval

# import tinkoff
# from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import (
    CandleInterval,
    HistoricCandle,
    OrderState,
    OrderExecutionReportStatus,
    StopOrder,
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


async def bollinger_and_rsi_data(share: dict, purchases: dict):
    analysis = get_analysis(share["ticker"])
    if analysis is None:
        return

    candle_close = analysis.indicators["close"]
    avarege = (analysis.indicators["BB.lower"] + analysis.indicators["BB.upper"]) / 2
    sko = (avarege - analysis.indicators["BB.lower"]) / 2
    rsi = analysis.indicators["RSI"]  # https://pastebin.com/1DjWv2Hd
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
            min(3000, purchases["available"]) // (candle_close * share["lot"])
        )
        if quantity_lot > 0:
            # purchase = {
            #     "date_buy": analysis.time.strftime("%d-%m-%Y %H:%M"),
            #     "date_sell": "-",
            #     "price_sell": "-",
            #     "profit": "-",
            # }
            # purchase["ticker"] = share["ticker"]
            # purchases[share["ticker"]] = purchase
            # purchase["type"] = 1
            buy_trade = await buy_limit_order(
                share["figi"], candle_close, quantity_lot, Config.NIKITA_TOKEN
            )
            # purchase["quantity"] = buy_trade.lots_executed * share["lot"]
            # purchase["price_buy"] = moneyvalue_to_float(buy_trade.executed_order_price)
            # purchase["buy_commission"] = moneyvalue_to_float(
            #     buy_trade.initial_commission
            # )
            purchases["limit_orders"][buy_trade.order_id] = share["ticker"]
            # purchases["available"] -= quantity_lot * candle_close
            # return purchase
    # elif purchases.get(share["ticker"], None):
    #     purchase = purchases[share["ticker"]]
    #     if not purchase.get("price_buy", None):
    #         purchases.pop(share["ticker"])
    #     candle_open = analysis.indicators["open"]
    #     if (
    #         (
    #             candle_open
    #             > float(purchase["price_buy"])
    #             * (100 + StrategyConfig.take_profit)
    #             / 100
    #         )
    #         or (
    #             candle_open
    #             < float(purchase["price_buy"]) * (100 - StrategyConfig.stop_los) / 100
    #         )
    #     ) and purchase["profit"] == "-":
    #         purchase["date_sell"] = analysis.time.strftime("%d-%m-%Y %H:%M")
    #         purchases[share["ticker"]] = {}
    #         purchase["type"] = 2
    #         sell_trade = await trade_by_ticker(
    #             share["ticker"],
    #             2,
    #             int(purchase["quantity"] / share["lot"]),
    #             Config.NIKITA_TOKEN,
    #         )
    #         purchase["price_sell"] = moneyvalue_to_float(
    #             sell_trade.executed_order_price
    #         )
    #         purchase["sell_commission"] = moneyvalue_to_float(
    #             sell_trade.initial_commission
    #         )
    #         purchase["profit"] = (
    #             purchase["price_sell"]
    #             - purchase["price_buy"]
    #             - purchase["sell_commission"]
    #             - purchase["buy_commission"]
    #         ) * purchase["quantity"]
    #         purchases["available"] += (
    #             purchase["quantity"] * purchase["price_sell"]
    #             - purchase["sell_commission"]
    #         )
    #         return purchase
    # return None


async def send_message(tg_bot: TG_Bot, trade: Dict):
    if trade["type"] == 2:
        message_text = f"СТРАТЕГИЯ НИКИТЫ ПРОДАЖА\n\nПокупка {trade['ticker']} {trade['date_buy']} по цене {trade['price_buy']} с начальной коммисией {trade['buy_commission']}\nКол-во: {trade['quantity']}\n\nПродажа {trade['date_sell']} по цене {trade['price_sell']} с коммисией {trade['sell_commission']}\n\nПрибыль: {trade['profit']}"
    else:
        message_text = f"СТРАТЕГИЯ НИКИТЫ ПОКУПКА\n\nПокупка {trade['ticker']} {trade['date_buy']} по цене {trade['price_buy']} с начальной коммисией {trade['buy_commission']}\nКол-во: {trade['quantity']}"
    await tg_bot.send_signal(
        message=message_text,
        strategy="nikita",
        volume=0,
    )


async def orders_check_nikita(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        active_orders: List[OrderState] = await client.orders.get_orders(
            await get_account_id(client)
        )
        local_orders_id = purchases["limit_orders"].keys()
        max_timestamp = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(seconds=59)
        for order in active_orders:
            ticker = purchases["limit_orders"][order.order_id]
            if order.order_id in local_orders_id and order.order_date > max_timestamp:
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
                    take_profit_response, stop_loss_response = await place_stop_orders(
                        order.figi,
                        take_profit_price,
                        stop_loss_price,
                        order.lots_executed,
                        client,
                    )
                    stop_orders_id_tuple = (
                        take_profit_response.stop_order_id,
                        stop_loss_response.stop_order_id,
                    )
                    purchases["stop_orders"][stop_orders_id_tuple] = (
                        purchase_text,
                        take_profit_price,
                        stop_loss_price,
                        order.lots_executed,
                    )
                    purchases["available"] -= order.executed_order_price
                else:
                    messages_to_send.append(
                        f"СТРАТЕГИЯ НИКИТЫ ОТМЕНА\n\nОтмена {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                await client.orders.cancel_order(order.order_id)
                purchases["limit_orders"].pop(order.order_id)
        local_orders_id = purchases["limit_orders"].keys()
        for local_order_id in local_orders_id:
            order: OrderState = await client.orders.get_order_state(
                await get_account_id(client), local_order_id
            )
            if (
                order.execution_report_status
                == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
            ):
                ticker = purchases["limit_orders"][order.order_id]
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
                take_profit_response, stop_loss_response = await place_stop_orders(
                    order.figi,
                    take_profit_price,
                    stop_loss_price,
                    order.lots_executed,
                    client,
                )
                stop_orders_id_tuple = (
                    take_profit_response.stop_order_id,
                    stop_loss_response.stop_order_id,
                )
                purchases["stop_orders"][stop_orders_id_tuple] = (
                    purchase_text,
                    take_profit_price,
                    stop_loss_price,
                    order.lots_executed,
                )
                purchases["limit_orders"].pop(order.order_id)
                purchases["available"] -= order.executed_order_price
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="nikita",
            volume=0,
        )


async def stop_orders_check_nikita(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        active_stop_orders: List[StopOrder] = await client.stop_orders.get_stop_orders(
            await get_account_id(client)
        )
        active_stop_orders_ids = [
            stop_order.stop_order_id for stop_order in active_stop_orders
        ]
        local_stop_orders_id = purchases["stop_orders"].keys()
        for take_profit_order_id, stop_loss_order_id in local_stop_orders_id:
            (purchase_text, take_profit_price, stop_loss_price, lots_traded) = (
                purchases["stop_order"][(take_profit_order_id, stop_loss_order_id)]
            )
            if (
                take_profit_order_id not in active_stop_orders_ids
                or stop_loss_order_id not in active_stop_orders_ids
            ):
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
                purchases["stop_orders"].pop((take_profit_order_id, stop_loss_order_id))
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
            trade = await bollinger_and_rsi_data(share, purchases)
            # if trade is not None:
            #     await send_message(tg_bot, trade)
