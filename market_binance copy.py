import asyncio
import sys
import json
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from pydantic.dataclasses import dataclass
#from pydantic.tools import parse_obj_as
import dataclasses
from datetime import datetime
import aiogram
from db.storage import UserStorage


last_prices = {}

def outer_message_handler(loop, queue):

    def inner_message_handler(_, message):
        dict_message = json.loads(message)
        if dict_message.get("e") == 'aggTrade':
            formatted_time = datetime.fromtimestamp(dict_message.get("T")/1000.0).strftime('%H:%M')
            local_price = float(dict_message['p'])
            local_volume = local_price*float(dict_message['q'])
            if formatted_time in last_prices.keys():
                last_prices[formatted_time]['volume'] += local_volume
                if local_price > last_prices[formatted_time]['max_price']:
                    last_prices[formatted_time]['max_price'] = local_price
                elif local_price < last_prices[formatted_time]['min_price']:
                    last_prices[formatted_time]['min_price'] = local_price
                last_prices[formatted_time]['last_price'] = local_price
            else:
                if len(last_prices.items())>1:
                    prev_data = list(last_prices.items())[-1]
                    if prev_data[1]['volume'] > 1.5 * 10:
                        now = datetime.now()
                        price_delta = round((prev_data[1]['last_price']-prev_data[1]['first_price'])/((prev_data[1]['max_price']+prev_data[1]['min_price'])/2)*100, 2)
                        message = f'''
#ETH {price_delta}% {round(prev_data[1]['volume']/1000000, 3)}М $

🔵Аномальный объём
Изменение цены: {price_delta}%
Объём: {round(prev_data[1]['volume']/1000000, 3)}М $
Время: {now:%Y-%m-%d} {prev_data[0]}
Цена: {prev_data[1]['last_price']} $
                        '''
                        loop.call_soon(queue.put_nowait, message)
                last_prices[formatted_time] = {
                    'volume':local_volume,
                    'first_price':local_price,
                    'last_price':local_price,
                    'min_price':local_price,
                    'max_price':local_price
                    }
                print(last_prices)

    return inner_message_handler

async def binance_review(loop:asyncio.AbstractEventLoop, queue:asyncio.Queue, tg_bot:aiogram.Bot, user_storage:UserStorage):
    my_client = SpotWebsocketStreamClient(on_message=outer_message_handler(loop=loop, queue=queue))
    my_client.agg_trade(symbol="ethusdt")

    for line in sys.stdin:
        if 'exit' == line.rstrip():
            my_client.stop()
            break
