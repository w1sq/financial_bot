import datetime
from typing import Optional, List, Dict, Tuple

import pandas
import asyncio
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest.utils import quotation_to_decimal, now
from tinkoff.invest import AsyncClient, CandleInterval, HistoricCandle

from bot import TG_Bot

configs = {
    "BR": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 5600,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 570,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "CR": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 2600,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 990,  # экспоненциальная средняя (по максимуму)
        "comission": 0.02,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "Eu": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 2300,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 620,  # экспоненциальная средняя (по максимуму)
        "comission": 0.02,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "GAZR": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 5200,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 800,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "RTS": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 4400,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 400,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "SBRF": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 4400,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 200,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "Si": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 1600,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 800,  # экспоненциальная средняя (по максимуму)
        "comission": 0.02,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "VTBR": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 2200,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 170,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "OZON": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 2000,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 170,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "YNDF": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 2000,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 170,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
    "NG": {
        "money_to_buy": 1000000,  # стартовый капитал
        "sma_frame(close)": 2700,  # скользящая средняя (по клозу)
        "ema_frame(maximum)": 70,  # экспоненциальная средняя (по максимуму)
        "comission": 0.05,  # комиссия в %
        "shares_in_lot": 1,  # кол-во акций в одном лоте
        "reinvestition": False,  # стратегия с реинвестицией или без
        "long_flag": True,  # флаг на стратегию в лонг
        "short_flag": True,  # флаг на стратегию в шорт
    },
}

strategy_data: Dict[str, List[HistoricCandle]] = {}


purchases: Dict[str, Dict] = {}


in_order_long: Dict[str, bool] = {}
in_order_short: Dict[str, bool] = {}
ema: Dict[str, float] = {}
sma_sum: Dict[str, float] = {}


