import datetime
import asyncio
from typing import List, Dict, Tuple

import pandas
from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest.exceptions import AioRequestError
from tinkoff.invest.async_services import AsyncServices
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    OrderState,
    OrderExecutionReportStatus,
    OperationType,
    OperationState,
    CandleInstrument,
    AsyncClient,
    HistoricCandle,
    CandleInterval,
    MarketDataRequest,
    SubscribeCandlesRequest,
    SubscriptionAction,
    SubscriptionInterval,
)

from bot import TG_Bot
from config import Config
from markets.tinkoff.utils import (
    get_shares,
    get_history,
    get_account_id,
    get_last_price,
    buy_limit_order,
    sell_limit_order,
    buy_market_order,
    moneyvalue_to_float,
    place_buy_stop_orders,
    place_sell_stop_orders,
)


class StrategyConfig:
    bolinger_mult = 2
    bollinger_frame_count = 20
    rsi_count_frame = 14
    strategy_bollinger_range = 1.5
    rsi_treshold_buy = 30
    rsi_treshold_sell = 70
    take_profit = 0.4
    stop_loss = 1


data_bollinger_shorts: Dict[str, List[float]] = {}
data_rsi_shorts: Dict[str, List[float]] = {}


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
    local_data_bollinger = data_bollinger_shorts[ticker]
    local_data_rsi = data_rsi_shorts[ticker]
    avarege, sko = calculate_bollinger_bands(pandas.Series(local_data_bollinger))
    if len(local_data_rsi) < StrategyConfig.rsi_count_frame:
        return False
    rsi = calculate_rsi(pandas.Series(local_data_rsi))
    if (
        last_price
        > (
            avarege
            + StrategyConfig.bolinger_mult
            * sko
            * StrategyConfig.strategy_bollinger_range
        )
        and rsi >= StrategyConfig.rsi_treshold_sell
    ):
        print(ticker + "strategy")
        return True
    return False


async def analise_share(share: dict, purchases: dict, client: AsyncServices):
    local_data_bollinger = data_bollinger_shorts.get(share["ticker"])
    local_data_rsi = data_rsi_shorts.get(share["ticker"])
    if not local_data_bollinger or not local_data_rsi:
        return None
    try:
        last_price = await get_last_price(share["figi"], client)
    except AioRequestError as e:
        print(e)
        return None
    share_status = False
    if datetime.datetime.now().minute == 00:
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
        print(share["ticker"] + "buying")
        quantity_lot = int(
            min(10000, purchases["available"]) // (last_price * share["lot"])
        )
        if quantity_lot > 0:
            last_price -= last_price % share["min_price_increment"]
            try:
                print(share["ticker"], last_price, quantity_lot)
                trade = await sell_limit_order(
                    share["figi"], last_price, quantity_lot, client
                )
                purchases["orders"][share["ticker"]]["type"] = "short"
                purchases["orders"][share["ticker"]]["order_id"] = trade.order_id
                purchases["orders"][share["ticker"]]["lot"] = share["lot"]
                purchases["available"] -= last_price * quantity_lot * share["lot"]
                return f"СТРАТЕГИЯ НИКИТЫ v 1.2 ЗАЯВКА #{purchases['orders'][share['ticker']]['type']}\n\nЗаявка на {share['ticker']} на сумму {last_price * quantity_lot * share['lot']}\n\n{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} по цене {last_price}\nКол-во: {quantity_lot * share['lot']}"
            except Exception as e:
                print(e)
    return None


async def fill_data_nikita_shorts(purchases: dict):
    async with AsyncRetryingClient(
        Config.ANDREY_TOKEN, Config.RETRY_SETTINGS
    ) as client:
        shares = await get_shares(client)
        for share in shares:
            data_bollinger_shorts[share["ticker"]] = []
            data_rsi_shorts[share["ticker"]] = []
        for share in shares:
            if share["ticker"] not in purchases["orders"].keys():
                purchases["orders"][share["ticker"]] = {
                    "min_price_increment": share["min_price_increment"],
                    "lot": share["lot"],
                    "figi": share["figi"],
                    "averaging": False,
                }
            for key in ["lot", "min_price_increment", "figi", "averaging"]:
                if key not in purchases["orders"][share["ticker"]]:
                    if key == "averaging":
                        purchases["orders"][share["ticker"]][key] = False
                    else:
                        purchases["orders"][share["ticker"]][key] = share[key]
            async for candle in client.get_all_candles(
                figi=share["figi"],
                from_=datetime.datetime.combine(
                    datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                    datetime.time(6, 0),
                ).replace(tzinfo=datetime.timezone.utc)
                - datetime.timedelta(days=3),
                interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
            ):
                await analise_historic_candle(candle, share)


