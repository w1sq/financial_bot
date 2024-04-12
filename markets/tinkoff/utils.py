import pytz
import datetime
import asyncio
from typing import Optional, List, Dict, Tuple


import tinkoff.invest.exceptions
from tinkoff.invest import (
    AsyncClient,
    OrderType,
    StopOrderType,
    OrderDirection,
    StopOrderDirection,
    PostStopOrderResponse,
    PostOrderResponse,
    StopOrderExpirationType,
    Quotation,
    OperationState,
    Operation,
)
from tinkoff.invest.async_services import AsyncServices
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal


async def get_shares(client: AsyncClient, tickers: List[str] = None) -> List[Dict]:
    """Get shares from Tinkoff API by tickers or all of them"""
    instruments: InstrumentsService = client.instruments
    shares = []
    for method in ["shares"]:
        for item in (await getattr(instruments, method)()).instruments:
            if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"] and (
                tickers is None or item.ticker in tickers
            ):
                shares.append(
                    {
                        "name": item.name,
                        "ticker": item.ticker,
                        "class_code": item.class_code,
                        "figi": item.figi,
                        "uid": item.uid,
                        "type": method,
                        "min_price_increment": float(
                            quotation_to_decimal(item.min_price_increment)
                        ),
                        "scale": 9 - len(str(item.min_price_increment.nano)) + 1,
                        "lot": item.lot,
                        "api_trade_available_flag": item.api_trade_available_flag,
                        "currency": item.currency,
                        "exchange": item.exchange,
                        "buy_available_flag": item.buy_available_flag,
                        "sell_available_flag": item.sell_available_flag,
                        "short_enabled_flag": item.short_enabled_flag,
                        "klong": float(quotation_to_decimal(item.klong)),
                        "kshort": float(quotation_to_decimal(item.kshort)),
                    }
                )
    return shares


async def get_account_id(client: AsyncClient):
    accounts = await client.users.get_accounts()
    return accounts.accounts[0].id


async def sell_market_order(
    figi: str,
    quantity: int,
    client: AsyncClient,
) -> PostOrderResponse:
    account_id = await get_account_id(client)
    order: PostOrderResponse = await client.orders.post_order(
        instrument_id=figi,
        account_id=account_id,
        quantity=quantity,
        direction=OrderDirection.ORDER_DIRECTION_SELL,
        order_type=OrderType.ORDER_TYPE_MARKET,
        order_id=str(datetime.datetime.utcnow().timestamp()),
    )
    if order.execution_report_status not in (1, 4):
        print(figi, order)
    return order


async def buy_market_order(
    figi: str,
    quantity: int,
    client: AsyncClient,
) -> PostOrderResponse:
    account_id = await get_account_id(client)
    order: PostOrderResponse = await client.orders.post_order(
        instrument_id=figi,
        account_id=account_id,
        quantity=quantity,
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        order_type=OrderType.ORDER_TYPE_MARKET,
        order_id=str(datetime.datetime.utcnow().timestamp()),
    )
    if order.execution_report_status not in (1, 4):
        print(figi, order)
    return order


async def buy_limit_order(
    figi: str,
    price: float,
    quantity: int,
    client: AsyncClient,
) -> PostOrderResponse:
    account_id = await get_account_id(client)
    order: PostOrderResponse = await client.orders.post_order(
        instrument_id=figi,
        account_id=account_id,
        price=float_to_quotation(price),
        quantity=quantity,
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        order_type=OrderType.ORDER_TYPE_LIMIT,
        order_id=str(datetime.datetime.utcnow().timestamp()),
    )
    if order.execution_report_status not in (1, 4):
        print(figi, order)
    return order


async def place_stop_orders(
    figi: str,
    take_profit_price: float,
    stop_loss_price: float,
    quantity: int,
    client: AsyncClient,
):
    account_id = await get_account_id(client)
    take_profit_response: PostStopOrderResponse = (
        await client.stop_orders.post_stop_order(
            quantity=quantity,
            price=float_to_quotation(take_profit_price),
            stop_price=float_to_quotation(take_profit_price),
            direction=StopOrderDirection.STOP_ORDER_DIRECTION_SELL,
            account_id=account_id,
            stop_order_type=StopOrderType.STOP_ORDER_TYPE_TAKE_PROFIT,
            instrument_id=figi,
            expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL,
        )
    )
    stop_loss_response: PostStopOrderResponse = (
        await client.stop_orders.post_stop_order(
            quantity=quantity,
            stop_price=float_to_quotation(stop_loss_price),
            direction=StopOrderDirection.STOP_ORDER_DIRECTION_SELL,
            account_id=account_id,
            stop_order_type=StopOrderType.STOP_ORDER_TYPE_STOP_LOSS,
            instrument_id=figi,
            expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL,
        )
    )
    return (take_profit_response, stop_loss_response)


def float_to_quotation(value):
    units = int(value)
    nano = int((value - units + 1e-10) * 1_000_000_000)
    return Quotation(units=units, nano=nano)


def moneyvalue_to_float(moneyvalue):
    return moneyvalue.units + moneyvalue.nano / 1_000_000_000


async def ensure_market_open(figi: str, client: AsyncServices):
    trading_status = await client.market_data.get_trading_status(figi=figi)
    while not (
        trading_status.market_order_available_flag
        and trading_status.api_trade_available_flag
    ):
        await asyncio.sleep(60)
        trading_status = await client.market_data.get_trading_status(figi=figi)


async def get_last_price(figi: str, client: AsyncServices) -> float:
    return float(
        quotation_to_decimal(
            (await client.market_data.get_last_prices(figi=[figi])).last_prices[0].price
        )
    )


async def get_history(client: AsyncServices) -> List[Operation]:
    account_id = await get_account_id(client)
    ten_min_ago = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=10)
    try:
        history = await client.operations.get_operations(
            account_id=account_id,
            from_=ten_min_ago,
            state=OperationState.OPERATION_STATE_EXECUTED,
        )
        return history.operations
    except tinkoff.invest.exceptions.AioRequestError:
        return []
