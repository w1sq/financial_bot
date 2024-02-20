import datetime

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
    OrderType,
    OrderDirection,
)
import tinkoff

TOKEN = "t.Gb6EBFHfF-eQqwR8LXYn6l7A5AM6aFh1vX9QMOmrZJ2V6OEhZdNZuW4dpThKlEH504oN2Og6HLdMXyltEBK5QQ"
ACCOUNT_ID = "2115576035"

usd_uid = "a22a1263-8e1b-4546-a1aa-416463f104d3"
usd_figi = "BBG0013HGFT4"

gazp_figi = "BBG004730RP0"
gazp_uid = "962e2a95-02a9-4171-abd7-aa198dbe643a"


async def open_order():
    with Client(TOKEN) as client:
        # print(client.users.get_margin_attributes(account_id=ACCOUNT_ID))
        orders = client.orders.get_orders(account_id=ACCOUNT_ID).orders
        print(orders)
        close_order = client.orders.post_order(
            # instrument_id=usd_uid,
            figi=gazp_figi,
            account_id=ACCOUNT_ID,
            quantity=1,
            direction=OrderDirection.ORDER_DIRECTION_SELL,
            order_type=OrderType.ORDER_TYPE_MARKET,
            order_id=str(datetime.datetime.utcnow().timestamp()),
        )
        print(close_order)


async def main():
    await open_order()

    # async def request_iterator():
    #     yield MarketDataRequest(
    #         subscribe_trades_request=SubscribeTradesRequest(
    #             subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
    #             instruments=[
    #                 TradeInstrument(
    #                     figi="BBG0013HGFT4",
    #                 )
    #             ],
    #         )
    #     )
    #     while True:
    #         await asyncio.sleep(1)

    # async with AsyncClient(TOKEN) as client:
    #     while True:
    #         data: dict[str, dict[str, dict]] = {}
    #         # chips_last_prices = await get_last_prices(client)
    #         async for marketdata in client.market_data_stream.market_data_stream(
    #             request_iterator()
    #         ):
    #             if marketdata.trade:
    #                 print(marketdata)


#                     if marketdata.trade.time.minute > 10:
#                         local_time = f"{marketdata.trade.time.hour}:{marketdata.trade.time.minute}"
#                     else:
#                         local_time = f"{marketdata.trade.time.hour}:0{marketdata.trade.time.minute}"
#                     local_figi = marketdata.trade.figi
#                     local_price = float(quotation_to_decimal(marketdata.trade.price))
#                     local_volume = (
#                         local_price
#                         * marketdata.trade.quantity
#                         * chips_lots[blue_chips[local_figi]]
#                     )
#                     if marketdata.trade.direction == 1:
#                         local_volume_direction = "buy"
#                     elif marketdata.trade.direction == 2:
#                         local_volume_direction = "sell"
#                     else:
#                         continue

#                     if local_time in data.keys():
#                         if blue_chips[local_figi] in data[local_time].keys():
#                             data[local_time][blue_chips[local_figi]][
#                                 local_volume_direction
#                             ] += local_volume
#                             data[local_time][blue_chips[local_figi]][
#                                 "close_price"
#                             ] = local_price
#                             if (
#                                 local_price
#                                 > data[local_time][blue_chips[local_figi]]["max_price"]
#                             ):
#                                 data[local_time][blue_chips[local_figi]][
#                                     "max_price"
#                                 ] = local_price
#                             if (
#                                 local_price
#                                 < data[local_time][blue_chips[local_figi]]["min_price"]
#                             ):
#                                 data[local_time][blue_chips[local_figi]][
#                                     "min_price"
#                                 ] = local_price
#                         else:
#                             data[local_time][blue_chips[local_figi]] = {
#                                 "buy": 0,
#                                 "sell": 0,
#                                 "open_price": local_price,
#                                 "close_price": local_price,
#                                 "max_price": local_price,
#                                 "min_price": local_price,
#                             }
#                             data[local_time][blue_chips[local_figi]][
#                                 local_volume_direction
#                             ] += local_volume
#                     else:
#                         data[local_time] = {
#                             blue_chips[local_figi]: {
#                                 "buy": 0,
#                                 "sell": 0,
#                                 "open_price": local_price,
#                                 "close_price": local_price,
#                                 "max_price": local_price,
#                                 "min_price": local_price,
#                             }
#                         }
#                         data[local_time][blue_chips[local_figi]][
#                             local_volume_direction
#                         ] += local_volume
#                         if len(data.keys()) > 1:
#                             # print(data)
#                             normal_keys = list(data.keys())
#                             for chip in data[normal_keys[0]].keys():
#                                 to_review_time_key = normal_keys[0]
#                                 to_review_volume = get_whole_volume(
#                                     data[to_review_time_key][chip]
#                                 )
#                                 price_delta = round(
#                                     (
#                                         data[to_review_time_key][chip]["close_price"]
#                                         - data[to_review_time_key][chip]["open_price"]
#                                     )
#                                     / (
#                                         (
#                                             data[to_review_time_key][chip]["max_price"]
#                                             + data[to_review_time_key][chip][
#                                                 "min_price"
#                                             ]
#                                         )
#                                         / 2
#                                     )
#                                     * 100,
#                                     2,
#                                 )
#                                 if price_delta < 1.50:
#                                     continue
#                                 day_data_close = data[to_review_time_key][chip][
#                                     "close_price"
#                                 ]
#                                 now = datetime.datetime.now()
#                                 buying_part = round(
#                                     data[to_review_time_key][chip]["buy"]
#                                     / to_review_volume,
#                                     2,
#                                 )
#                                 selling_part = 1 - buying_part
#                                 to_review_time_key = to_review_time_key.split(":")
#                                 to_review_time_key = (
#                                     to_review_time_key[0].strip()[:2]
#                                     + ":"
#                                     + to_review_time_key[1].strip()[:2]
#                                 )
#                                 trade_time = datetime.datetime.strptime(
#                                     to_review_time_key, "%H:%M"
#                                 ) + datetime.timedelta(hours=3)
#                                 message_to_send = f"""
# #{chip} {price_delta}% {round(to_review_volume/1000000, 1)}М ₽
# <b>{chips_names[chip]}</b>

# Изменение цены: {price_delta}%
# Объём: {round(to_review_volume/1000000, 1)}М ₽
# Покупка: {int(buying_part*100)}% Продажа: {int(selling_part*100)}%
# Время: {now:%Y-%m-%d} {trade_time:%H:%M}
# Цена: {day_data_close} ₽"""
#                                 # print(message_to_send)
#                                 await tg_bot.send_signal(
#                                     message_to_send,
#                                     "tinkoff",
#                                     "scarping",
#                                     to_review_volume,
#                                 )
#                             data.pop(normal_keys[0])


if __name__ == "__main__":
    asyncio.run(main())
