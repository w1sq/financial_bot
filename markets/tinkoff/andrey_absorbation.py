import datetime
from typing import Optional, List, Dict, Tuple

import asyncio
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle
from tinkoff.invest import (
    OrderState,
    OrderExecutionReportStatus,
)
from tinkoff.invest.exceptions import AioRequestError


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
    take_profit = 1
    stop_loss = 2
    dynamic_border = True  # статичные или динамические границы ордеров
    dynamic_border_mult = 1.25  # насколько двигаем границу, при достижении профита, тут нужны пояснения от Андрея
    falling_indicator_frame_count = 5
    volume = 0  # поизучать
    comission = 0.05  # в процентах
    money_in_order = 10000  # виртуальная сумма для сделки


def get_candle_body_perc(candle: HistoricCandle) -> float:
    if float(quotation_to_decimal(candle.high - candle.low)):
        return (
            100
            * abs(float(quotation_to_decimal(candle.open - candle.close)))
            / float(quotation_to_decimal(candle.high - candle.low))
        )
    else:
        return 0


async def analisys(
    share: dict, current_candle: HistoricCandle, purchases: dict, buy: bool = True
):
    if not purchases[share["ticker"]]:
        purchases[share["ticker"]] = (
            float(quotation_to_decimal(current_candle.open)),
            float(quotation_to_decimal(current_candle.close)),
            get_candle_body_perc(current_candle),
            [float(quotation_to_decimal(current_candle.open))],
        )
        return None
    prev_candle_open, prev_candle_close, prev_candle_body_perc, market_data = purchases[
        share["ticker"]
    ]
    market_data.append(float(quotation_to_decimal(current_candle.open)))

    if len(market_data) > StrategyConfig.falling_indicator_frame_count:
        market_data = market_data[1:]

    current_candle_body_perc = get_candle_body_perc(current_candle)
    falling_market_indicator = falling_indicator(market_data)

    purchases[share["ticker"]] = (
        float(quotation_to_decimal(current_candle.open)),
        float(quotation_to_decimal(current_candle.close)),
        current_candle_body_perc,
        market_data,
    )

    if len(market_data) < StrategyConfig.falling_indicator_frame_count:
        return None

    if (
        (
            (prev_candle_open <= prev_candle_close)
            & (current_candle.open > current_candle.close)
        )
        & (prev_candle_body_perc > 20)
        & (current_candle_body_perc > 20)
    ) & (
        prev_candle_open <= float(quotation_to_decimal(current_candle.open))
    ) & falling_market_indicator and buy and not purchases["orders"][share["ticker"]].get("order_id", None):
        candle_close = float(quotation_to_decimal(current_candle.close))
        quantity_lot = int(
            min(StrategyConfig.money_in_order, purchases["available"])
            // (candle_close * share["lot"])
        )
        if quantity_lot > 0:
            async with AsyncClient(Config.ANDREY_TOKEN) as client:
                buy_trade = await buy_limit_order(
                    share["figi"], candle_close, quantity_lot, client
                )
            purchases["orders"][share["ticker"]]["order_id"] = buy_trade.order_id
            purchases["available"] -= candle_close * quantity_lot * share["lot"]
            return f"СТРАТЕГИЯ АНДРЕЯ ЗАЯВКА\n\nЗаявка на {share['ticker']} {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} по цене {candle_close}\nКол-во: {quantity_lot * share['lot']}"
    return None


# индикатор того, что рынок до появления сигнала - падающий
def falling_indicator(input_list: List[float]) -> bool:
    return (
        sum(input_list) / len(input_list) >= input_list[-1]
    )  # рынок "падающий" - если текущая цена ниже среднего за falling_indicator_frame_count дней


