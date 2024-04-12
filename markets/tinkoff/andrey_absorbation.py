import datetime
from typing import Optional, List, Dict, Tuple

import asyncio
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle
from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest import (
    OrderState,
    OrderExecutionReportStatus,
    OperationType,
    OperationState,
)
from tinkoff.invest.exceptions import AioRequestError


from bot import TG_Bot
from config import Config
from markets.tinkoff.candle_model import CustomCandle
from markets.tinkoff.utils import (
    get_shares,
    buy_market_order,
    place_stop_orders,
    moneyvalue_to_float,
    get_account_id,
    get_history,
)


class StrategyConfig:
    take_profit = 2.5  # 2,
    stop_loss = 0.5  # 0.5
    dynamic_border = True  # статичные или динамические границы ордеров .. идея на потом
    # dynamic_border_mult 2,  # 1.25, # насколько двигаем границу, при достижении профита, .. идея на потом
    falling_indicator_frame_count = 5
    volume = 0  # поизучать
    comission = 0.05  # в процентах
    short_comission = 0.06  # или 0.07, комиссия ежедневная
    money_in_order = 10000  # виртуальная сумма для сделки
    # параметры для Бычьего и Медвежьего поглощения
    first_candle_perc_ba_and_ba = 1
    second_candle_perc_ba_and_ba = 1.5
    body_perc_ba_and_ba = 55  # 70  # 55
    # параметры для Темных облаков и Пронзающей свечи
    first_candle_perc_pc_and_dc = 1.5
    second_candle_perc_pc_and_dc = 1.5
    body_perc_pc_and_dc = 55  # 70  # 55
    # параметры для Бычьего и Медвежьего перекрестия
    first_candle_perc_bс_and_bс = 1  # 1.2 1.5
    second_candle_perc_bс_and_bс = 1.5
    body_perc_bс_and_bс = 55  # 70  # 55
    # параметры для молота и падающей звезды
    hammer_candle_length_perc = 1.5
    hammer_low_shadow_perc = 75
    hammer_body_perc = 10
    star_candle_length_perc = 1.5
    star_high_shadow_perc = 75
    star_body_perc = 10


def get_candle_body_perc(candle: HistoricCandle) -> float:
    if float(quotation_to_decimal(candle.high - candle.low)):
        return (
            100
            * abs(float(quotation_to_decimal(candle.open - candle.close)))
            / float(quotation_to_decimal(candle.high - candle.low))
        )
    else:
        return 0


last_candles = {}


