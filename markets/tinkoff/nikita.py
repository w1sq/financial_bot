import datetime
from typing import Optional, List, Dict, Tuple

import pandas
import asyncio
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle

from bot import TG_Bot


def calculate_bollinger_bands(data, window=20):
    sma = data.rolling(window=window).mean()
    std = data.rolling(window=window).std()
    return sma.iloc[-1], std.iloc[-1]


def calculate_rsi(data, period=14):
    delta = data.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


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
purchases: Dict[str, Dict] = {}

# bollinger_indicators: Dict[str, Dict[datetime.datetime, float]] = {}
# rsi_indicators: Dict[str, Dict[datetime.datetime, Tuple[float, float]]] = {}


def bollinger_and_rsi_data(ticker: str, candle_data: HistoricCandle) -> Optional[Dict]:
    local_data_bollinger = data_bollinger[ticker]
    local_data_rsi = data_rsi[ticker]
    candle_close = float(quotation_to_decimal(candle_data.close))
    if candle_data.time.minute == 30:
        if len(local_data_bollinger) < StrategyConfig.bollinger_frame_count:
            local_data_bollinger.append(candle_close)
        else:
            local_data_bollinger.pop(0)
            local_data_bollinger.append(candle_close)
        if len(local_data_rsi) < StrategyConfig.rsi_count_frame:
            local_data_rsi.append(candle_close)
        else:
            local_data_rsi.pop(0)
            local_data_rsi.append(candle_close)
    elif len(local_data_bollinger) > 0:
        local_data_bollinger[-1] = candle_close
        local_data_rsi[-1] = candle_close
    else:
        return None

    _avarege, _sko = calculate_bollinger_bands(pandas.Series(local_data_bollinger))
    _rsi = calculate_rsi(pandas.Series(local_data_rsi))

    # bollinger_indicators[ticker][candle_data.time] = (_avarege, _sko)
    # rsi_indicators[ticker][candle_data.time] = _rsi

    if (
        candle_close
        < (
            _avarege
            - StrategyConfig.bolinger_mult
            * _sko
            * StrategyConfig.strategy_bollinger_range
        )
        and _rsi <= StrategyConfig.rsi_treshold
        and not purchases[ticker]
    ):
        _purchase = {
            "date_buy": candle_data.time,
            "price_buy": candle_close,
            "date_sell": "-",
            "price_sell": "-",
            "profit": "-",
        }
        _purchase["ticker"] = ticker
        purchases[ticker] = _purchase
    elif purchases[ticker]:
        _purchase = purchases[ticker]
        if (
            float(quotation_to_decimal(candle_data.open))
            > float(_purchase["price_buy"]) * (100 + StrategyConfig.take_profit) / 100
            and _purchase["profit"] == "-"
        ):
            _purchase["date_sell"] = candle_data.time
            _purchase["price_sell"] = float(quotation_to_decimal(candle_data.open))
            _purchase["profit"] = (
                float(quotation_to_decimal(candle_data.open)) - _purchase["price_buy"]
            )
            purchases[ticker] = {}
            return _purchase

        if (
            float(quotation_to_decimal(candle_data.open))
            < float(_purchase["price_buy"]) * (100 - StrategyConfig.stop_los) / 100
            and _purchase["profit"] == "-"
        ):
            _purchase["date_sell"] = candle_data.time
            _purchase["price_sell"] = float(quotation_to_decimal(candle_data.open))
            _purchase["profit"] = (
                float(quotation_to_decimal(candle_data.open)) - _purchase["price_buy"]
            )
            purchases[ticker] = {}
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
TOKEN = "t.b--pMCWrjEHHBKOZzAfeRbw8OHJdJRWX4AtVf3EUXQa7tuuYt5cEpVE6MneVZ-SeC1-UgiAmf2jNJ_Fys0Y_JA"  # full access
working_hours = range(10, 24)


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


async def fill_data(shares, client):
    trades = []
    for share in shares:
        data_bollinger[share["ticker"]] = []
        data_rsi[share["ticker"]] = []
        purchases[share["ticker"]] = {}
        # bollinger_indicators[share["ticker"]] = {}
        # rsi_indicators[share["ticker"]] = {}
    for share in shares:
        async for candle in client.get_all_candles(
            figi=share["figi"],
            from_=datetime.datetime.combine(
                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                datetime.time(6, 0),
            ).replace(tzinfo=datetime.timezone.utc)
            - datetime.timedelta(days=2),
            interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
        ):
            trade = bollinger_and_rsi_data(share["ticker"], candle)
            if trade is not None:
                print(trade)
                trades.append(trade)
    return trades


async def send_message(tg_bot: TG_Bot, trade: Dict):
    await tg_bot.send_signal(
        message=f"СТРАТЕГИЯ НИКИТЫ\n\nПокупка {trade['ticker']} {trade['date_buy']+datetime.timedelta(hours=3):%d-%m-%Y %H:%M} по цене {trade['price_buy']}\n\nПродажа {trade['date_sell']+datetime.timedelta(hours=3):%d-%m-%Y %H:%M} по цене {trade['price_sell']}\n\nПрибыль: {trade['profit']}",
        strategy="nikita",
        volume=0,
    )


async def market_review_nikita(tg_bot: TG_Bot):
    shares = await get_all_shares()
    async with AsyncClient(TOKEN) as client:
        trades = await fill_data(shares, client)
        for trade in trades:
            await send_message(tg_bot, trade)
        await asyncio.sleep(30)
        current_minute = datetime.datetime.now().minute
        while True:
            time_now = datetime.datetime.now()
            if time_now.hour in working_hours and current_minute == time_now.minute:
                candles = []
                for share in shares:
                    async for candle in client.get_all_candles(
                        figi=share["figi"],
                        from_=now() - datetime.timedelta(minutes=1),
                        interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
                    ):
                        candles.append((share["ticker"], candle))
                        await asyncio.sleep(0.3)
                for candle in candles:
                    trade = bollinger_and_rsi_data(candle[0], candle[1])
                    if trade is not None:
                        await send_message(tg_bot, trade)
                if current_minute == 59:
                    current_minute = 0
                else:
                    current_minute += 1
            await asyncio.sleep(10)