def strategy(ticker: str, candle_data: HistoricCandle):
    local_config = configs[ticker]
    local_data = strategy_data[ticker]
    local_in_order_long = in_order_long[ticker]
    local_in_order_short = in_order_short[ticker]
    _capital = float(local_config["money_to_buy"])
    _capital_max = _capital
    local_ema = ema[ticker]
    local_sma_sum = sma_sum[ticker]
    _purchase = purchases[ticker]
    _purchase_list = []

    # отсупаем до напитания индикаторов - _config['sma_frame(close)']
    # считаем сумму для простой скользящей (по закрытию)
    if len(local_data) - 1 == local_config["sma_frame(close)"]:
        for i in range(local_config["sma_frame(close)"]):
            local_sma_sum += float(quotation_to_decimal(local_data[i].close))

        # считаем экспоненциальную среднюю (по максимуму бара)
        _df = pandas.DataFrame(
            {
                "maximum": [
                    float(quotation_to_decimal(candle.high)) for candle in local_data
                ]
            }
        )
        _df["ema"] = (
            _df["maximum"]
            .ewm(span=local_config["ema_frame(maximum)"], adjust=False, min_periods=5)
            .mean()
        )
        local_ema = _df.values[-1][1]
    elif len(local_data) - 1 > local_config["sma_frame(close)"]:
        # for i in range(local_config["sma_frame(close)"], len(_data)):
        # индикатор простой скользящей (по закрытию)
        local_sma_sum = (
            local_sma_sum
            - float(
                quotation_to_decimal(
                    local_data[-local_config["sma_frame(close)"]].close
                )
            )
            + float(quotation_to_decimal(local_data[-1].close))
        )
        local_sma_sum = local_sma_sum / local_config["sma_frame(close)"]

        # индикатор экспоненциальную среднюю (по максимуму бара)
        _weight_factor = 2 / (local_config["ema_frame(maximum)"] + 1)
        local_ema = local_ema + _weight_factor * (
            float(quotation_to_decimal(local_data[-1].high)) - local_ema
        )

        # проверяем условие, что хватает денег на лот
        _lot_price = float(quotation_to_decimal(local_data[-1].close)) * float(
            local_config["shares_in_lot"]
        )
        if _capital > _lot_price:
            # стратегия с реинвестированием
            if local_config["reinvestition"]:
                # лонг
                if local_config["long_flag"]:
                    # заходим в лонг
                    if (
                        (local_sma_sum < local_ema)
                        and not (local_in_order_long)
                        and not (local_in_order_short)
                    ):

                        _purchase = long_input(
                            candle_data,
                            local_config,
                            _capital,
                            local_sma_sum,
                            local_ema,
                            0,
                        )
                        local_in_order_long = True
                    # выходим из лонга
                    if (
                        (local_sma_sum > local_ema)
                        and (local_in_order_long)
                        and not (local_in_order_short)
                    ):
                        _purchase, _capital, _capital_max = long_output(
                            candle_data,
                            _purchase,
                            local_config,
                            local_sma_sum,
                            local_ema,
                            _capital_max,
                            _capital_max,
                            0,
                        )
                        _purchase["ticker"] = ticker
                        _purchase_list.append(_purchase)
                        _purchase = {}
                        local_in_order_long = False
                # шорт
                if local_config["short_flag"]:
                    # заходим в шорт
                    if (
                        (local_sma_sum > local_ema)
                        and not (local_in_order_short)
                        and not (local_in_order_long)
                    ):
                        print("Заходим в лонг")
                        _purchase = short_input(
                            candle_data,
                            local_config,
                            _capital,
                            local_sma_sum,
                            local_ema,
                            0,
                        )
                        local_in_order_short = True
                    # выходим из шорта
                    if (
                        (local_sma_sum < local_ema)
                        and local_in_order_short
                        and not (local_in_order_long)
                    ):
                        _purchase, _capital, _capital_max = short_output(
                            candle_data,
                            _purchase,
                            local_config,
                            local_sma_sum,
                            local_ema,
                            _capital,
                            _capital_max,
                            # _capital_max,
                            0,
                        )
                        _purchase["ticker"] = ticker
                        _purchase_list.append(_purchase)
                        _purchase = {}
                        local_in_order_short = False
            # стратегия без реинвестирования
            else:
                # деньги, не участвующие в сделке
                _frozen_money = 0
                if _capital > float(local_config["money_to_buy"]):
                    _frozen_money = _capital - float(local_config["money_to_buy"])
                # лонг
                if local_config["long_flag"]:
                    # заходим в лонг
                    if (
                        (local_sma_sum < local_ema)
                        and not (local_in_order_long)
                        and not (local_in_order_short)
                    ):
                        _purchase = long_input(
                            candle_data,
                            local_config,
                            _capital,
                            local_sma_sum,
                            local_ema,
                            _frozen_money,
                        )
                        local_in_order_long = True
                    # выходим из лонга
                    if (
                        (local_sma_sum > local_ema)
                        and (local_in_order_long)
                        and not (local_in_order_short)
                    ):
                        _purchase, _capital, _capital_max = long_output(
                            candle_data,
                            _purchase,
                            local_config,
                            local_sma_sum,
                            local_ema,
                            _capital_max,
                            local_config["money_to_buy"],
                            _frozen_money,
                        )
                        _purchase["ticker"] = ticker
                        _purchase_list.append(_purchase)
                        _purchase = {}
                        local_in_order_long = False
                # шорт
                if local_config["short_flag"]:
                    # заходим в шорт
                    if (
                        (local_sma_sum > local_ema)
                        and not (local_in_order_short)
                        and not (local_in_order_long)
                    ):
                        _purchase = short_input(
                            candle_data,
                            local_config,
                            _capital,
                            local_sma_sum,
                            local_ema,
                            _frozen_money,
                        )
                        local_in_order_short = True
                    # выходим из шорта
                    if (
                        (local_sma_sum < local_ema)
                        and local_in_order_short
                        and not (local_in_order_long)
                    ):
                        _purchase, _capital, _capital_max = short_output(
                            candle_data,
                            _purchase,
                            local_config,
                            local_sma_sum,
                            local_ema,
                            _capital,
                            _capital_max,
                            local_config["money_to_buy"],
                        )
                        _purchase["ticker"] = ticker
                        _purchase_list.append(_purchase)
                        _purchase = {}
                        local_in_order_short = False

    # добавляем последнюю сделку, если она не была закрыта ранее
    # if local_in_order_long:
    #     _purchase_list.append(_purchase)
    # if local_in_order_short:
    #     _purchase_list.append(_purchase)
    local_data.append(candle_data)
    ema[ticker] = local_ema
    sma_sum[ticker] = local_sma_sum
    in_order_long[ticker] = local_in_order_long
    in_order_short[ticker] = local_in_order_short
    purchases[ticker] = _purchase
    if _purchase_list:
        return _purchase_list
    else:
        return None


