from dataclasses import dataclass
from typing import List


@dataclass
class Candle:
    """Class representing trading candle"""

    high_shadow_val: float
    low_shadow_val: float
    high_shadow_perc: float
    low_shadow_perc: float
    body_val: float
    body_perc: float
    length: float
    color: str
    type: str

    def to_dict(self) -> dict:
        return {
            "high_shadow_val": self.high_shadow_val,
            "low_shadow_val": self.low_shadow_val,
            "high_shadow_perc": self.high_shadow_perc,
            "low_shadow_perc": self.low_shadow_perc,
            "body_val": self.body_val,
            "body_perc": self.body_perc,
            "length": self.length,
            "color": self.color,
            "type": self.type,
        }


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
    candle: Candle


def analysis_input_data(
    input_link: str,
) -> tuple[List[TradeData], List[Candle], List[str]]:
    f = open(input_link, "r")
    situation = []
    candles = []
    candles_types = []

    for line in f:
        (
            info_name,
            info_type,
            day_data_date,
            day_data_time,
            day_data_open,
            day_data_high,
            day_data_low,
            day_data_close,
            day_data_vol,
        ) = line.split(",")
        (
            day_data_open,
            day_data_high,
            day_data_low,
            day_data_close,
            day_data_vol,
        ) = map(
            float,
            (
                day_data_open,
                day_data_high,
                day_data_low,
                day_data_close,
                day_data_vol,
            ),
        )

        candle_low_shadow_val = min(day_data_open, day_data_close) - day_data_low
        candle_body_val = abs(day_data_open - day_data_close)
        candle_high_shadow_val = day_data_high - max(day_data_open, day_data_close)

        if (
            day_data_high == day_data_low
        ):  # отработка нуля, пример 20220107 в файле IMOEX_2022-2023_220101_230910.txt
            candle_low_shadow_perc = 0
            candle_high_shadow_perc = 0
            candle_body_perc = 0
        else:
            candle_high_shadow_perc = (
                100 * candle_high_shadow_val / (day_data_high - day_data_low)
            )
            candle_low_shadow_perc = (
                100 * candle_low_shadow_val / (day_data_high - day_data_low)
            )
            candle_body_perc = 100 * candle_body_val / (day_data_high - day_data_low)
        candle_length = day_data_high - day_data_low

        if day_data_open > day_data_close:
            candle_color = "red"
        else:
            candle_color = "green"

        candle = Candle(
            high_shadow_val=candle_high_shadow_val,
            low_shadow_val=candle_low_shadow_val,
            high_shadow_perc=candle_high_shadow_perc,
            low_shadow_perc=candle_low_shadow_perc,
            body_val=candle_body_val,
            body_perc=candle_body_perc,
            length=candle_length,
            color=candle_color,
            type=None,
        )
        candle_type = candle_type_analysis(candle, day_data_vol)
        candle.type = candle_type
        day_data = TradeData(
            date=day_data_date,
            time=day_data_time,
            open=day_data_open,
            high=day_data_high,
            low=day_data_low,
            close=day_data_close,
            volume=day_data_vol,
            candle=candle,
        )

        situation.append(day_data)
        candles.append(candle)
        candles_types.append(candle.type)

    f.close()

    return situation, candles, candles_types


def candle_type_analysis(candle: Candle, vol) -> str:
    vol_treshold = (
        0  # объем рынка, ниже которого определение типа свечи нецелесообразно
    )

    if vol_treshold < vol:
        for candle_function in (
            cross_5,
            hammer_candle_25,
            star_candle_25,
            escimo,
            hammer_candle,
            star_candle,
            middle_candle,
        ):
            checked_candle = candle_function(candle)
            if checked_candle:
                return checked_candle

    return "trash"


def hammer_candle(candle: Candle) -> str | bool:
    treshold = 0  # длина свечи (от лоу до хай), ниже которого определение типа свечи нецелесообразно

    if (
        treshold < candle.length
        and 0 < candle.high_shadow_perc < 15
        and 0 < candle.body_perc < 15
        and 0 < candle.low_shadow_perc < 100
    ):
        return candle.color + "_hammer"

    return False


def star_candle(candle: Candle) -> str | bool:
    treshold = 0  # длина свечи (от лоу до хай), ниже которого определение типа свечи нецелесообразно

    if (
        treshold < candle.length
        and 0 < candle.low_shadow_perc < 15
        and 0 < candle.body_perc < 15
        and 0 < candle.high_shadow_perc < 100
    ):
        return candle.color + "_star"

    return False


def middle_candle(candle: Candle) -> str | bool:
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
    candle: Candle,
) -> str | bool:  # свеча молот - где "тело + верхняя часть" в четверть
    treshold = 0

    if treshold < candle.length and 75 <= candle.low_shadow_perc < 100:
        return candle.color + "_hammer_25"

    return False


def star_candle_25(
    candle: Candle,
) -> str | bool:  # свеча звезда - где "тело + нижняя часть" в четверть
    treshold = 0

    if treshold < candle.length and 75 <= candle.high_shadow_perc < 100:
        return candle.color + "_star_25"

    return False


def escimo(
    candle: Candle,
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


def cross_5(candle: Candle) -> str | bool:  # свеча 'крест' - узкое тело
    if candle.body_perc <= 5:
        return "cross_5"

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
        if situation.candle.type == "cross_5":
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


def get_out_data(link):
    situation, candles, candles_only_types = analysis_input_data(link)
    pure_and_cross_candles_list = pure_candles_list(situation)

    with open(f"out/pure candles {link}", "w", encoding="utf-8") as file:
        for elem in pure_and_cross_candles_list[0]:
            file.write(elem + "\n")

    with open(f"out/cross candles {link}", "w", encoding="utf-8") as file:
        for elem in pure_and_cross_candles_list[1]:
            file.write(elem + "\n")

    with open(f"out/triggers {inp_link}", "w", encoding="utf-8") as file:
        for elem in trigger_hammer_middle(situation):
            file.write(elem + "\n")

    with open(f"out/all candles {inp_link}", "w", encoding="utf-8") as file:
        for elem in candles_only_types:
            file.write(elem + "\n")

    with open(f"out/candles data {inp_link}", "w", encoding="utf-8") as file:
        for elem in candles:
            for key in elem.to_dict():
                file.write(key + ": " + str(elem.to_dict()[key]) + "; ")
            file.write("\n")


if __name__ == "__main__":
    inp_link = "IMOEX_2018-2019_180101_191231.txt"
    get_out_data(inp_link)

    inp_link = "IMOEX_2020-2021_200101_211231.txt"
    get_out_data(inp_link)

    inp_link = "IMOEX_2022-2023_220101_230910.txt"
    get_out_data(inp_link)
