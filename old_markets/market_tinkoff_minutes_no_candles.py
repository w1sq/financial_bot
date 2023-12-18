from dataclasses import dataclass

import asyncio
import datetime
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    Client,
    AsyncClient,
    TradeInstrument,
    MarketDataRequest,
    SubscribeTradesRequest,
    SubscriptionAction,
    CandleInterval,
)
import tinkoff

from bot import TG_Bot
from db.storage import UserStorage
from candle_model import candle_type_analysis

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


async def get_last_prices(tinkoff_client: AsyncClient) -> dict:
    chips_last_prices = {}
    trade_day = False
    days_ago = 1
    while not trade_day:
        for figi, ticker in blue_chips.items():
            chip_last_price = 0.0
            async for candle in tinkoff_client.get_all_candles(
                figi=figi,
                from_=datetime.datetime.now() - datetime.timedelta(days=days_ago),
                # from_ = datetime.datetime(2023, 8, 7),
                to=datetime.datetime.now(),
                # to = datetime.datetime(2023, 8, 8),
                interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
            ):
                if candle.close:
                    trade_day = True
                    chip_last_price = float(quotation_to_decimal(candle.close))
            chips_last_prices[ticker] = chip_last_price
        if trade_day:
            break
        days_ago += 1
    return chips_last_prices


