import os
import csv
import math
import asyncio
import datetime
from dateutil.relativedelta import relativedelta

from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.retrying.settings import RetryClientSettings
from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest import CandleInterval, Quotation

from tinkoff.invest.utils import now, quotation_to_decimal

READONLY_TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw"
RETRY_SETTINGS = RetryClientSettings(use_retry=True, max_retry_attempt=1000000)


async def main():
    async with AsyncRetryingClient(
        token=READONLY_TOKEN, settings=RETRY_SETTINGS
    ) as client:
        tickers = []
        candle_attrs_to_write = ["time", "open", "high", "low", "close", "volume"]
        instruments: InstrumentsService = client.instruments
        shares = {}
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"] and (
                    not tickers or item.ticker in tickers
                ):
                    shares[item.ticker] = (item.figi, item.first_1min_candle_date)
        print(len(shares))
        dir_name = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
        os.mkdir(dir_name)
        for ticker, (figi, time_to_parse) in shares.items():
            path = f"{dir_name}/{ticker}.csv"
            with open(path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=candle_attrs_to_write)
                writer.writeheader()
                rows = []
                years_to_parse = math.ceil(
                    (
                        datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)
                        - time_to_parse
                    ).days
                    / 365
                )
                print(years_to_parse)
                for sub_delta in range(years_to_parse):
                    local_rows = []
                    async for candle in client.get_all_candles(
                        instrument_id=figi,
                        from_=now() - relativedelta(years=sub_delta + 1),
                        to=now() - relativedelta(years=sub_delta),
                        interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
                    ):
                        dict_to_write = {}
                        for candle_attr_to_write in candle_attrs_to_write:
                            attr = getattr(candle, candle_attr_to_write)
                            if isinstance(attr, Quotation):
                                attr = float(quotation_to_decimal(attr))
                            elif isinstance(attr, datetime.datetime):
                                attr = attr.strftime("%Y-%m-%d %H:%M")
                            dict_to_write[candle_attr_to_write] = attr
                        local_rows.append(dict_to_write)
                    rows.extend(local_rows[::-1])
                writer.writerows(rows)


if __name__ == "__main__":
    asyncio.run(main())