async def analisys(
    share: dict, current_candle: HistoricCandle, purchases: dict, buy: bool = True
):
    current_custom_candle = CustomCandle(current_candle)
    if not last_candles.get(share["ticker"]):
        last_candles[share["ticker"]] = [current_custom_candle]
        return None

    prev_custom_candle = last_candles[share["ticker"]][-1]
    last_candles[share["ticker"]].append(current_custom_candle)

    if (
        len(last_candles[share["ticker"]])
        < StrategyConfig.falling_indicator_frame_count
    ):
        return None
    elif (
        len(last_candles[share["ticker"]])
        > StrategyConfig.falling_indicator_frame_count
    ):
        last_candles[share["ticker"]] = last_candles[share["ticker"]][1:]

    falling_market_indicator = falling_indicator(last_candles[share["ticker"]])
    # print(share["ticker"], current_custom_candle.open, prev_custom_candle.open)я

    async def create_order(order_candle: CustomCandle):
        if (
            prev_custom_candle.volume
            * share["lot"]
            * (prev_custom_candle.low + prev_custom_candle.length / 2)
        ) > 100 * 10**6:
            print(
                order_candle.time.strftime("%Y-%m-%d"),
                share["ticker"],
                order_candle.type,
            )
        quantity_lot = int(
            min(StrategyConfig.money_in_order, purchases["available"])
            // (order_candle.close * share["lot"])
        )
        if (
            quantity_lot > 0
            and buy
            and (
                prev_custom_candle.volume
                * share["lot"]
                * (prev_custom_candle.low + prev_custom_candle.length / 2)
            )
            > 100 * 10**6
        ):
            order_candle.close -= order_candle.close % share["min_price_increment"]
            async with AsyncRetryingClient(
                Config.ANDREY_TOKEN, Config.RETRY_SETTINGS
            ) as client:
                buy_trade = await buy_market_order(share["figi"], quantity_lot, client)
            purchases["orders"][share["ticker"]]["order_id"] = buy_trade.order_id
            purchases["available"] -= order_candle.close * quantity_lot * share["lot"]
            return f"СТРАТЕГИЯ АНДРЕЯ ЗАЯВКА {order_candle.type} ЛОНГ\n\nЗаявка на {share['name']}\n{share['ticker']} {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} по цене {order_candle.close}\nКол-во : {quantity_lot * share['lot']}"

    async def create_short_order(order_candle: CustomCandle):
        if (
            prev_custom_candle.volume
            * share["lot"]
            * (prev_custom_candle.low + prev_custom_candle.length / 2)
        ) > 100 * 10**6:
            print(
                order_candle.time.strftime("%Y-%m-%d"),
                share["ticker"],
                order_candle.type,
            )
            # quantity_lot = int(
            #     min(StrategyConfig.money_in_order, purchases["available"])
            #     // (order_candle.close * share["lot"])
            # )
            # if (
            #     quantity_lot > 0
            #     and buy
            #     and (
            #         prev_custom_candle.volume
            #         * share["lot"]
            #         * (prev_custom_candle.low + prev_custom_candle.length / 2)
            #     )
            #     > 100 * 10**6
            # ):
            #     order_candle.close -= order_candle.close % share["min_price_increment"]
            # async with AsyncRetryingClient(
            #     Config.ANDREY_TOKEN, Config.RETRY_SETTINGS
            # ) as client:
            #     buy_trade = await buy_market_order(share["figi"], quantity_lot, client)
            # purchases["orders"][share["ticker"]]["order_id"] = buy_trade.order_id
            # purchases["available"] -= order_candle.close * quantity_lot * share["lot"]
            # return f"СТРАТЕГИЯ АНДРЕЯ ЗАЯВКА {order_candle.type}\n\nЗаявка на {share['name']}\n{share['ticker']} {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} по цене {order_candle.close}\nКол-во: {quantity_lot * share['lot']}"

    if (
        (prev_custom_candle.color == "red")
        & (current_custom_candle.color == "green")
        & (prev_custom_candle.length_perc >= StrategyConfig.first_candle_perc_pc_and_dc)
        & (
            current_custom_candle.length_perc
            >= StrategyConfig.second_candle_perc_pc_and_dc
        )
        & (prev_custom_candle.body_perc > StrategyConfig.body_perc_pc_and_dc)
        & (current_custom_candle.body_perc > StrategyConfig.body_perc_pc_and_dc)
        & (prev_custom_candle.high > current_custom_candle.close)
        & (prev_custom_candle.low > current_custom_candle.open)
        & (prev_custom_candle.close < current_custom_candle.close)
        & (falling_market_indicator)
    ):
        current_custom_candle.type = "ПРОНЗАЮЩАЯ СВЕЧА"
        return await create_order(current_custom_candle)
    # вход в шорт двухдневная модель "Тёмные облака"
    elif (
        (prev_custom_candle.color == "green")
        & (current_custom_candle.color == "red")
        & (prev_custom_candle.length_perc >= StrategyConfig.first_candle_perc_pc_and_dc)
        & (
            current_custom_candle.length_perc
            >= StrategyConfig.second_candle_perc_pc_and_dc
        )
        & (prev_custom_candle.body_perc >= StrategyConfig.body_perc_pc_and_dc)
        & (current_custom_candle.body_perc >= StrategyConfig.body_perc_pc_and_dc)
        & (prev_custom_candle.high < current_custom_candle.open)
        & (prev_custom_candle.low < current_custom_candle.close)
        & (prev_custom_candle.close > current_custom_candle.close)
        & (not falling_market_indicator)
    ):
        current_custom_candle.type = "Тёмные облака"
        return await create_short_order(current_custom_candle)
    # вход в лонг двухдневная модель "Бычье поглощение"
    elif (
        (prev_custom_candle.color == "red")
        & (current_custom_candle.color == "green")
        & (prev_custom_candle.length_perc >= StrategyConfig.first_candle_perc_ba_and_ba)
        & (
            current_custom_candle.length_perc
            >= StrategyConfig.second_candle_perc_ba_and_ba
        )
        & (prev_custom_candle.body_perc > StrategyConfig.body_perc_ba_and_ba)
        & (current_custom_candle.body_perc > StrategyConfig.body_perc_ba_and_ba)
        & (prev_custom_candle.high < current_custom_candle.close)
        & (prev_custom_candle.low > current_custom_candle.open)
        & (falling_market_indicator)
    ):
        current_custom_candle.type = "БЫЧЬЕ ПОГЛОЩЕНИЕ"
        return await create_order(current_custom_candle)
    # вход в шорт двухдневная модель "Медвежье поглощение"
    elif (
        (prev_custom_candle.color == "green")
        & (current_custom_candle.color == "red")
        & (prev_custom_candle.length_perc >= StrategyConfig.first_candle_perc_ba_and_ba)
        & (
            current_custom_candle.length_perc
            >= StrategyConfig.second_candle_perc_ba_and_ba
        )
        & (prev_custom_candle.body_perc > StrategyConfig.body_perc_ba_and_ba)
        & (current_custom_candle.body_perc > StrategyConfig.body_perc_ba_and_ba)
        & (prev_custom_candle.high < current_custom_candle.open)
        & (prev_custom_candle.low > current_custom_candle.close)
        & (not falling_market_indicator)
    ):
        current_custom_candle.type = "МЕДВЕЖЬЕ ПОГЛОЩЕНИЕ"
        return await create_short_order(current_custom_candle)
    # вход в лонг двухдневная модель "Бычье перекрытие"
    elif (
        (prev_custom_candle.color == "red")
        & (current_custom_candle.color == "green")
        & (prev_custom_candle.length_perc >= StrategyConfig.first_candle_perc_bс_and_bс)
        & (
            current_custom_candle.length_perc
            >= StrategyConfig.second_candle_perc_bс_and_bс
        )
        & (prev_custom_candle.body_perc > StrategyConfig.body_perc_bс_and_bс)
        & (current_custom_candle.body_perc > StrategyConfig.body_perc_bс_and_bс)
        & (prev_custom_candle.high < current_custom_candle.close)
        & (prev_custom_candle.close > current_custom_candle.open)
        & (falling_market_indicator)
    ):
        current_custom_candle.type = "БЫЧЬЕ ПЕРЕКРЫТИЕ"
        return await create_order(current_custom_candle)
    # вход в шорт двухдневная модель Медвежье перекрытие
    elif (
        (prev_custom_candle.color == "green")
        & (current_custom_candle.color == "red")
        & (prev_custom_candle.length_perc >= StrategyConfig.first_candle_perc_bс_and_bс)
        & (
            current_custom_candle.length_perc
            >= StrategyConfig.second_candle_perc_bс_and_bс
        )
        & (prev_custom_candle.body_perc > StrategyConfig.body_perc_bс_and_bс)
        & (current_custom_candle.body_perc > StrategyConfig.body_perc_bс_and_bс)
        & (prev_custom_candle.close < current_custom_candle.open)
        & (prev_custom_candle.open > current_custom_candle.close)
        & (not falling_market_indicator)
    ):
        current_custom_candle.type = "МЕДВЕЖЬЕ ПЕРЕКРЫТИЕ"
        return await create_short_order(current_custom_candle)
    # вход в лонг модель однодневный молот
    if (
        (current_custom_candle.color == "green")
        & (
            current_custom_candle.length_perc
            >= StrategyConfig.hammer_candle_length_perc
        )
        & (
            current_custom_candle.low_shadow_perc
            >= StrategyConfig.hammer_low_shadow_perc
        )
        & (current_custom_candle.body_perc > StrategyConfig.hammer_body_perc)
        & (falling_market_indicator)
    ):
        current_custom_candle.type = "ОДНОДНЕВНЫЙ МОЛОТ"
        return await create_order(current_custom_candle)
    # вход в шорт модель однодневная падающая звезда
    elif (
        (current_custom_candle.color == "red")
        & (current_custom_candle.length_perc >= StrategyConfig.star_candle_length_perc)
        & (
            current_custom_candle.high_shadow_perc
            >= StrategyConfig.star_high_shadow_perc
        )
        & (current_custom_candle.body_perc > StrategyConfig.star_body_perc)
        & (not falling_market_indicator)
    ):
        current_custom_candle.type = "ОДНОДНЕВНАЯ ПАДАЮЩАЯ ЗВЕЗДА"
        return await create_short_order(current_custom_candle)
    return None


