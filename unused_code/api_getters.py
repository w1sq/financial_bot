from datetime import timedelta

import asyncio
import tinkoff
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle

TOKEN = "t.Gb6EBFHfF-eQqwR8LXYn6l7A5AM6aFh1vX9QMOmrZJ2V6OEhZdNZuW4dpThKlEH504oN2Og6HLdMXyltEBK5QQ"


async def get_share_by_figi(figi: str):
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]:
                    if item.figi == figi:
                        print(
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
                                "scale": 9
                                - len(str(item.min_price_increment.nano))
                                + 1,
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


async def get_share_by_ticker(ticker: str):
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]:
                    if item.name == "QIWI":
                        print(
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
                                "scale": 9
                                - len(str(item.min_price_increment.nano))
                                + 1,
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


if __name__ == "__main__":
    asyncio.run(get_share_by_figi("BBG00475K6C3"))