async def analise_historic_candle(candle: HistoricCandle, share: dict):
    local_data_bollinger = data_bollinger_shorts[share["ticker"]]
    local_data_rsi = data_rsi_shorts[share["ticker"]]
    last_price = float(quotation_to_decimal(candle.close))
    share_status = False
    # print(candle.time + datetime.timedelta(hours=3), end="")
    if candle.time.minute == 00:
        if len(local_data_bollinger) < StrategyConfig.bollinger_frame_count:
            local_data_bollinger.append(last_price)
        else:
            local_data_bollinger.pop(0)
            local_data_bollinger.append(last_price)
            # share_status = strategy(last_price, share["ticker"])
            # print(share["ticker"], candle.time + datetime.timedelta(hours=3))
        if len(local_data_rsi) < StrategyConfig.rsi_count_frame * 10:
            local_data_rsi.append(last_price)
        else:
            local_data_rsi.pop(0)
            local_data_rsi.append(last_price)
            # share_status = strategy(last_price, share["ticker"])
            # print(share["ticker"], candle.time + datetime.timedelta(hours=3))
    elif len(local_data_bollinger) > 0:
        local_data_bollinger[-1] = last_price
        local_data_rsi[-1] = last_price
        # share_status = strategy(last_price, share["ticker"])
        # print(share["ticker"], candle.time + datetime.timedelta(hours=3))
    else:
        return None
    # if share_status:
    #     print(share["ticker"], candle.time + datetime.timedelta(hours=3), last_price)