def long_input(_cur_data, _config, _cur_capital, _sma, _ema, _cur_frozen_money):
    _purchase_temp = {}
    _cur_lot_prize = float(quotation_to_decimal(_cur_data.open)) * float(
        _config["shares_in_lot"]
    )  #!покупаем по открытию

    # _purchase_temp["buy_date"] = _cur_data["date"]
    _purchase_temp["buy_time"] = _cur_data.time
    _purchase_temp["type"] = "long"
    _purchase_temp["sma(close)_in"] = _sma
    _purchase_temp["ema(high)_in"] = _ema
    _purchase_temp["buy_price"] = float(quotation_to_decimal(_cur_data.open))
    _purchase_temp["volume(lots)"] = (
        (_cur_capital - _cur_frozen_money)
        * float(100 - _config["comission"])
        / 100
        // float(_cur_lot_prize)
    )
    _purchase_temp["volume(shares)"] = _purchase_temp["volume(lots)"] * float(
        _config["shares_in_lot"]
    )
    _purchase_temp["shares_in_lot"] = float(_config["shares_in_lot"])
    _purchase_temp["money_in_order"] = _purchase_temp["volume(lots)"] * _cur_lot_prize
    _purchase_temp["frozen_money"] = _cur_frozen_money  # убрать?
    _purchase_temp["comission_buy"] = (
        _purchase_temp["money_in_order"] * float(_config["comission"]) / 100
    )
    _purchase_temp["resid"] = (
        _cur_capital
        - _cur_frozen_money
        - _purchase_temp["comission_buy"]
        - _purchase_temp["money_in_order"]
    )

    return _purchase_temp


def long_output(
    _cur_data,
    _purchase,
    _config,
    _sma,
    _ema,
    _capital_max,
    _capital_for_drawdawn,
    _cur_frozen_money,
):

    _cur_purchase = _purchase
    _cur_lot_prize = float(quotation_to_decimal(_cur_data.open)) * float(
        _config["shares_in_lot"]
    )  #!покупаем по открытию

    # _cur_purchase["sell_date"] = _cur_data["date"]
    _cur_purchase["sell_time"] = _cur_data.time
    _cur_purchase["sma(close)_out"] = _sma
    _cur_purchase["ema(high)_out"] = _ema
    _cur_purchase["sell_price"] = float(quotation_to_decimal(_cur_data.open))
    _cur_purchase["sell_money"] = (
        float(_cur_purchase["volume(lots)"] * _cur_lot_prize)
        * float(100 - _config["comission"])
        / 100
    )
    _cur_purchase["comission_sell"] = (
        float(_cur_purchase["volume(lots)"] * _cur_lot_prize)
        * float(_config["comission"])
        / 100
    )
    _cur_purchase["comission_deal"] = (
        _cur_purchase["comission_buy"] + _cur_purchase["comission_sell"]
    )
    _capital = _cur_purchase["resid"] + _cur_purchase["sell_money"] + _cur_frozen_money
    _cur_purchase["capital"] = _capital

    _capital_max = max(_capital_max, _capital)
    _drawdawn = _capital_max - _capital

    _cur_purchase["drawdawn"] = _drawdawn
    _cur_purchase["drawdawn_%"] = _drawdawn / (_capital_for_drawdawn) * 100

    return _cur_purchase, _capital, _capital_max


def short_input(_cur_data, _config, _cur_capital, _sma, _ema, _cur_frozen_money):
    _purchase_temp = {}
    _cur_lot_prize = float(quotation_to_decimal(_cur_data.open)) * float(
        _config["shares_in_lot"]
    )  #!покупаем по открытию

    # _purchase_temp["buy_date"] = _cur_data["date"]
    _purchase_temp["buy_time"] = _cur_data.time
    _purchase_temp["type"] = "short"
    _purchase_temp["sma(close)_in"] = _sma
    _purchase_temp["ema(high)_in"] = _ema
    _purchase_temp["buy_price"] = float(quotation_to_decimal(_cur_data.open))
    _purchase_temp["volume(lots)"] = (
        (_cur_capital - _cur_frozen_money)
        * float(100 - _config["comission"])
        / 100
        // float(_cur_lot_prize)
    )
    _purchase_temp["volume(shares)"] = _purchase_temp["volume(lots)"] * float(
        _config["shares_in_lot"]
    )
    _purchase_temp["shares_in_lot"] = float(_config["shares_in_lot"])
    _purchase_temp["money_in_order"] = _purchase_temp["volume(lots)"] * _cur_lot_prize
    _purchase_temp["frozen_money"] = _cur_frozen_money
    _purchase_temp["comission_buy"] = (
        _purchase_temp["money_in_order"] * float(_config["comission"]) / 100
    )
    _purchase_temp["resid"] = (
        _cur_capital
        - _cur_frozen_money
        - _purchase_temp["comission_buy"]
        - _purchase_temp["money_in_order"]
    )

    return _purchase_temp


