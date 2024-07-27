import asyncio
from time import sleep
from typing import List, Dict
from datetime import timedelta

import gspread
from tinkoff.invest import AsyncClient
from markets.tinkoff.utils import (
    get_history,
    moneyvalue_to_float,
)

from config import Config
from tinkoff.invest.async_services import AsyncServices
from tinkoff.invest import (
    AsyncClient,
    Quotation,
)


google_client = gspread.service_account(filename="service_account.json")

table = google_client.open_by_key(Config.NIKITA_TABLE_ID)
deals_worksheet = table.get_worksheet(0)
active_worksheet = table.get_worksheet(1)


async def get_figis_to_tickers(client: AsyncServices) -> List[Dict]:
    """Get shares from Tinkoff API by tickers or all of them"""
    instruments = client.instruments
    figis_to_tickerslots = {}
    for method in ["shares"]:
        for item in (await getattr(instruments, method)()).instruments:
            if item.exchange in [
                "MOEX",
                "MOEX_WEEKEND",
                "MOEX_EVENING_WEEKEND",
            ]:
                figis_to_tickerslots[item.figi] = (item.ticker, item.lot)
    return figis_to_tickerslots


async def get_account_id(client: AsyncServices):
    accounts = await client.users.get_accounts()
    return accounts.accounts[0].id


def float_to_quotation(value):
    units = int(value)
    nano = int((value - units + 1e-10) * 1_000_000_000)
    return Quotation(units=units, nano=nano)


async def get_balance_delta(client: AsyncServices, trades: List, fees: Dict) -> float:
    delta = 0
    for trade in trades:
        delta += moneyvalue_to_float(trade.payment)

        # Логируем комиссии
        if trade.operation_type == 19:
            fees[trade.parent_operation_id] = trade

    return delta


async def main():
    async with AsyncClient(Config.NIKITA_TOKEN) as client:
        active_orders = {}
        fees = {}
        figis_info = await get_figis_to_tickers(client)
        acc_id = await get_account_id(client)
        operations = await get_history(client, minutes=60 * 24 * 7)

        operations = operations[::-1]

        balance_delta = await get_balance_delta(client, operations, fees)

        portfolio = await client.operations.get_portfolio(account_id=acc_id)

        present_balance = moneyvalue_to_float(
            portfolio.total_amount_currencies
        ) + moneyvalue_to_float(portfolio.total_amount_shares)

        current_balance = present_balance + balance_delta

        max_balance = current_balance
        max_low = present_balance - max_balance

        current_string_deals = 4
        current_string_active = 4

        for operation in operations:
            if operation.operation_type == 19:
                continue

            local_delta = moneyvalue_to_float(operation.payment) + moneyvalue_to_float(
                fees[operation.id].payment
            )

            current_balance += local_delta

            if current_balance > max_balance:
                max_balance = current_balance

            if max_low > current_balance - max_balance:
                max_low = current_balance - max_balance

            # Обработка выхода из сделки
            if operation.figi in active_orders and operation.operation_type == 22:
                entrance_operation = active_orders[operation.figi]
                entrance_fee = fees[entrance_operation.id]
                exit_fee = fees[operation.id]

                ticker, lot = figis_info[operation.figi]

                values = [
                    str(current_string_deals - 3),
                    ticker,
                    "long",
                    operation.quantity / lot,
                    entrance_operation.date.strftime("%Y-%m-%d"),
                    (entrance_operation.date + timedelta(hours=3)).strftime("%H:%M"),
                    moneyvalue_to_float(entrance_operation.price) * lot,
                    moneyvalue_to_float(entrance_operation.payment),
                    operation.date.strftime("%Y-%m-%d"),
                    (operation.date + timedelta(hours=3)).strftime("%H:%M"),
                    moneyvalue_to_float(operation.price) * lot,
                    moneyvalue_to_float(operation.payment),
                    moneyvalue_to_float(exit_fee.payment)
                    + moneyvalue_to_float(entrance_fee.payment),
                    moneyvalue_to_float(operation.payment)
                    + moneyvalue_to_float(entrance_operation.payment)
                    + moneyvalue_to_float(exit_fee.payment)
                    + moneyvalue_to_float(entrance_fee.payment),
                    current_balance,
                    max_balance,
                    current_balance - max_balance,
                    max_low,
                ]
                deals_worksheet.update(
                    [values], f"A{current_string_deals}:R{current_string_deals}"
                )

                current_string_deals += 1
                if current_string_active % 10 == 0:
                    sleep(10)

                del active_orders[operation.figi]
            elif operation.operation_type == 15:
                ticker, lot = figis_info[operation.figi]

                values = [
                    str(current_string_deals - 3),
                    ticker,
                    "long",
                    operation.quantity / lot,
                    operation.date.strftime("%Y-%m-%d"),
                    (operation.date + timedelta(hours=3)).strftime("%H:%M"),
                    moneyvalue_to_float(operation.price) * lot,
                    moneyvalue_to_float(operation.payment),
                ]
                # Тут логика выгрузки
                active_worksheet.update(
                    [values], f"A{current_string_active}:H{current_string_active}"
                )
                active_orders[operation.figi] = operation
                current_string_active += 1

                if current_string_active % 10 == 0:
                    sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