async def fill_market_data_andrey(purchases: dict):
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        shares = await get_shares(client)
        now_time = datetime.datetime.combine(
            datetime.datetime.now(datetime.UTC).replace(tzinfo=datetime.timezone.utc),
            datetime.time(6, 0),
        ).replace(tzinfo=datetime.timezone.utc)
        for share in shares:
            if share["ticker"] not in purchases["orders"].keys():
                purchases["orders"][share["ticker"]] = {
                    "min_price_increment": share["min_price_increment"]
                }
        for share in shares:
            async for candle in client.get_all_candles(
                figi=share["figi"],
                from_=now_time - datetime.timedelta(days=10),
                to=now_time - datetime.timedelta(days=2),
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                await analisys(share, candle, purchases, buy=False)


async def orders_check_andrey(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        for ticker in purchases["orders"].keys():
            order_id = purchases["orders"][ticker].get("order_id", None)
            if not order_id or "|" in order_id:
                continue
            order: OrderState = await client.orders.get_order_state(
                account_id=await get_account_id(client), order_id=order_id
            )
            if (
                order.execution_report_status
                == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
            ):
                if order.lots_executed > 0:
                    purchase_text = f"Покупка {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nКол-во: {order.lots_executed}"
                    messages_to_send.append(
                        "СТРАТЕГИЯ АНДРЕЯ ПОКУПКА\n\n" + purchase_text
                    )
                    take_profit_price = moneyvalue_to_float(
                        order.average_position_price
                    ) * (1 + StrategyConfig.take_profit / 100)
                    stop_loss_price = moneyvalue_to_float(
                        order.average_position_price
                    ) * (1 - StrategyConfig.stop_loss / 100)
                    take_profit_price -= (
                        take_profit_price
                        % purchases["orders"][ticker]["min_price_increment"]
                    )
                    stop_loss_price -= (
                        stop_loss_price
                        % purchases["orders"][ticker]["min_price_increment"]
                    )
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
                    purchases["orders"][ticker]["order_id"] = stop_orders_id_string
                    purchases["orders"][ticker]["order_data"] = (
                        purchase_text,
                        take_profit_price,
                        stop_loss_price,
                        order.lots_executed,
                    )
                    # purchases["available"] -= moneyvalue_to_float(
                    #     order.executed_order_price
                    # )
                else:
                    messages_to_send.append(
                        f"СТРАТЕГИЯ АНДРЕЯ ОТМЕНА\n\nОтмена {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                if (
                    order.execution_report_status
                    != OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
                ):
                    try:
                        await client.orders.cancel_order(
                            account_id=await get_account_id(client),
                            order_id=order.order_id,
                        )
                    except AioRequestError as e:
                        print(e)
                    purchases["orders"][ticker]["order_id"] = None
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="andrey",
            volume=0,
        )


async def stop_orders_check_andrey(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        active_stop_orders = await client.stop_orders.get_stop_orders(
            account_id=str(await get_account_id(client))
        )
        active_stop_orders_ids = [
            stop_order.stop_order_id for stop_order in active_stop_orders.stop_orders
        ]
        for ticker in purchases["orders"].keys():
            order_id = purchases["orders"][ticker].get("order_id", None)
            if not order_id or "|" not in order_id:
                continue
            take_profit_order_id, stop_loss_order_id = order_id.split("|")
            if (
                take_profit_order_id not in active_stop_orders_ids
                or stop_loss_order_id not in active_stop_orders_ids
            ):
                (purchase_text, take_profit_price, stop_loss_price, lots_traded) = (
                    purchases["orders"][ticker]["order_data"]
                )
                if (
                    take_profit_order_id not in active_stop_orders_ids
                    and stop_loss_order_id in active_stop_orders_ids
                ):
                    try:
                        await client.stop_orders.cancel_stop_order(
                            account_id=await get_account_id(client),
                            stop_order_id=stop_loss_order_id,
                        )
                    except AioRequestError as e:
                        print(e)
                    price_sell = take_profit_price
                    price_buy = take_profit_price / (
                        1 + StrategyConfig.take_profit / 100
                    )
                    profit = lots_traded * (price_sell - price_buy)
                elif (
                    stop_loss_order_id not in active_stop_orders_ids
                    and take_profit_order_id in active_stop_orders_ids
                ):
                    try:
                        await client.stop_orders.cancel_stop_order(
                            account_id=await get_account_id(client),
                            stop_order_id=take_profit_order_id,
                        )
                    except AioRequestError as e:
                        print(e)
                    price_sell = stop_loss_price
                    price_buy = stop_loss_price / (1 - StrategyConfig.stop_loss / 100)
                    profit = -lots_traded * (price_sell - price_buy)
                purchases["available"] += lots_traded * price_sell
                messages_to_send.append(
                    f"СТРАТЕГИЯ АНДРЕЯ ПРОДАЖА\n\n{purchase_text}\n\nПродажа {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} по цене {price_sell}\n\nПрибыль: {round(profit, 2)}"
                )
                purchases["orders"][ticker]["order_id"] = None
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="andrey",
            volume=0,
        )


async def market_review_andrey(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        shares = await get_shares(client)
        messages_to_send = []
        for share in shares:
            async for candle in client.get_all_candles(
                figi=share["figi"],
                from_=now() - datetime.timedelta(days=1),
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                message = await analisys(share, candle, purchases)
                if message is not None:
                    messages_to_send.append(message)
        for message in messages_to_send:
            await tg_bot.send_signal(
                message=message,
                strategy="andrey",
                volume=0,
            )
