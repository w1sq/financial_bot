import asyncio
import json
import datetime

from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    AsyncClient,
    CandleInterval,
)
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal
import tinkoff

TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw"


async def main():
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        shares = []
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                # if item.ticker == "MOEX":
                #     print(item)
                if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]:
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


if __name__ == "__main__":
    asyncio.run(main())
