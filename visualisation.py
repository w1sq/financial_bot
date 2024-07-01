import asyncio

from tinkoff.invest import AsyncClient
from markets.tinkoff.utils import (
    buy_market_order,
    get_shares,
    get_history,
    sell_market_order,
    place_sell_stop_orders,
)
from config import Config
from tinkoff.invest.async_services import AsyncServices
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

from pprint import pprint


async def get_account_id(client: AsyncServices):
    accounts = await client.users.get_accounts()
    return accounts.accounts[0].id


def float_to_quotation(value):
    units = int(value)
    nano = int((value - units + 1e-10) * 1_000_000_000)
    return Quotation(units=units, nano=nano)


async def main():
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        # shares = await get_shares(client)
        # for share in shares:
        #     if share["ticker"] in ["MVID"]:
        #         order = await sell_market_order(share["figi"], 100, client)
        #         print(order)
        #     if share["ticker"] in ["MTLR"]:
        #         order = await sell_market_order(share["figi"], 74, client)
        #         print(order)

        pprint(await get_shares(client))

        acc_id = await get_account_id(client)
        # print(acc_id)

        # trades = await get_history(client)
        # pprint(trades)
        # for trade in trades:
        #     if trade.operation_type != 19:
        #         pprint(trade)
        # print(await client.orders.get_orders(account_id=acc_id))

        # await client.stop_orders.cancel_stop_order(
        #     account_id=acc_id,
        #     stop_order_id="a3f587f4-066a-45f4-b458-e28c076f14dd",
        # )

        # stop_loss_response: PostStopOrderResponse = (
        #     await client.stop_orders.post_stop_order(
        #         quantity=35,
        #         stop_price=float_to_quotation(4.193),
        #         direction=StopOrderDirection.STOP_ORDER_DIRECTION_SELL,
        #         account_id=acc_id,
        #         stop_order_type=StopOrderType.STOP_ORDER_TYPE_STOP_LOSS,
        #         instrument_id="BBG004S68473",
        #         expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL,
        #     )
        # )
        # print(stop_loss_response)

        # await sell_market_order("BBG00F9XX7H4", 46, client)
        # pprint(await client.stop_orders.get_stop_orders(account_id=acc_id))

        # pprint(await client.operations.get_portfolio(account_id=acc_id))


if __name__ == "__main__":
    asyncio.run(main())
