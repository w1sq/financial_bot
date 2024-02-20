import datetime
from typing import Optional, List, Dict, Tuple

import asyncio
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle


def moving_average_and_sko_calc(input_list: List[float]):
    _avarege = sum(input_list) / len(input_list)

    _summ2 = 0
    for elem in input_list:
        _summ2 += (_avarege - elem) ** 2
    _sko = (_summ2 / len(input_list)) ** 0.5

    return _avarege, _sko


def rsi_calc(input_list: List[float]) -> float:
    _positive_frame_count = 0.1
    _negative_frame_count = 0.1

    for i in range(len(input_list) - 1):
        if input_list[i] < input_list[i + 1]:
            _positive_frame_count += 1
        if input_list[i] > input_list[i + 1]:
            _negative_frame_count += 1

    rsi = 100 - 100 / (1 + _positive_frame_count / _negative_frame_count)

    return rsi


class StrategyConfig:
    bolinger_mult = 2
    bollinger_frame_count = 20
    rsi_count_frame = 14
    strategy_bollinger_range = 1.25
    rsi_treshold = 30
    take_profit = 0.4
    stop_los = 1


data_bollinger: Dict[str, List[float]] = {}
data_rsi: Dict[str, List[float]] = {}

bollinger_indicators: Dict[str, Dict[datetime.datetime, float]] = {}
rsi_indicators: Dict[str, Dict[datetime.datetime, Tuple[float, float]]] = {}


def bollinger_and_rsi_data(figi: str, candle_data: HistoricCandle) -> Optional[Dict]:
    local_data_bollinger = data_bollinger[figi]
    local_data_rsi = data_rsi[figi]
    candle_open = float(quotation_to_decimal(candle_data.open))
    if len(local_data_bollinger) < StrategyConfig.bollinger_frame_count:
        local_data_bollinger.append(candle_open)
    else:
        local_data_bollinger.pop(0)
        local_data_bollinger.append(candle_open)
    if len(local_data_rsi) < StrategyConfig.rsi_count_frame:
        local_data_rsi.append(candle_open)
    else:
        local_data_rsi.pop(0)
        local_data_rsi.append(candle_open)

    _avarege, _sko = moving_average_and_sko_calc(local_data_bollinger)
    _rsi = rsi_calc(local_data_rsi)

    bollinger_indicators[figi][candle_data.time] = (_avarege, _sko)
    rsi_indicators[figi][candle_data.time] = _rsi

    if (
        candle_open
        < (
            _avarege
            - StrategyConfig.bolinger_mult
            * _sko
            * StrategyConfig.strategy_bollinger_range
        )
        and _rsi <= StrategyConfig.rsi_treshold
    ):
        _purchase = {
            "date_buy": candle_data.time,
            "price_buy": candle_open,
            "date_sell": "-",
            "price_sell": "-",
            "profit": "-",
        }

        if (
            candle_open
            > _purchase["price_buy"] * (100 + StrategyConfig.take_profit) / 100
            and _purchase["profit"] == "-"
        ):
            _purchase["date_sell"] = candle_data.time
            _purchase["price_sell"] = candle_open
            _purchase["profit"] = candle_open - _purchase["price_buy"]

        if (
            candle_open < _purchase["price_buy"] * (100 - StrategyConfig.stop_los) / 100
            and _purchase["profit"] == "-"
        ):
            _purchase["date_sell"] = candle_data.time
            _purchase["price_sell"] = candle_open
            _purchase["profit"] = candle_open - _purchase["price_buy"]

        return _purchase
    return None


async def get_all_shares():
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        shares = []
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
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


async def get_ticker_by_figi(figi: str) -> str:
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]:
                    if item.figi == figi:
                        return item.ticker


# TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw" #readonly
TOKEN = "t.Gb6EBFHfF-eQqwR8LXYn6l7A5AM6aFh1vX9QMOmrZJ2V6OEhZdNZuW4dpThKlEH504oN2Og6HLdMXyltEBK5QQ"  # full access
working_hours = range(10, 24)


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


async def market_review_nikita():
    shares = await get_all_shares()
    for share in shares:
        data_bollinger[share["figi"]] = []
        data_rsi[share["figi"]] = []
        bollinger_indicators[share["figi"]] = {}
        rsi_indicators[share["figi"]] = {}
    time_stamp = datetime.datetime.now().minute
    # time_stamp = 5
    async with AsyncClient(TOKEN) as client:
        while True:
            time_now = datetime.datetime.now()
            if time_now.minute == time_stamp and time_now.hour in working_hours:
                for share in shares:
                    if share["ticker"] in ("NKNCP", "NKNC", "SELG"):
                        print(share["figi"], share["ticker"])
                        async for candle in client.get_all_candles(
                            figi=share["figi"],
                            from_=datetime.datetime.combine(
                                datetime.datetime.utcnow().replace(
                                    tzinfo=datetime.timezone.utc
                                ),
                                datetime.time(6, 0),
                            ).replace(tzinfo=datetime.timezone.utc)
                            - datetime.timedelta(days=2),
                            interval=CandleInterval.CANDLE_INTERVAL_HOUR,
                        ):
                            purchase = bollinger_and_rsi_data(share["figi"], candle)
                            if purchase is not None:
                                print(await get_ticker_by_figi(share["figi"]), purchase)
                for time in bollinger_indicators["BBG002458LF8"]:
                    print(
                        time.strftime("%d/%m/%y %H:%M"),
                        bollinger_indicators["BBG002458LF8"][time],
                        rsi_indicators["BBG002458LF8"][time],
                    )
                for time in bollinger_indicators["BBG000GQSVC2"]:
                    print(
                        time.strftime("%d/%m/%y %H:%M"),
                        bollinger_indicators["BBG000GQSVC2"][time],
                        rsi_indicators["BBG000GQSVC2"][time],
                    )
                for time in bollinger_indicators["BBG000GQSRR5"]:
                    print(
                        time.strftime("%d/%m/%y %H:%M"),
                        bollinger_indicators["BBG000GQSRR5"][time],
                        rsi_indicators["BBG000GQSRR5"][time],
                    )
                await asyncio.sleep(40 * 60)
            else:
                await asyncio.sleep(60)


if __name__ == "__main__":
    print(asyncio.run(market_review_nikita()))
