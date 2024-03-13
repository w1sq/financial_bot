import datetime
from typing import Optional, List, Dict, Tuple

import asyncio
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle
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
    take_profit = 1
    stop_los = 2
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


async def analisys(
    share: str, current_candle: HistoricCandle, purchases: dict, buy: bool = True
) -> Optional[Dict]:
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

    if len(market_data) < StrategyConfig.falling_indicator_frame_count:
        return None

    if len(market_data) > StrategyConfig.falling_indicator_frame_count:
        market_data = market_data[1:]

    purchases[share["ticker"]] = (
        float(quotation_to_decimal(current_candle.open)),
        float(quotation_to_decimal(current_candle.close)),
        get_candle_body_perc(current_candle),
        market_data,
    )

    current_candle_body_perc = get_candle_body_perc(current_candle)
    falling_market_indicator = falling_indicator(market_data)
    if (
        (
            (prev_candle_open <= prev_candle_close)
            & (current_candle.open > current_candle.close)
        )
        & (prev_candle_body_perc > 20)
        & (current_candle_body_perc > 20)
    ) & (
        prev_candle_open <= float(quotation_to_decimal(current_candle.open))
    ) & falling_market_indicator and buy:
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
            purchases["limit_orders"][buy_trade.order_id] = share["ticker"]
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
            datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
            datetime.time(6, 0),
        ).replace(tzinfo=datetime.timezone.utc)
        for share in shares:
            purchases[share["ticker"]] = ()
        for share in shares:
            async for candle in client.get_all_candles(
                figi=share["figi"],
                from_=now_time - datetime.timedelta(days=7),
                to=now_time - datetime.timedelta(days=1),
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                await analisys(share, candle, purchases, buy=False)


async def orders_check_andrey(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        active_orders = await client.orders.get_orders(
            account_id=await get_account_id(client)
        )
        local_orders_id = purchases["limit_orders"].keys()
        max_timestamp = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(minutes=59)
        for order in active_orders.orders:
            ticker = purchases["limit_orders"][order.order_id]
            if order.order_id in local_orders_id and order.order_date > max_timestamp:
                if order.lots_executed > 0:
                    purchase_text = f"Покупка {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nКол-во: {order.lots_executed}"
                    messages_to_send.append(
                        "СТРАТЕГИЯ АНДРЕЯ ПОКУПКА\n\n" + purchase_text
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
                    purchases["stop_orders"][stop_orders_id_string] = (
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
                        f"СТРАТЕГИЯ АНДРЕЯ ОТМЕНА\n\nОтмена {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                await client.orders.cancel_order(order.order_id)
                purchases["limit_orders"].pop(order.order_id)
        local_orders_id = purchases["limit_orders"].keys()
        for local_order_id in local_orders_id:
            order: OrderState = await client.orders.get_order_state(
                account_id=await get_account_id(client), order_id=local_order_id
            )
            if (
                order.execution_report_status
                == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
            ):
                ticker = purchases["limit_orders"][order.order_id]
                purchase_text = f"Покупка {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nКол-во: {order.lots_executed}"
                messages_to_send.append("СТРАТЕГИЯ АНДРЕЯ ПОКУПКА\n\n" + purchase_text)
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
                purchases["stop_orders"][stop_orders_id_string] = (
                    purchase_text,
                    take_profit_price,
                    stop_loss_price,
                    order.lots_executed,
                )
                purchases["limit_orders"].pop(order.order_id)
                purchases["available"] -= moneyvalue_to_float(
                    order.executed_order_price
                )
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="adnrey",
            volume=0,
        )


async def stop_orders_check_andrey(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        active_stop_orders = await client.stop_orders.get_stop_orders(
            account_id=await get_account_id(client)
        )
        active_stop_orders_ids = [
            stop_order.stop_order_id for stop_order in active_stop_orders.stop_orders
        ]
        local_stop_orders_id = purchases["stop_orders"].keys()
        for stop_orders_id_string in local_stop_orders_id:
            take_profit_order_id, stop_loss_order_id = stop_orders_id_string.split("|")
            (purchase_text, take_profit_price, stop_loss_price, lots_traded) = (
                purchases["stop_orders"][stop_orders_id_string]
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
                    f"СТРАТЕГИЯ АНДРЕЯ ПРОДАЖА\n\n{purchase_text}\n\nПродажа {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} по цене {price_sell}\n\nПрибыль: {profit}"
                )
                purchases["stop_orders"].pop(stop_orders_id_string)
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="andrey",
            volume=0,
        )


async def market_review_andrey(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        shares = await get_shares(client)
        time_now = datetime.datetime.now()
        if time_now.hour in Config.MOEX_WORKING_HOURS:
            for share in shares:
                async for candle in client.get_all_candles(
                    figi=share["figi"],
                    from_=now() - datetime.timedelta(days=1),
                    interval=CandleInterval.CANDLE_INTERVAL_DAY,
                ):
                    await analisys(share, candle, purchases)
