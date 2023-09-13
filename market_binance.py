import time
import sys
import json
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from pydantic.dataclasses import dataclass
#from pydantic.tools import parse_obj_as
import dataclasses
from datetime import datetime


last_prices = {}

def message_handler(_, message):
    dict_message = json.loads(message)
    if dict_message.get("e") == 'aggTrade':
        formatted_time = datetime.fromtimestamp(dict_message.get("T")/1000.0).strftime('%H:%M')
        local_volume = float(dict_message['p'])*float(dict_message['q'])
        if formatted_time in last_prices.keys():
            last_prices[formatted_time] += local_volume
        else:
            last_prices[formatted_time] = local_volume
            print(last_prices)

my_client = SpotWebsocketStreamClient(on_message=message_handler)
my_client.agg_trade(symbol="ethusdt")
for line in sys.stdin:
    if 'exit' == line.rstrip():
        my_client.stop()
