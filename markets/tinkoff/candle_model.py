from typing import List
from dataclasses import dataclass


from tinkoff.invest import HistoricCandle
from tinkoff.invest.utils import quotation_to_decimal


@dataclass
class CustomCandle:
    """Class representing trading candle"""

    def __init__(self, candle: HistoricCandle):
        self.open = float(quotation_to_decimal(candle.open))
        self.high = float(quotation_to_decimal(candle.high))
        self.low = float(quotation_to_decimal(candle.low))
        self.close = float(quotation_to_decimal(candle.close))
        self.volume = candle.volume
        self.time = candle.time
        self.high_shadow_val = self.high - max(self.open, self.close)
        self.low_shadow_val = min(self.open, self.close) - self.low
        self.length = self.high - self.low
        self.body_val = abs(self.open - self.close)
        self.length_perc = self.length / self.high * 100
        self.type = None
        if self.length == 0:
            self.low_shadow_perc = 0.0
            self.high_shadow_perc = 0.0
            self.body_perc = 0.0
        else:
            self.high_shadow_perc = 100 * self.high_shadow_val / self.length
            self.low_shadow_perc = 100 * self.low_shadow_val / self.length
            self.body_perc = 100 * self.body_val / self.length
        if self.open > self.close:
            self.color = "red"
        else:
            self.color = "green"

    def calc_type(self):
        vol_treshold = (
            0  # объем рынка, ниже которого определение типа свечи нецелесообразно
        )
        if vol_treshold < self.volume:
            for candle_function in (
                cross_5_low,
                cross_5_high,
                hammer_candle_25,
                star_candle_25,
                escimo,
                hammer_candle,
                star_candle,
                middle_candle,
            ):
                candle_type = candle_function(self)
                if candle_type:
                    self.type = candle_type
                    return
        self.type = "trash"


@dataclass
class TradeData:
    """Class representing results of trading period"""

    date: str
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    candle: CustomCandle


def hammer_candle(candle: CustomCandle) -> str | bool:
    treshold = 0  # длина свечи (от лоу до хай), ниже которого определение типа свечи нецелесообразно

    if (
        treshold < candle.length
        and 0 < candle.high_shadow_perc < 15
        and 0 < candle.body_perc < 15
        and 0 < candle.low_shadow_perc < 100
    ):
        return candle.color + "_hammer"

    return False


def star_candle(candle: CustomCandle) -> str | bool:
    treshold = 0  # длина свечи (от лоу до хай), ниже которого определение типа свечи нецелесообразно

    if (
        treshold < candle.length
        and 0 < candle.low_shadow_perc < 15
        and 0 < candle.body_perc < 15
        and 0 < candle.high_shadow_perc < 100
    ):
        return candle.color + "_star"

    return False


def middle_candle(candle: CustomCandle) -> str | bool:
    treshold = 0  # длина свечи (от лоу до хай), ниже которого определение типа свечи нецелесообразно

    if (
        treshold < candle.length
        and 20 < candle.low_shadow_perc
        and 20 < candle.body_perc
        and 20 < candle.high_shadow_perc
    ):
        return candle.color + "_middle"

    return False


def trigger_hammer_middle(
    _situation: List[TradeData],
):  # сначала свеча "молот", потом свеча "мидл", пробелы в виде "trash" - допустимы
    signals_list = []

    pure_situation = []
    for situation in _situation:
        if situation.candle.type != "trash":
            pure_situation.append(situation)

    for i in range(1, len(pure_situation)):
        if (
            "hammer" in pure_situation[i - 1].candle.type
            and "middle" in pure_situation[i].candle.type
        ):
            signals_list.append(
                pure_situation[i - 1].date
                + "-"
                + pure_situation[i].date
                + " паттерн молот-миддл"
            )

    return signals_list


def hammer_candle_25(
    candle: CustomCandle,
) -> str | bool:  # свеча молот - где "тело + верхняя часть" в четверть
    treshold = 0

    if treshold < candle.length and 60 <= candle.low_shadow_perc < 100:
        return candle.color + "_hammer_25"

    return False


def star_candle_25(
    candle: CustomCandle,
) -> str | bool:  # свеча звезда - где "тело + нижняя часть" в четверть
    treshold = 0

    if treshold < candle.length and 60 <= candle.high_shadow_perc < 100:
        return candle.color + "_star_25"

    return False


def escimo(
    candle: CustomCandle,
) -> str | bool:  # свеча 'эскимо' - большое зеленое тело, нижняя тень больше верхней
    treshold = 0  # длина свечи (от лоу до хай), ниже которого определение типа свечи нецелесообразно

    if (
        treshold < candle.length
        and candle.high_shadow_perc < candle.low_shadow_perc
        and 40 < candle.body_perc < 80
        and candle.color == "green"
    ):
        return "escimo"

    return False


def cross_5_low(
    candle: CustomCandle,
) -> (
    str | bool
):  # свеча 'крест лоу' - узкое тело, маленькая верхняя тень, большое нисходящее движение
    if candle.body_perc <= 5 and candle.high_shadow_perc <= 30:
        return "cross_5_low"

    return False


def cross_5_high(
    candle: CustomCandle,
) -> (
    str | bool
):  # свеча 'крест' - узкое тело, маленькая большая тень, большое восходящее движение
    if candle.body_perc <= 5 and candle.low_shadow_perc <= 30:
        return "cross_5_high"

    return False


def pure_candles_list(situations: List[TradeData]):
    pure_candles = []
    cross_candles = []

    for index, situation in enumerate(situations):
        quality = "Bad_length"  # оцениваем качество свечи: "длина < 1.5% цены" - "bad", "1.5% цены <= длина < 2% цены" - "normal", "2% цены < длина" - "good"
        _candle_div_price = 100 * (situation.high - situation.low) / situation.low

        if 1.5 <= _candle_div_price < 2:
            quality = "Normal_length"
        elif 2 < _candle_div_price:
            quality = "Good_length"

        vol_change_yest = "normal"  # отслеживаем изменения объёмов (х2) относительно "вчера", "3-дневного среднего", "5-дневного среднего"
        vol_change_3_day = "normal"
        vol_change_5_day = "normal"

        if 1 <= index:
            if situation.volume >= 2 * situations[index - 1].volume:
                vol_change_yest = "yest_day_vol_alert"

        if 3 <= index:
            if (
                situation.volume
                >= 2
                * (
                    situations[index - 1].volume
                    + situations[index - 2].volume
                    + situations[index - 3].volume
                )
                / 3
            ):
                vol_change_3_day = "3_day_vol_alert"

        if 5 <= index:
            if (
                situation.volume
                >= 2
                * (
                    situations[index - 1].volume
                    + situations[index - 2].volume
                    + situations[index - 3].volume
                    + situations[index - 4].volume
                    + situations[index - 5].volume
                )
                / 5
            ):
                vol_change_5_day = "5_day_vol_alert"

        if situation.candle.type != "trash":
            pure_candles.append(
                situation.date
                + " "
                + situation.candle.type
                + " "
                + quality
                + " "
                + vol_change_yest
                + " "
                + vol_change_3_day
                + " "
                + vol_change_5_day
            )
        if (
            situation.candle.type == "cross_5_low"
            or situation.candle.type == "cross_5_high"
        ):
            cross_candles.append(
                situation.date
                + " "
                + situation.candle.type
                + " "
                + quality
                + " "
                + vol_change_yest
                + " "
                + vol_change_3_day
                + " "
                + vol_change_5_day
            )

    return pure_candles, cross_candles
