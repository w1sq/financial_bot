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
        self.type = "trash"
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
                cross,
                falling_star,
                hammer_candle,
                escimo,
                middle_candle,
            ):
                candle_type = candle_function(self)
                if candle_type:
                    self.type = candle_type

    def __str__(self):
        return f"Open: {self.open}, High: {self.high}, Low: {self.low}, Close: {self.close}, Volume: {self.volume}, Time: {self.time}, High shadow: {self.high_shadow_val}, Low shadow: {self.low_shadow_val}, Length: {self.length}, Body: {self.body_val}, Length perc: {self.length_perc}, High shadow perc: {self.high_shadow_perc}, Low shadow perc: {self.low_shadow_perc}, Body perc: {self.body_perc}, Color: {self.color}, Type: {self.type}"


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
    if (
        candle.length_perc >= 1.5
        and candle.body_perc >= 10
        and candle.low_shadow_perc >= 75
    ):
        return candle.color + "_hammer"
    elif (
        candle.length_perc >= 1.5
        and candle.body_perc >= 10
        and candle.high_shadow_perc >= 75
    ):
        return candle.color + "_reversed_hammer"

    return False


def cross(
    candle: CustomCandle,
) -> str | bool:
    if (
        candle.length_perc >= 1.5
        and candle.body_perc <= 10
        and candle.low_shadow_perc >= 75
    ):
        return candle.color + "_cross"

    return False


def falling_star(
    candle: CustomCandle,
) -> str | bool:
    if (
        candle.length_perc >= 1.5
        and candle.body_perc <= 10
        and candle.high_shadow_perc >= 75
    ):
        return candle.color + "_falling_star"

    return False


def middle_candle(candle: CustomCandle) -> str | bool:
    if (
        candle.length_perc >= 1.5
        and 20 < candle.low_shadow_perc
        and 20 < candle.body_perc
        and 20 < candle.high_shadow_perc
    ):
        return candle.color + "_middle"

    return False


def escimo(
    candle: CustomCandle,
) -> str | bool:  # свеча 'эскимо' - большое зеленое тело, нижняя тень больше верхней
    if (
        candle.length_perc >= 1.5
        and candle.high_shadow_perc < candle.low_shadow_perc
        and 40 < candle.body_perc < 80
        and candle.color == "green"
    ):
        return "escimo"

    return False
