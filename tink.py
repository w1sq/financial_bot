"""Main file for tinkoff"""

import asyncio
from pandas import DataFrame
from datetime import datetime, timedelta, timezone
from tinkoff.invest import CandleInterval
from tinkoff.invest import Client, SecurityTradingStatus
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest.utils import now
from tinkoff.invest import (
    AsyncClient,
    TradeInstrument,
    MarketDataRequest,
    SubscribeTradesRequest,
    SubscriptionAction,
    SubscriptionInterval,
)


blue_chips = {
    #https://www.tinkoff.ru/invest/social/profile/Bipolyar/24291b85-5029-447e-a7b0-11f58705f3e1/
    # 'ALRS': 'BBG004S68B31',
    # 'GAZP': 'BBG004730RP0',
    # 'GMKN': 'BBG004731489',
    # 'IRAO': 'BBG004S68473',
    # 'LKOH': 'BBG004731032',
    'MGNT': 'BBG004RVFCY3',
    # 'MTSS': 'BBG004S681W1',
    # 'NVTK': 'BBG00475KKY8',
    # 'PLZL': 'BBG000R607Y3',
    # 'ROSN': 'BBG004731354',
    # 'RUAL': 'BBG008F2T3T2',
    # 'SBER': 'BBG004730N88',
    # 'SNGS': 'BBG0047315D0',
    # 'TATN': 'BBG004RVFFC0',
    # 'YNDX': 'BBG006L8G4H1'
}

TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw"

def get_shares_names(client: Client):
    """All client shares names"""
    instruments: InstrumentsService = client.instruments
    tickers = []
    for method in ["shares"]:
        for item in getattr(instruments, method)().instruments:
            tickers.append(item.name)
    return tickers

def format_share(share_item):
    """Share-formatting"""
    return {
        "name": share_item.name,
        "ticker": share_item.ticker,
        "class_code": share_item.class_code,
        "figi": share_item.figi,
        "uid": share_item.uid,
        "type": "shares",
        "min_price_increment": quotation_to_decimal(
            share_item.min_price_increment
        ),
        "scale": 9 - len(str(share_item.min_price_increment.nano)) + 1,
        "lot": share_item.lot,
        "trading_status": str(
            SecurityTradingStatus(share_item.trading_status).name
        ),
        "nominal": share_item.nominal,
        "api_trade_available_flag": share_item.api_trade_available_flag,
        "currency": share_item.currency,
        "exchange": share_item.exchange,
        "buy_available_flag": share_item.buy_available_flag,
        "sell_available_flag": share_item.sell_available_flag,
        "short_enabled_flag": share_item.short_enabled_flag,
        "klong": quotation_to_decimal(share_item.klong),
        "kshort": quotation_to_decimal(share_item.kshort),
    }

def get_all_shares(client:Client):
    """All client shares"""
    instruments: InstrumentsService = client.instruments
    tickers = []
    for method in ["shares"]:
        for item in getattr(instruments, method)().instruments:
            tickers.append(
                format_share(item)
            )
    return DataFrame(tickers)

def get_blue_chips(client:Client):
    """Blue chips shares"""
    instruments: InstrumentsService = client.instruments
    tickers = []
    for method in ["shares"]:
        for item in getattr(instruments, method)().instruments:
            if item.ticker in blue_chips.keys():
                tickers.append(
                    format_share(item)
                )
    return DataFrame(tickers)

if __name__ == "__main__":
    with Client(TOKEN) as tinkoff_client:
        # shares = get_blue_chips(tinkoff_client)
        # print(shares)
        # for index, row in shares.iterrows():
        #     print(f'{row["ticker"]}: {row["figi"]}')
        for ticker, figi in blue_chips.items():
            day_candles = []
            to_check = None
            for candle in tinkoff_client.get_all_candles(
                figi=figi,
                from_ = now() - timedelta(days = 1),
                to = now(),
                interval = CandleInterval.CANDLE_INTERVAL_1_MIN
            ):
                print(candle.time, float(quotation_to_decimal(candle.close)))
                # print(candle.time, candle.volume* (quotation_to_decimal(candle.high) + quotation_to_decimal(candle.low))/2)
                if to_check and to_check.volume > (10*candle.volume):
                    print(ticker, to_check.time, to_check.volume, quotation_to_decimal(to_check.open), quotation_to_decimal(to_check.high), quotation_to_decimal(to_check.low), quotation_to_decimal(to_check.close))
                    to_check = None
                if day_candles and (candle.volume > (10*day_candles[-1].volume)):
                    to_check = candle
                else:
                    to_check = None
                day_candles.append(candle)

# async def main():
#     async def request_iterator():
#         yield MarketDataRequest(
#             subscribe_candles_request=SubscribeTradesRequest(
#                 subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
#                 instruments=[
#                     TradeInstrument(
#                         figi="BBG006L8G4H1"
#                     )
#                 ],
#             )
#         )
#         while True:
#             await asyncio.sleep(1)

#     async with AsyncClient(TOKEN) as client:
#         async for marketdata in client.market_data_stream.market_data_stream(
#             request_iterator()
#         ):
#             print(marketdata)


# if __name__ == "__main__":
#     asyncio.run(main())