import asyncio
import datetime

from tinkoff.invest import AsyncClient
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
)
from tinkoff.invest.utils import quotation_to_decimal

from config import Config


async def get_account_id(client: AsyncClient):
    accounts = await client.users.get_accounts()
    return accounts.accounts[0].id


def float_to_quotation(value):
    units = int(value)
    nano = int((value - units) * 1_000_000_000)
    return Quotation(units=units, nano=nano)


async def get_shares(client: AsyncClient):
    """Get shares from Tinkoff API by tickers or all of them"""
    instruments = client.instruments
    shares = {}
    for method in ["shares"]:
        for item in (await getattr(instruments, method)()).instruments:
            if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]:
                shares[item.figi] = {
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
    return shares


async def sell(
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
    if order.execution_report_status != 1:
        print(figi, order)
    return order


async def sell_all_positions():
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        accounts = await client.users.get_accounts()
        shares = await get_shares(client)
        for position in (
            await client.operations.get_portfolio(account_id=accounts.accounts[0].id)
        ).positions:
            try:
                share = shares[position.figi]
                await sell(
                    position.figi,
                    int(quotation_to_decimal(position.quantity) / share["lot"]),
                    client,
                )
            except KeyError:
                print(f"Share {position.figi} not found in shares")


async def list_all_positions():
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        accounts = await client.users.get_accounts()
        for position in (
            await client.operations.get_portfolio(account_id=accounts.accounts[0].id)
        ).positions:
            print(position)


if __name__ == "__main__":
    asyncio.run(sell_all_positions())
