import asyncio
import sys
import json
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from pydantic.dataclasses import dataclass
#from pydantic.tools import parse_obj_as
import dataclasses
from datetime import datetime
from bot import TG_Bot
from db.storage import UserStorage


class Binance():
    def __init__(self, tg_bot:TG_Bot, loop:asyncio.AbstractEventLoop):
        self.last_prices = {}
        self._tg_bot:TG_Bot = tg_bot
        # self._user_storage:UserStorage = None
        self._loop = loop
    
    def message_handler(self, _, message):
        dict_message = json.loads(message)
        if dict_message.get("e") == 'aggTrade':
            formatted_time = datetime.fromtimestamp(dict_message.get("T")/1000.0).strftime('%H:%M')
            local_price = float(dict_message['p'])
            local_volume = local_price*float(dict_message['q'])
            if formatted_time in self.last_prices.keys():
                self.last_prices[formatted_time]['volume'] += local_volume
                if local_price > self.last_prices[formatted_time]['max_price']:
                    self.last_prices[formatted_time]['max_price'] = local_price
                elif local_price < self.last_prices[formatted_time]['min_price']:
                    self.last_prices[formatted_time]['min_price'] = local_price
                self.last_prices[formatted_time]['last_price'] = local_price
            else:
                if len(self.last_prices.items())>1:
                    prev_data = list(self.last_prices.items())[-1]
                    if prev_data[1]['volume'] > 1.5 * 10:
                        now = datetime.now()
                        price_delta = round((prev_data[1]['last_price']-prev_data[1]['first_price'])/((prev_data[1]['max_price']+prev_data[1]['min_price'])/2)*100, 2)
                        message_to_send = f'''
#ETH {price_delta}% {round(prev_data[1]['volume']/1000000, 3)}М $

🔵Аномальный объём
Изменение цены: {price_delta}%
Объём: {round(prev_data[1]['volume']/1000000, 3)}М $
Время: {now:%Y-%m-%d} {prev_data[0]}
Цена: {prev_data[1]['last_price']} $'''
                        print(message_to_send)
                        self._loop.create_task(self._tg_bot.send_signal(message_to_send, 'binance'))
                self.last_prices[formatted_time] = {
                    'volume':local_volume,
                    'first_price':local_price,
                    'last_price':local_price,
                    'min_price':local_price,
                    'max_price':local_price
                    }
                # print(self.last_prices)

    async def binance_review(self):
        my_client = SpotWebsocketStreamClient(on_message=self.message_handler)
        my_client.agg_trade(symbol="ethusdt")

        # for line in sys.stdin:
        #     if 'exit' == line.rstrip():
        #         my_client.stop()
        #         break

# if __name__ == '__main__':
#     binance = Binance()
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(binance.binance_review())