# индикатор того, что рынок до появления сигнала - падающий
def falling_indicator(input_list: List[CustomCandle]) -> bool:
    opens_list = [candle.open for candle in input_list]
    return (
        sum(opens_list) / len(opens_list) >= opens_list[-1]
    )  # рынок "падающий" - если текущая цена ниже среднего за falling_indicator_frame_count дней


async def fill_market_data_andrey(purchases: dict):
    async with AsyncRetryingClient(
        Config.ANDREY_TOKEN, Config.RETRY_SETTINGS
    ) as client:
        shares = await get_shares(client)
        now_time = datetime.datetime.combine(
            datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
            datetime.time(6, 0),
        ).replace(tzinfo=datetime.timezone.utc)
        for share in shares:
            if share["ticker"] not in purchases["orders"].keys():
                purchases["orders"][share["ticker"]] = {
                    "min_price_increment": share["min_price_increment"],
                    "lots": share["lot"],
                    "figi": share["figi"],
                }
            elif "figi" not in purchases["orders"][share["ticker"]].keys():
                purchases["orders"][share["ticker"]]["figi"] = share["figi"]
        for share in shares:
            async for candle in client.get_all_candles(
                figi=share["figi"],
                from_=now_time - datetime.timedelta(days=15),
                to=now_time - datetime.timedelta(days=2),
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                await analisys(share, candle, purchases, buy=False)


async def orders_check_andrey(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncRetryingClient(
        Config.ANDREY_TOKEN, Config.RETRY_SETTINGS
    ) as client:
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
                    purchase_text = f"Покупка {ticker} ЛОНГ {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nОбщий объем сделки: {moneyvalue_to_float(order.total_order_amount)}\nКол-во бумаг: {order.lots_executed*purchases['orders'][ticker]['lots']}\nКол-во лотов: {order.lots_executed}\nСтоп-лосс: {stop_loss_price}\nТейк-профит: {take_profit_price}"
                    messages_to_send.append(
                        "СТРАТЕГИЯ АНДРЕЯ ПОКУПКА\n\n" + purchase_text
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
    async with AsyncRetryingClient(
        Config.ANDREY_TOKEN, Config.RETRY_SETTINGS
    ) as client:
        last_trades = await get_history(client)
        if not last_trades:
            return None
        # active_stop_orders = await client.stop_orders.get_stop_orders(
        #     account_id=str(await get_account_id(client))
        # )
        # active_stop_orders_ids = [
        #     stop_order.stop_order_id for stop_order in active_stop_orders.stop_orders
        # ]
        for ticker in purchases["orders"].keys():
            order_id = purchases["orders"][ticker].get("order_id")
            figi = purchases["orders"][ticker].get("figi")
            if not order_id or "|" not in order_id:
                continue
            take_profit_order_id, stop_loss_order_id = order_id.split("|")
            for last_trade in last_trades:
                if (
                    last_trade.figi == figi
                    and last_trade.operation_type == OperationType.OPERATION_TYPE_SELL
                    and last_trade.state == OperationState.OPERATION_STATE_EXECUTED
                ):
                    (purchase_text, take_profit_price, stop_loss_price, lots_traded) = (
                        purchases["orders"][ticker]["order_data"]
                    )
                    sell_price = moneyvalue_to_float(last_trade.price)
                    if abs(sell_price - take_profit_price) < abs(
                        sell_price - stop_loss_price
                    ):
                        try:
                            await client.stop_orders.cancel_stop_order(
                                account_id=await get_account_id(client),
                                stop_order_id=stop_loss_order_id,
                            )
                        except AioRequestError as e:
                            print(e)
                        price_buy = take_profit_price / (
                            1 + StrategyConfig.take_profit / 100
                        )
                    else:
                        try:
                            await client.stop_orders.cancel_stop_order(
                                account_id=await get_account_id(client),
                                stop_order_id=take_profit_order_id,
                            )
                        except AioRequestError as e:
                            print(e)
                        price_buy = stop_loss_price / (
                            1 - StrategyConfig.stop_loss / 100
                        )
                        profit = lots_traded * (sell_price - price_buy)
                    purchases["available"] += moneyvalue_to_float(last_trade.payment)
                    messages_to_send.append(
                        f"СТРАТЕГИЯ АНДРЕЯ ПРОДАЖА\n\n{purchase_text}\n\nПродажа ЛОНГ {last_trade.date.strftime('%Y-%m-%d %H:%M')}\nКоличество: {last_trade.quantity}\nЦена выхода: {sell_price}\nЦена входа: {price_buy}\n\nПрибыль: {round(profit, 2)}"
                    )
                    purchases["orders"][ticker]["order_id"] = None
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="andrey",
            volume=0,
        )


async def market_review_andrey(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    async with AsyncRetryingClient(
        Config.ANDREY_TOKEN, Config.RETRY_SETTINGS
    ) as client:
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