async def market_review(tg_bot: TG_Bot, user_storage: UserStorage):
    async def request_iterator():
        yield MarketDataRequest(
            subscribe_trades_request=SubscribeTradesRequest(
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[
                    TradeInstrument(
                        figi=figi,
                    )
                    for figi in blue_chips.keys()
                ],
            )
        )
        while True:
            await asyncio.sleep(1)

    async with AsyncClient(TOKEN) as client:
        while True:
            data: dict[str, dict[str, dict]] = {}
            # chips_last_prices = await get_last_prices(client)
            async for marketdata in client.market_data_stream.market_data_stream(
                request_iterator()
            ):
                if marketdata.trade:
                    if marketdata.trade.time.minute > 10:
                        local_time = f"{marketdata.trade.time.hour}:{marketdata.trade.time.minute}"
                    else:
                        local_time = f"{marketdata.trade.time.hour}:0{marketdata.trade.time.minute}"
                    local_figi = marketdata.trade.figi
                    local_price = float(quotation_to_decimal(marketdata.trade.price))
                    local_volume = (
                        local_price
                        * marketdata.trade.quantity
                        * chips_lots[blue_chips[local_figi]]
                    )
                    if marketdata.trade.direction == 1:
                        local_volume_direction = "buy"
                    elif marketdata.trade.direction == 2:
                        local_volume_direction = "sell"
                    else:
                        continue

                    if local_time in data.keys():
                        if blue_chips[local_figi] in data[local_time].keys():
                            data[local_time][blue_chips[local_figi]][
                                local_volume_direction
                            ] += local_volume
                            data[local_time][blue_chips[local_figi]][
                                "close_price"
                            ] = local_price
                            if (
                                local_price
                                > data[local_time][blue_chips[local_figi]]["max_price"]
                            ):
                                data[local_time][blue_chips[local_figi]][
                                    "max_price"
                                ] = local_price
                            if (
                                local_price
                                < data[local_time][blue_chips[local_figi]]["min_price"]
                            ):
                                data[local_time][blue_chips[local_figi]][
                                    "min_price"
                                ] = local_price
                        else:
                            data[local_time][blue_chips[local_figi]] = {
                                "buy": 0,
                                "sell": 0,
                                "open_price": local_price,
                                "close_price": local_price,
                                "max_price": local_price,
                                "min_price": local_price,
                            }
                            data[local_time][blue_chips[local_figi]][
                                local_volume_direction
                            ] += local_volume
                    else:
                        data[local_time] = {
                            blue_chips[local_figi]: {
                                "buy": 0,
                                "sell": 0,
                                "open_price": local_price,
                                "close_price": local_price,
                                "max_price": local_price,
                                "min_price": local_price,
                            }
                        }
                        data[local_time][blue_chips[local_figi]][
                            local_volume_direction
                        ] += local_volume
                        null_chip = {"buy": 0, "sell": 0}
                        if len(data.keys()) > 1:
                            # print(data)
                            normal_keys = list(data.keys())
                            for chip in data[normal_keys[0]].keys():
                                to_review_time_key = normal_keys[0]
                                to_review_volume = get_whole_volume(
                                    data[to_review_time_key][chip]
                                )
                                price_delta = round(
                                    (
                                        data[to_review_time_key][chip]["close_price"]
                                        - data[to_review_time_key][chip]["open_price"]
                                    )
                                    / (
                                        (
                                            data[to_review_time_key][chip]["max_price"]
                                            + data[to_review_time_key][chip][
                                                "min_price"
                                            ]
                                        )
                                        / 2
                                    )
                                    * 100,
                                    2,
                                )
                                info_name = ...
                                info_type = ...
                                day_data_date = ...
                                day_data_time = ...
                                day_data_open = data[to_review_time_key][chip][
                                    "open_price"
                                ]
                                day_data_high = data[to_review_time_key][chip][
                                    "max_price"
                                ]
                                day_data_low = data[to_review_time_key][chip][
                                    "min_price"
                                ]
                                day_data_close = data[to_review_time_key][chip][
                                    "close_price"
                                ]
                                day_data_vol = to_review_volume

                                candle_low_shadow_val = (
                                    min(day_data_open, day_data_close) - day_data_low
                                )
                                candle_body_val = abs(day_data_open - day_data_close)
                                candle_high_shadow_val = day_data_high - max(
                                    day_data_open, day_data_close
                                )

                                if (
                                    day_data_high == day_data_low
                                ):  # отработка нуля, пример 20220107 в файле IMOEX_2022-2023_220101_230910.txt
                                    candle_low_shadow_perc = 0
                                    candle_high_shadow_perc = 0
                                    candle_body_perc = 0
                                else:
                                    candle_high_shadow_perc = (
                                        100
                                        * candle_high_shadow_val
                                        / (day_data_high - day_data_low)
                                    )
                                    candle_low_shadow_perc = (
                                        100
                                        * candle_low_shadow_val
                                        / (day_data_high - day_data_low)
                                    )
                                    candle_body_perc = (
                                        100
                                        * candle_body_val
                                        / (day_data_high - day_data_low)
                                    )
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
                                if candle_type != "trash":
                                    now = datetime.datetime.now()
                                    buying_part = round(
                                        data[to_review_time_key][chip]["buy"]
                                        / to_review_volume,
                                        2,
                                    )
                                    selling_part = 1 - buying_part
                                    to_review_time_key = to_review_time_key.split(":")
                                    to_review_time_key = (
                                        to_review_time_key[0].strip()[:2]
                                        + ":"
                                        + to_review_time_key[1].strip()[:2]
                                    )
                                    trade_time = datetime.datetime.strptime(
                                        to_review_time_key, "%H:%M"
                                    ) + datetime.timedelta(hours=3)
                                    message_to_send = f"""
#{chip} {price_delta}% {round(to_review_volume/1000000, 1)}М ₽
<b>{chips_names[chip]}</b>

Определён тип свечи
Изменение цены: {price_delta}%
Объём: {round(to_review_volume/1000000, 1)}М ₽
Покупка: {int(buying_part*100)}% Продажа: {int(selling_part*100)}%
Время: {now:%Y-%m-%d} {trade_time:%H:%M}
Цена: {day_data_close} ₽"""
                                    await tg_bot.send_signal(message_to_send, "tinkoff")
                            data.pop(normal_keys[0])


if __name__ == "__main__":
    with Client(TOKEN) as tinkoff_client:
        for figi in blue_chips.keys():
            instruments = tinkoff_client.instruments
            for method in ["share_by"]:
                item = getattr(instruments, method)(
                    id_type=tinkoff.invest.services.InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                    id=figi,
                ).instrument
                print(item.ticker, item.lot)
    # asyncio.run(market_review())
