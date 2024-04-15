import asyncio

from tinkoff.invest import AsyncClient
from markets.tinkoff.utils import buy_market_order, get_shares, get_history
from config import Config

from pprint import pprint


async def get_account_id(client: AsyncClient):
    accounts = await client.users.get_accounts()
    return accounts.accounts[0].id


async def main():
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        # shares = await get_shares(client)
        # for share in shares:
        #     if share["ticker"] == "BELU":
        #         order = await buy_market_order(share["figi"], 1, client)
        #         print(order)

        acc_id = await get_account_id(client)
        # print(acc_id)

        # pprint(await get_history(client))

        pprint(await client.stop_orders.get_stop_orders(account_id=acc_id))

        # portfolio = await client.operations.get_portfolio(account_id=acc_id)
        # pprint(portfolio)


if __name__ == "__main__":
    asyncio.run(main())
