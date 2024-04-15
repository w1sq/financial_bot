import datetime
from typing import List, Dict, Tuple


import pandas
import numpy
from tinkoff.invest import AsyncClient, HistoricCandle, CandleInterval
from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest.exceptions import AioRequestError
from tinkoff.invest.async_services import AsyncServices

from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    OrderState,
    OrderExecutionReportStatus,
    OperationType,
    OperationState,
)


from bot import TG_Bot
from config import Config
from markets.tinkoff.utils import (
    get_shares,
    buy_limit_order,
    place_sell_stop_orders,
    moneyvalue_to_float,
    get_account_id,
    get_last_price,
    get_history,
)


class StrategyConfig:
    bolinger_mult = 2
    bollinger_frame_count = 20
    rsi_count_frame = 14  # 14 actually
    strategy_bollinger_range = 1.5
    rsi_treshold = 30
    take_profit = 0.4
    stop_loss = 1


data_bollinger: Dict[str, List[float]] = {}
data_rsi: Dict[str, List[float]] = {}


def calculate_bollinger_bands(data: pandas.Series, window=20) -> Tuple[float, float]:
    sma = data.rolling(window=window).mean()
    std = data.rolling(window=window).std()
    return sma.iloc[-1], std.iloc[-1]


def calculate_rsi(data: pandas.Series, period=StrategyConfig.rsi_count_frame) -> float:
    delta = data.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


def strategy(last_price: float, ticker: str) -> bool:
    local_data_bollinger = data_bollinger[ticker]
    local_data_rsi = data_rsi[ticker]
    avarege, sko = calculate_bollinger_bands(pandas.Series(local_data_bollinger))
    if len(local_data_rsi) < StrategyConfig.rsi_count_frame:
        return False
    rsi = calculate_rsi(pandas.Series(local_data_rsi))
    # if rsi < 30:
    #     print("rsi", rsi)
    if (
        last_price
        < (
            avarege
            - StrategyConfig.bolinger_mult
            * sko
            * StrategyConfig.strategy_bollinger_range
        )
        and rsi <= StrategyConfig.rsi_treshold
    ):
        return True
    return False


async def analise_share(share: dict, purchases: dict, client: AsyncServices):
    local_data_bollinger = data_bollinger.get(share["ticker"])
    local_data_rsi = data_rsi.get(share["ticker"])
    if not local_data_bollinger or not local_data_rsi:
        return None
    try:
        last_price = await get_last_price(share["figi"], client)
    except AioRequestError as e:
        print(e)
        return None
    share_status = False
    if datetime.datetime.now().minute == 30:
        if len(local_data_bollinger) < StrategyConfig.bollinger_frame_count:
            local_data_bollinger.append(last_price)
        else:
            local_data_bollinger.pop(0)
            local_data_bollinger.append(last_price)
            share_status = strategy(last_price, share["ticker"])
        if len(local_data_rsi) < StrategyConfig.rsi_count_frame:
            local_data_rsi.append(last_price)
        else:
            local_data_rsi.pop(0)
            local_data_rsi.append(last_price)
            share_status = strategy(last_price, share["ticker"])
    elif len(local_data_bollinger) > 0:
        local_data_bollinger[-1] = last_price
        local_data_rsi[-1] = last_price
        share_status = strategy(last_price, share["ticker"])
    else:
        return None
    if (
        share_status
        and not purchases["orders"][share["ticker"]].get("order_id", None)
        and (
            (not purchases["orders"][share["ticker"]].get("last_sell", None))
            or (
                (
                    datetime.datetime.now()
                    - datetime.datetime.strptime(
                        purchases["orders"][share["ticker"]]["last_sell"],
                        "%Y-%m-%d %H:%M",
                    )
                )
                > datetime.timedelta(hours=2)
            )
        )
    ):
        quantity_lot = int(
            min(10000, purchases["available"]) // (last_price * share["lot"])
        )
        if quantity_lot > 0:
            last_price -= last_price % share["min_price_increment"]
            async with AsyncRetryingClient(
                Config.NIKITA_TOKEN, Config.RETRY_SETTINGS
            ) as client:
                buy_trade = await buy_limit_order(
                    share["figi"], last_price, quantity_lot, client
                )
            purchases["orders"][share["ticker"]]["order_id"] = buy_trade.order_id
            purchases["orders"][share["ticker"]]["lot"] = share["lot"]
            purchases["available"] -= last_price * quantity_lot * share["lot"]
            return f"СТРАТЕГИЯ НИКИТЫ ЗАЯВКА\n\nЗаявка на {share['ticker']} на сумму {last_price * quantity_lot * share['lot']}\n\n{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} по цене {last_price}\nКол-во: {quantity_lot * share['lot']}"
    return None


async def fill_data_nikita(purchases: dict):
    async with AsyncRetryingClient(
        Config.NIKITA_TOKEN, Config.RETRY_SETTINGS
    ) as client:
        shares = await get_shares(client)
        for share in shares:
            data_bollinger[share["ticker"]] = []
            data_rsi[share["ticker"]] = []
        for share in shares:
            if share["ticker"] not in purchases["orders"].keys():
                purchases["orders"][share["ticker"]] = {
                    "min_price_increment": share["min_price_increment"],
                    "lot": share["lot"],
                    "figi": share["figi"],
                    "averaging": False,
                }
            async for candle in client.get_all_candles(
                figi=share["figi"],
                from_=datetime.datetime.combine(
                    datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                    datetime.time(6, 0),
                ).replace(tzinfo=datetime.timezone.utc)
                - datetime.timedelta(days=5),
                interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
            ):
                await analise_historic_candle(candle, share)


