import os
import time

from tinkoff.invest import (
    CandleInstrument,
    Client,
    MarketDataRequest,
    SubscribeCandlesRequest,
    SubscriptionAction,
    SubscriptionInterval,
)

from config import Config

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


async def main():
    async with AsyncClient(Config.ANDREY_TOKEN) as client:
        shares = await get_shares(client)
        figis = [share["figi"] for share in shares]

    def request_iterator():
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
            time.sleep(1)

    with Client(Config.READONLY_TOKEN) as client:
        for marketdata in client.market_data_stream.market_data_stream(
            request_iterator()
        ):
            if marketdata.candle:
                print(marketdata.candle.low)


if __name__ == "__main__":
    asyncio.run(main())