async def orders_check_nikita_shorts(tg_bot: TG_Bot, purchases: dict):
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
                    purchase_text = f"Продажа {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')} по цене {moneyvalue_to_float(order.average_position_price)} с коммисией {moneyvalue_to_float(order.executed_commission)}\nКол-во: {order.lots_executed*lots}\nОбщая сумма: {moneyvalue_to_float(order.executed_order_price)}"
                    messages_to_send.append(
                        "СТРАТЕГИЯ НИКИТЫ v 1.2 ПРОДАЖА #short\n\n" + purchase_text
                    )
                    take_profit_price = moneyvalue_to_float(
                        order.average_position_price
                    ) * (1 - StrategyConfig.take_profit / 100)
                    stop_loss_price = moneyvalue_to_float(
                        order.average_position_price
                    ) * (1 + StrategyConfig.stop_loss / 100)
                    take_profit_price -= (
                        take_profit_price
                        % purchases["orders"][ticker]["min_price_increment"]
                    )
                    stop_loss_price -= (
                        stop_loss_price
                        % purchases["orders"][ticker]["min_price_increment"]
                    )
                    take_profit_response, stop_loss_response = (
                        await place_buy_stop_orders(
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
                        + stop_loss_response.stop_order_id
                    )
                    purchases["orders"][ticker]["order_id"] = stop_orders_id_string
                    purchases["orders"][ticker]["order_data"] = purchase_text
                    purchases["orders"][ticker]["price_buy"] = moneyvalue_to_float(
                        order.average_position_price
                    )
                    purchases["orders"][ticker]["quantity"] = order.lots_executed
                else:
                    messages_to_send.append(
                        f"СТРАТЕГИЯ НИКИТЫ v 1.2 ОТМЕНА\n\nОтмена {ticker} {(order.order_date+ datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}"
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


async def stop_orders_check_nikita_shorts(tg_bot: TG_Bot, purchases: dict):
    messages_to_send = []
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        last_trades = await get_history(client)
        for ticker in purchases["orders"].keys():
            order_id = purchases["orders"][ticker].get("order_id")
            if not order_id or "|" not in order_id:
                continue
            take_profit_order_id, stop_loss_order_id = order_id.split("|")
            figi = purchases["orders"][ticker].get("figi")
            price_buy = purchases["orders"][ticker].get("price_buy", 0)
            quantity = purchases["orders"][ticker].get("quantity", 0)
            purchase_text = purchases["orders"][ticker].get("order_data", "")
            if last_trades:
                for last_trade in last_trades:
                    if (
                        last_trade.figi == figi
                        and last_trade.operation_type
                        == OperationType.OPERATION_TYPE_BUY
                        and last_trade.state == OperationState.OPERATION_STATE_EXECUTED
                    ):
                        order_id = purchases["orders"][ticker].pop("order_id")
                        sell_price = moneyvalue_to_float(last_trade.price)
                        purchases["available"] += moneyvalue_to_float(
                            last_trade.payment
                        )
                        profit = last_trade.quantity * (price_buy - sell_price)
                        messages_to_send.append(
                            f"СТРАТЕГИЯ НИКИТЫ v 1.2 ПОКУПКА\n\n{purchase_text}\n\nПокупка {(last_trade.date + datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M')} по цене {sell_price}\n\nПрибыль: {round(profit, 2)}"
                        )
                        purchases["orders"][ticker] = {
                            "last_sell": (
                                last_trade.date + datetime.timedelta(hours=3)
                            ).strftime("%Y-%m-%d %H:%M"),
                            "min_price_increment": purchases["orders"][ticker][
                                "min_price_increment"
                            ],
                            "figi": purchases["orders"][ticker]["figi"],
                            "lot": purchases["orders"][ticker]["lot"],
                            "averaging": False,
                        }
            if (
                not stop_loss_order_id
                and purchases["orders"][ticker]["averaging"] is False
                and price_buy
                and quantity
                and purchases["orders"][ticker].get("lowest_price", 10e9)
                < price_buy * (1 - StrategyConfig.stop_loss / 200)
            ):
                continue
                trade = await buy_market_order(figi, quantity, client)
                purchases["available"] -= moneyvalue_to_float(trade.total_order_amount)
                purchases["orders"][ticker]["quantity"] = quantity * 2
                purchases["orders"][ticker]["averaging"] = True
                messages_to_send.append(
                    f"СТРАТЕГИЯ НИКИТЫ v 1.2 ПОКУПКА\n\n{purchase_text}\n\nУсреднение на сумму {moneyvalue_to_float(trade.total_order_amount)} по цене {moneyvalue_to_float(trade.executed_order_price)}\nКоличество: {quantity*purchases['orders'][ticker].get('lot',0)}"
                )
                try:
                    await client.stop_orders.cancel_stop_order(
                        account_id=await get_account_id(client),
                        stop_order_id=take_profit_order_id,
                    )
                except Exception as e:
                    print(e)
                take_profit_price = price_buy * (1 + StrategyConfig.take_profit / 100)
                stop_loss_price = price_buy * (1 - StrategyConfig.stop_loss / 100)
                take_profit_price -= (
                    take_profit_price
                    % purchases["orders"][ticker]["min_price_increment"]
                )
                stop_loss_price -= (
                    stop_loss_price % purchases["orders"][ticker]["min_price_increment"]
                )
                take_profit_response, stop_loss_response = await place_sell_stop_orders(
                    figi,
                    take_profit_price,
                    stop_loss_price,
                    quantity * 2,
                    client,
                )
                stop_orders_id_string = str(
                    take_profit_response.stop_order_id
                    + "|"
                    + stop_loss_response.stop_order_id
                )
                purchases["orders"][ticker]["order_id"] = stop_orders_id_string

    for message in messages_to_send:
        await tg_bot.send_signal(
            message=message,
            strategy="nikita",
            volume=0,
        )


async def update_lowest_prices_nikita(purchases: Dict[str, Dict]):
    figis = []
    figi_to_ticker = {}
    for ticker, order_info in purchases["orders"].items():
        figi = order_info.get("figi")
        figis.append(figi)
        figi_to_ticker[figi] = ticker

    async def request_iterator():
        yield MarketDataRequest(
            subscribe_candles_request=SubscribeCandlesRequest(
                waiting_close=True,
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[
                    CandleInstrument(
                        figi=figi,
                        interval=SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE,
                    )
                    for figi in figis
                ],
            )
        )
        while True:
            await asyncio.sleep(1)

    async with AsyncClient(Config.READONLY_TOKEN) as client:
        try:
            async for marketdata in client.market_data_stream.market_data_stream(
                request_iterator()
            ):
                if marketdata.candle:
                    purchases["orders"][figi_to_ticker[marketdata.candle.figi]][
                        "lowest_price"
                    ] = float(quotation_to_decimal(marketdata.candle.low))
        except Exception as e:
            print("TEST", e)


async def market_review_nikita_shorts(tg_bot: TG_Bot, purchases: Dict[str, Dict]):
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
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