async def analise_historic_candle(candle: HistoricCandle, share: dict):
    local_data_bollinger = data_bollinger[share["ticker"]]
    local_data_rsi = data_rsi[share["ticker"]]
    last_price = float(quotation_to_decimal(candle.close))
    share_status = False
    if candle.time.minute == 00:
        if len(local_data_bollinger) < StrategyConfig.bollinger_frame_count:
            local_data_bollinger.append(last_price)
        else:
            local_data_bollinger.pop(0)
            local_data_bollinger.append(last_price)
            share_status = strategy(last_price, share["ticker"])
            # print(share["ticker"], candle.time + datetime.timedelta(hours=3))
        if len(local_data_rsi) < StrategyConfig.rsi_count_frame * 10:
            local_data_rsi.append(last_price)
        else:
            local_data_rsi.pop(0)
            local_data_rsi.append(last_price)
            share_status = strategy(last_price, share["ticker"])
            # print(share["ticker"], candle.time + datetime.timedelta(hours=3))
    elif len(local_data_bollinger) > 0:
        local_data_bollinger[-1] = last_price
        local_data_rsi[-1] = last_price
        share_status = strategy(last_price, share["ticker"])
        # print(share["ticker"], candle.time + datetime.timedelta(hours=3))
    else:
        return None
    # if share_status:
    #     print(share["ticker"], candle.time + datetime.timedelta(hours=3), last_price)


async def orders_check_nikita(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncRetryingClient(
        Config.NIKITA_TOKEN, Config.RETRY_SETTINGS
    ) as client:
        for ticker in purchases["orders"].keys():
            order_id = purchases["orders"][ticker].get("order_id", None)
            if not order_id or "|" in order_id:
                continue
            order: OrderState = await client.orders.get_order_state(
                account_id=await get_account_id(client), order_id=order_id
            )
            last_price = await get_last_price(order.figi, client)
            if (
                order.execution_report_status
                == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
            ) or (
                order.execution_report_status
                != OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
                and not strategy(last_price, ticker)
            ):
                if order.lots_executed > 0:
                    lots = purchases["orders"][ticker].get("lot", 1)
                    purchase_text = f"Покупка {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nКол-во: {order.lots_executed*lots}"
                    messages_to_send.append(
                        "СТРАТЕГИЯ НИКИТЫ ПОКУПКА\n\n" + purchase_text
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
                    take_profit_response, stop_loss_response = (
                        await place_sell_stop_orders(
                            order.figi,
                            take_profit_price,
                            stop_loss_price,
                            order.lots_executed,
                            client,
                        )
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
                        f"СТРАТЕГИЯ НИКИТЫ ОТМЕНА\n\nОтмена {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}"
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
            strategy="nikita",
            volume=0,
        )


async def stop_orders_check_nikita(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncRetryingClient(
        Config.NIKITA_TOKEN, Config.RETRY_SETTINGS
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
            if not order_id or "|" not in order_id:
                continue
            take_profit_order_id, stop_loss_order_id = order_id.split("|")
            figi = purchases["orders"][ticker].get("figi")
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
                        except Exception as e:
                            pass
                        price_buy = take_profit_price / (
                            1 + StrategyConfig.take_profit / 100
                        )
                    else:
                        try:
                            await client.stop_orders.cancel_stop_order(
                                account_id=await get_account_id(client),
                                stop_order_id=take_profit_order_id,
                            )
                        except Exception as e:
                            pass
                        price_buy = stop_loss_price / (
                            1 - StrategyConfig.stop_loss / 100
                        )
                    profit = lots_traded * (sell_price - price_buy)
                    purchases["available"] += moneyvalue_to_float(last_trade.payment)
                    messages_to_send.append(
                        f"СТРАТЕГИЯ НИКИТЫ ПРОДАЖА\n\n{purchase_text}\n\nПродажа {(last_trade.date + datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M')} по цене {sell_price}\n\nПрибыль: {round(profit, 2)}"
                    )
                    purchases["orders"][ticker] = {
                        "last_sell": (
                            last_trade.date + datetime.timedelta(hours=3)
                        ).strftime("%Y-%m-%d %H:%M"),
                        "min_price_increment": purchases["orders"][ticker][
                            "min_price_increment"
                        ],
                        "figi": purchases["orders"][ticker]["figi"],
                        "averaging": False,
                    }
    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="nikita",
            volume=0,
        )


async def market_review_nikita(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    async with AsyncRetryingClient(
        Config.NIKITA_TOKEN, Config.RETRY_SETTINGS
    ) as client:
        shares = await get_shares(client)
        messages_to_send = []
        for share in shares:
            message = await analise_share(share, purchases, client)
            if message is not None:
                messages_to_send.append(message)
        for message in messages_to_send:
            await tg_bot.send_signal(
                message=message,
                strategy="nikita",
                volume=0,
            )


# import asyncio


# async def main():
#     await fill_data_nikita()
#     scheduler = AsyncIOScheduler()
#     scheduler.add_job(
#         market_review_nikita,
#         "cron",
#         hour="10-23",
#         second="00",
#         args=[self.tg_bot, self.strategies_data["nikita"]],
#     )


# if __name__ == "__main__":
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(main())