def short_output(
    _cur_data,
    _purchase,
    _config,
    _sma,
    _ema,
    _capital,
    _capital_max,
    _capital_for_drawdawn,
):
    _cur_purchase = _purchase
    _cur_lot_prize = float(quotation_to_decimal(_cur_data.open)) * float(
        _config["shares_in_lot"]
    )  #!покупаем по открытию

    # _cur_purchase["sell_date"] = _cur_data["date"]
    _cur_purchase["sell_time"] = _cur_data.time
    _cur_purchase["sma(close)_out"] = _sma
    _cur_purchase["ema(high)_out"] = _ema
    _cur_purchase["sell_price"] = float(quotation_to_decimal(_cur_data.open))
    _cur_purchase["sell_money"] = float(_cur_purchase["volume(lots)"] * _cur_lot_prize)
    _cur_purchase["comission_sell"] = (
        float(_cur_purchase["volume(lots)"] * _cur_lot_prize)
        * float(_config["comission"])
        / 100
    )
    _cur_purchase["comission_deal"] = (
        _cur_purchase["comission_buy"] + _cur_purchase["comission_sell"]
    )
    _capital = (
        _capital
        - _cur_purchase["comission_deal"]
        + _cur_purchase["money_in_order"]
        - _purchase["sell_money"]
    )  # + _cur_purchase['resid'] + _cur_frozen_money
    _cur_purchase["capital"] = _capital

    _capital_max = max(_capital_max, _capital)
    _drawdawn = _capital_max - _capital

    _cur_purchase["drawdawn"] = _drawdawn
    _cur_purchase["drawdawn_%"] = _drawdawn / (_capital_for_drawdawn) * 100

    return _cur_purchase, _capital, _capital_max


async def get_all_shares():
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        shares = []
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                if (
                    item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]
                    and item.ticker in configs.keys()
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


async def get_ticker_by_figi(figi: str) -> str:
    async with AsyncClient(TOKEN) as client:
        instruments: InstrumentsService = client.instruments
        for method in ["shares"]:
            for item in (await getattr(instruments, method)()).instruments:
                if item.exchange in ["MOEX", "MOEX_EVENING_WEEKEND"]:
                    if item.figi == figi:
                        return item.ticker


# TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw" #readonly
TOKEN = "t.aVvt9V0XFMyQFrfVQgSJsxtNjDycKY-vgV--mEsk_MBZY1n-lWH58-1U2dMvw35ztBASwwakPdqcb1IRMhvwLg"  # full access
working_hours = range(10, 24)


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


async def fill_data(shares, client):
    local_purchases = []
    for share in shares:
        strategy_data[share["ticker"]] = []
        in_order_long[share["ticker"]] = False
        in_order_short[share["ticker"]] = False
        ema[share["ticker"]] = 0
        sma_sum[share["ticker"]] = 0
        purchases[share["ticker"]] = {}
    for share in shares:
        async for candle in client.get_all_candles(
            figi=share["figi"],
            from_=datetime.datetime.combine(
                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                datetime.time(6, 0),
            ).replace(tzinfo=datetime.timezone.utc)
            - datetime.timedelta(days=20),
            interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
        ):
            purchase_list = strategy(share["ticker"], candle)
            if purchase_list is not None:
                local_purchases.extend(purchase_list)
    return local_purchases


async def send_message(tg_bot: TG_Bot, purchase):
    fstring = f"СТРАТЕГИЯ ГЕОРГИЯ\n\nПокупка {purchase['ticker']} {purchase['buy_time']+datetime.timedelta(hours=3):%d-%m-%Y %H:%M}\n"
    for key, value in purchase.items():
        if key not in ["ticker", "buy_time"]:
            fstring += f"{key}: {value}\n"
    await tg_bot.send_signal(
        message=fstring,
        strategy="george",
        volume=0,
    )


async def market_review_george(tg_bot: TG_Bot):
    shares = await get_all_shares()
    async with AsyncClient(TOKEN) as client:
        local_purchases = await fill_data(shares, client)
        for purchase in local_purchases:
            await send_message(tg_bot, purchase)
        # await asyncio.sleep(30)
        # work_hour = 1
        # while True:
        #     if datetime.datetime.now().hour == work_hour:
        #         candles = []
        #         for share in shares:
        #             async for candle in client.get_all_candles(
        #                 figi=share["figi"],
        #                 from_=now() - datetime.timedelta(days=1),
        #                 interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
        #             ):
        #                 candles.append((share["ticker"], candle))
        #         for candle in candles:
        #             purchase = strategy(candle[0], candle[1])
        #             if purchase is not None:
        #                 await send_message(tg_bot, purchase)
        #         await asyncio.sleep(60 * 60 * 23)
        #     else:
        #         await asyncio.sleep(60)