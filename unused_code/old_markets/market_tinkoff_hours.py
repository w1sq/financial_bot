from dataclasses import dataclass

import asyncio
import datetime
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    AsyncClient,
    CandleInterval,
)
import tinkoff


from bot import TG_Bot
from markets.tinkoff.candle_model import candle_type_analysis

blue_chips = {
    "BBG004S68B31": "ALRS",
    "BBG004730RP0": "GAZP",
    "BBG004731489": "GMKN",
    "BBG004S68473": "IRAO",
    "BBG004731032": "LKOH",
    "BBG004RVFCY3": "MGNT",
    "BBG004S681W1": "MTSS",
    "BBG00475KKY8": "NVTK",
    "BBG000R607Y3": "PLZL",
    "BBG004731354": "ROSN",
    "BBG008F2T3T2": "RUAL",
    "BBG004730N88": "SBER",
    "BBG0047315D0": "SNGS",
    "BBG004RVFFC0": "TATN",
    "BBG006L8G4H1": "YNDX",
}
chips_names = {
    "ALRS": "АЛРОСА",
    "GAZP": "Газпром",
    "GMKN": "Норильский никель",
    "IRAO": "Интер РАО ЕЭС",
    "LKOH": "ЛУКОЙЛ",
    "MGNT": "Магнит",
    "MTSS": "МТС",
    "NVTK": "НОВАТЭК",
    "PLZL": "Полюс",
    "ROSN": "Роснефть",
    "RUAL": "РУСАЛ",
    "SBER": "Сбер Банк",
    "SNGS": "Сургутнефтегаз",
    "TATN": "Татнефть",
    "YNDX": "Yandex",
}

chips_lots = {
    "ALRS": 10,
    "GAZP": 10,
    "GMKN": 1,
    "IRAO": 100,
    "LKOH": 1,
    "MGNT": 1,
    "MTSS": 10,
    "NVTK": 1,
    "PLZL": 1,
    "ROSN": 1,
    "RUAL": 10,
    "SBER": 10,
    "SNGS": 100,
    "TATN": 1,
    "YNDX": 1,
}


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
    type: str | None

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


TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw"


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


async def market_review(tg_bot: TG_Bot):
    time_stamp = datetime.datetime.now().minute
    async with AsyncClient(TOKEN) as client:
        while True:
            time_now = datetime.datetime.now()
            if time_now.minute == time_stamp:
                for figi, ticker in blue_chips.items():
                    async for candle in client.get_all_candles(
                        figi=figi,
                        from_=tinkoff.invest.utils.now()
                        - datetime.timedelta(minutes=60 + time_stamp),
                        to=tinkoff.invest.utils.now(),
                        # from_=now(),
                        interval=CandleInterval.CANDLE_INTERVAL_HOUR,
                    ):
                        if candle.time.hour == time_now.hour - 4:
                            # print(ticker, candle)
                            candle_high_shadow_val = float(
                                quotation_to_decimal(
                                    candle.high - max(candle.open, candle.close)
                                )
                            )
                            candle_low_shadow_val = float(
                                quotation_to_decimal(
                                    min(candle.open, candle.close) - candle.low
                                )
                            )
                            price_delta = float(
                                quotation_to_decimal(candle.high - candle.low)
                            )
                            percent_price_delta = round(
                                (
                                    (
                                        float(quotation_to_decimal(candle.close))
                                        - float(quotation_to_decimal(candle.open))
                                    )
                                    / (
                                        (
                                            float(quotation_to_decimal(candle.high))
                                            + float(quotation_to_decimal(candle.low))
                                        )
                                        / 2
                                    )
                                )
                                * 100,
                                2,
                            )
                            candle_body_val = float(
                                quotation_to_decimal(abs(candle.open - candle.close))
                            )
                            if (
                                price_delta == 0
                            ):  # отработка нуля, пример 20220107 в файле IMOEX_2022-2023_220101_230910.txt
                                candle_low_shadow_perc = 0
                                candle_high_shadow_perc = 0
                                candle_body_perc = 0
                            else:
                                candle_high_shadow_perc = (
                                    100 * candle_high_shadow_val / price_delta
                                )
                                candle_low_shadow_perc = (
                                    100 * candle_low_shadow_val / price_delta
                                )
                                candle_body_perc = 100 * candle_body_val / price_delta
                            if candle.open > candle.close:
                                candle_color = "red"
                            else:
                                candle_color = "green"
                            custom_candle = Candle(
                                high_shadow_val=candle_high_shadow_val,
                                low_shadow_val=candle_low_shadow_val,
                                high_shadow_perc=candle_high_shadow_perc,
                                low_shadow_perc=candle_low_shadow_perc,
                                body_val=candle_body_val,
                                body_perc=candle_body_perc,
                                length=price_delta,
                                color=candle_color,
                                type=None,
                            )
                            candle_type = candle_type_analysis(
                                custom_candle, candle.volume
                            )
                            custom_candle.type = candle_type
                            # if candle_type != "trash" and candle.volume > 1.5 * 10**6:
                            if candle_type != "trash":
                                message_to_send = f"""
#{ticker} {percent_price_delta}% {round(candle.volume/1000000, 1)}М ₽
<b>{chips_names[ticker]}</b>

Определён тип свечи: {candle_type}
Изменение цены: {percent_price_delta}%
Объём: {round(candle.volume/1000000, 1)}М ₽
Время: {time_now:%Y-%m-%d} {time_now.hour-1}:00
Цена: {float(quotation_to_decimal(candle.close))} ₽"""
                                await tg_bot.send_signal(
                                    message_to_send, "tinkoff", "candles"
                                )
                await asyncio.sleep(60 * 60)
            else:
                await asyncio.sleep(60)


# if __name__ == "__main__":
# asyncio.run(market_review())
