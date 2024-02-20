import datetime
from typing import Optional, List, Dict, Tuple

import asyncio
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle

from bot import TG_Bot

data: Dict[str, List[Tuple[HistoricCandle, float]]] = {}


class StrategyConfig:
    take_profit = 2
    stop_los = 1
    dynamic_border = True  # статичные или динамические границы ордеров
    dynamic_border_mult = 1.25  # насколько двигаем границу, при достижении профита, тут нужны пояснения от Андрея
    falling_indicator_frame_count = 5
    volume = 0  # поизучать
    comission = 0.05  # в процентах
    money_in_order = 100000  # виртуальная сумма для сделки


# def absorbation_data(input_link):
#     _data = []

#     f = open("files_for_strategy/absorbation/{}".format(input_link), "r")
#     for line in f:
#         _slovar = {}
#         _strok = line.split(", ")
#         for item in _strok:
#             _slovar[item.split(": ")[0][1:-1]] = (
#                 item.split(": ")[1].replace("'", "").replace("\n", "")
#             )
#         _data.append(_slovar)
#     f.close()

#     _log, _results_share, _results_money, _locked_money = analisys(_data)

#     f = open(
#         "strategy_log_files/absorbation_results/{}".format("analys" + input_link),
#         "w",
#         encoding="utf-8",
#     )
#     for elem in _log:
#         strok = ""
#         for key, val in elem.items():
#             strok += key + " " + str(val) + "; "
#         f.write(strok + "\n")
#     f.write("\n")
#     f.write("Results(money):" + "\n")
#     for key, val in _results_money.items():
#         f.write(key + " " + str(val) + "\n")
#     f.close()
#     return


def analisys(ticker: str, candle_data: HistoricCandle) -> Optional[Dict]:
    if float(quotation_to_decimal(candle_data.high - candle_data.low)):
        candle_body_perc = (
            100
            * abs(float(quotation_to_decimal(candle_data.open - candle_data.close)))
            / float(quotation_to_decimal(candle_data.high - candle_data.low))
        )
    else:
        candle_body_perc = 0
    prev_candles = data[ticker]

    if len(prev_candles) < StrategyConfig.falling_indicator_frame_count:
        prev_candles.append((candle_data, candle_body_perc))
        return None
    prev_candle_data, prev_candle_data_body_perc = prev_candles[-1]

    _market_list = []

    for j in range(StrategyConfig.falling_indicator_frame_count):
        _market_list.append(
            float(quotation_to_decimal(prev_candles[len(prev_candles) - j - 1][0].open))
        )
    prev_candles.append((candle_data, candle_body_perc))
    if (
        (
            (
                (prev_candle_data.open <= prev_candle_data.close)
                & (candle_data.open > candle_data.close)
            )
            & (prev_candle_data_body_perc > 20)
            & (float(candle_body_perc) > 20)
        )
        & (prev_candle_data.open <= candle_data.open)
        & falling_indicator(_market_list)
    ):
        return {
            "ticker": ticker,
            "buy_date": candle_data.time,
            "buy_price": float(quotation_to_decimal(candle_data.close)),
            "number_of_shares": (
                float(StrategyConfig.money_in_order)
                * (100 - StrategyConfig.comission)
                / 100
            )
            / float(quotation_to_decimal(candle_data.close)),
            "money_in_order": float(StrategyConfig.money_in_order)
            * (100 - StrategyConfig.comission)
            / 100,
            "stop_los": float(quotation_to_decimal(candle_data.close))
            * float((100 - StrategyConfig.stop_los) / 100),
            "take_profit": float(quotation_to_decimal(candle_data.close))
            * float((100 + StrategyConfig.take_profit) / 100),
            "sell_date": "-",
            "sell_price": "-",
            "sell_volume(money)": "-",
            "profit(share)": "-",
            "profit(money)_minus_comission": "-",
            "comission(share)": float(quotation_to_decimal(candle_data.close))
            * StrategyConfig.comission
            / 100,
            "comission(money)": float(StrategyConfig.money_in_order)
            * StrategyConfig.comission
            / 100,
        }
    return None


# индикатор того, что рынок до появления сигнала - падающий
def falling_indicator(input_list):
    return (
        sum(input_list) / len(input_list) >= input_list[-1]
    )  # рынок "падающий" - если текущая цена ниже среднего за falling_indicator_frame_count дней


def change_order_border(cur_price, take_profit, stop_los):
    return (
        cur_price * (100 + take_profit) / 100,
        cur_price * (100 - stop_los) / 100,
    )  # new take profit / new stop loss


def config_optimization(input_link):
    _config = {}
    _best_config = {}
    _data = []

    f = open("files_for_strategy/absorbation/{}".format(input_link), "r")
    for line in f:
        _slovar = {}
        _strok = line.split(", ")
        for item in _strok:
            _slovar[item.split(": ")[0][1:-1]] = (
                item.split(": ")[1].replace("'", "").replace("\n", "")
            )
        _data.append(_slovar)
    f.close()

    _log, _results_share, _results_money, _locked_money = analisys(_data)

    return _best_config


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


async def fill_data(shares, client):
    purchases = []
    for share in shares:
        data[share["ticker"]] = []
    for share in shares:
        async for candle in client.get_all_candles(
            figi=share["figi"],
            from_=datetime.datetime.combine(
                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                datetime.time(6, 0),
            ).replace(tzinfo=datetime.timezone.utc)
            - datetime.timedelta(days=12),
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            purchase = analisys(share["ticker"], candle)
            if purchase is not None:
                # print(purchase)
                purchases.append(purchase)
    return purchases


async def send_message(tg_bot: TG_Bot, purchase):
    await tg_bot.send_signal(
        message=f"СТРАТЕГИЯ АНДРЕЯ СИГНАЛ НА ПОКУПКУ\n\nПокупка #{purchase['ticker']} {purchase['buy_date']:%d-%m-%Y}\nЦена: {purchase['buy_price']} руб\nКоличество: {round(purchase['number_of_shares'])}\nСумма сделки: {purchase['money_in_order']} руб\nСтоп-лосс: {purchase['stop_los']} руб\nТейк-профит: {purchase['take_profit']} руб",
        strategy="andrey",
        volume=0,
    )


async def market_review_andrey(tg_bot: TG_Bot):
    shares = await get_all_shares()
    async with AsyncClient(TOKEN) as client:
        purchases = await fill_data(shares, client)
        # print(len(purchases))
        for purchase in purchases:
            await send_message(tg_bot, purchase)
        await asyncio.sleep(30)
        work_hour = 1
        while True:
            if datetime.datetime.now().hour == work_hour:
                candles = []
                for share in shares:
                    async for candle in client.get_all_candles(
                        figi=share["figi"],
                        from_=now() - datetime.timedelta(days=1),
                        interval=CandleInterval.CANDLE_INTERVAL_DAY,
                    ):
                        candles.append((share["ticker"], candle))
                for candle in candles:
                    purchase = analisys(candle[0], candle[1])
                    if purchase is not None:
                        await send_message(tg_bot, purchase)
                await asyncio.sleep(60 * 60 * 23)
            else:
                await asyncio.sleep(60)
