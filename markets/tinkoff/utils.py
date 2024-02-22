import datetime
from typing import Optional, List, Dict, Tuple

from tinkoff.invest import (
    AsyncClient,
    OrderType,
    OrderDirection,
)

from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle


async def get_all_shares(client: AsyncClient, tickers: List[str] = []) -> List[Dict]:
    instruments: InstrumentsService = client.instruments
    shares = []
    for method in ["shares"]:
        for item in (await getattr(instruments, method)()).instruments:
            if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"] and (
                not tickers or item.ticker in tickers
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


async def trade(
    instrument_figi: str, trade_direction: int, ACCOUNT_ID: str, TOKEN: str
):
    # trade_direction : buy - 1, sell - 2
    async with AsyncClient(TOKEN) as client:
        order = await client.orders.post_order(
            figi=instrument_figi,
            account_id=ACCOUNT_ID,
            quantity=1,
            direction=trade_direction,
            order_type=OrderType.ORDER_TYPE_MARKET,
            order_id=str(datetime.datetime.utcnow().timestamp()),
        )
        return order
