import asyncio
import datetime
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    AsyncClient,
    TradeInstrument,
    MarketDataRequest,
    SubscribeTradesRequest,
    SubscriptionAction,
    MoneyValue,
    CandleInterval,
)
import tinkoff

from bot import TG_Bot
from trade_instrument import trade

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


TOKEN = "t.Gb6EBFHfF-eQqwR8LXYn6l7A5AM6aFh1vX9QMOmrZJ2V6OEhZdNZuW4dpThKlEH504oN2Og6HLdMXyltEBK5QQ"


def get_whole_volume(trade_dict: dict) -> float:
    return trade_dict["buy"] + trade_dict["sell"]


def money_to_float(money: MoneyValue):
    return float(money.units + money.nano / 10**9)


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


async def market_review_scarping(tg_bot: TG_Bot):
    # async def market_review():
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
            try:
                data: dict[str, dict[str, dict]] = {}
                # chips_last_prices = await get_last_prices(client)
                async for marketdata in client.market_data_stream.market_data_stream(
                    request_iterator()
                ):
                    if marketdata.trade:
                        if marketdata.trade.time.minute >= 10:
                            local_time = f"{marketdata.trade.time.hour}:{marketdata.trade.time.minute}"
                        else:
                            local_time = f"{marketdata.trade.time.hour}:0{marketdata.trade.time.minute}"
                        local_figi = marketdata.trade.figi
                        local_price = float(
                            quotation_to_decimal(marketdata.trade.price)
                        )
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
                                    > data[local_time][blue_chips[local_figi]][
                                        "max_price"
                                    ]
                                ):
                                    data[local_time][blue_chips[local_figi]][
                                        "max_price"
                                    ] = local_price
                                if (
                                    local_price
                                    < data[local_time][blue_chips[local_figi]][
                                        "min_price"
                                    ]
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
                                            data[to_review_time_key][chip][
                                                "close_price"
                                            ]
                                            - data[to_review_time_key][chip][
                                                "open_price"
                                            ]
                                        )
                                        / (
                                            (
                                                data[to_review_time_key][chip][
                                                    "max_price"
                                                ]
                                                + data[to_review_time_key][chip][
                                                    "min_price"
                                                ]
                                            )
                                            / 2
                                        )
                                        * 100,
                                        2,
                                    )
                                    if abs(price_delta) < 0.2:
                                        continue
                                    day_data_close = data[to_review_time_key][chip][
                                        "close_price"
                                    ]
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
                                    message_to_send = f"""#{chip} {price_delta}% {round(to_review_volume/1000000, 1)}М ₽\n<b>{chips_names[chip]}</b>\n\nИзменение цены: {price_delta}%\nОбъём: {round(to_review_volume/1000000, 1)}М ₽\nПокупка: {int(buying_part*100)}% Продажа: {int(selling_part*100)}%\nВремя: {now:%Y-%m-%d} {trade_time:%H:%M}\nЦена: {day_data_close} ₽"""
                                    figi = list(blue_chips.keys())[
                                        list(blue_chips.values()).index(chip)
                                    ]
                                    if price_delta > 0:
                                        order = await trade(figi, 1)
                                        if order.execution_report_status == 1:
                                            message_to_send = (
                                                "❗️ ПОКУПКА ❗️"
                                                + f"\nПокупка на {money_to_float(order.total_order_amount)} ₽\n"
                                                + message_to_send
                                            )
                                        else:
                                            message_to_send = (
                                                "❗️ ПОТЕНЦИАЛЬНАЯ ПОКУПКА ❗️"
                                                + message_to_send
                                            )
                                    else:
                                        order = await trade(figi, 2)
                                        if order.execution_report_status == 1:
                                            message_to_send = (
                                                "❗️ ПРОДАЖА ❗️"
                                                + f"\nПродажа на {money_to_float(order.total_order_amount)} ₽\n"
                                                + message_to_send
                                            )
                                        else:
                                            message_to_send = (
                                                "❗️ ПОТЕНЦИАЛЬНАЯ ПРОДАЖА ❗️"
                                                + message_to_send
                                            )
                                    print(order)
                                    # print(message_to_send)
                                    await tg_bot.send_signal(
                                        message_to_send,
                                        "tinkoff",
                                        "scarping",
                                        to_review_volume,
                                    )
                                data.pop(normal_keys[0])
            except tinkoff.invest.exceptions.AioRequestError:
                pass


# if __name__ == "__main__":
# with Client(TOKEN) as tinkoff_client:
#     for figi in blue_chips.keys():
#         instruments = tinkoff_client.instruments
#         for method in ["share_by"]:
#             item = getattr(instruments, method)(
#                 id_type=tinkoff.invest.services.InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
#                 id=figi,
#             ).instrument
#             print(item.ticker, item.lot)
# asyncio.run(market_review())
