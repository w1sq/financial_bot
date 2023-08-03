import time
import asyncio
from tinkoff.invest.utils import quotation_to_decimal
from tinkoff.invest import (
    AsyncClient,
    TradeInstrument,
    MarketDataRequest,
    SubscribeTradesRequest,
    SubscriptionAction,
    SubscriptionInterval,
)
import datetime
blue_chips = {
    'BBG004S68B31':'ALRS',
    'BBG004730RP0':'GAZP',
    'BBG004731489':'GMKN',
    'BBG004S68473':'IRAO',
    'BBG004731032':'LKOH',
    'BBG004RVFCY3':'MGNT',
    'BBG004S681W1':'MTSS',
    'BBG00475KKY8':'NVTK',
    'BBG000R607Y3':'PLZL',
    'BBG004731354':'ROSN',
    'BBG008F2T3T2':'RUAL',
    'BBG004730N88':'SBER',
    'BBG0047315D0':'SNGS',
    'BBG004RVFFC0':'TATN',
    'BBG006L8G4H1':'YNDX',
}
chips_names = {
    'ALRS': 'АЛРОСА',
    'GAZP': 'Газпром',
    'GMKN': 'Норильский никель',
    'IRAO': 'Интер РАО ЕЭС',
    'LKOH': 'ЛУКОЙЛ',
    'MGNT': 'Магнит',
    'MTSS': 'МТС',
    'NVTK': 'НОВАТЭК',
    'PLZL': 'Полюс',
    'ROSN': 'Роснефть',
    'RUAL': 'РУСАЛ',
    'SBER': 'Сбер Банк',
    'SNGS': 'Сургутнефтегаз',
    'TATN': 'Татнефть',
    'YNDX': 'Yandex',
}
TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw"

def get_whole_volume(trade_dict:dict) -> float:
    return trade_dict['buy'] + trade_dict['sell']

async def main():
    async def request_iterator():
        yield MarketDataRequest(
            subscribe_trades_request=SubscribeTradesRequest(
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[
                    TradeInstrument(
                        figi=figi,
                    ) for figi in blue_chips.keys()
                ],
            )
        )
        while True:
            await asyncio.sleep(1)

    async with AsyncClient(TOKEN) as client:
        data = {}
        async for marketdata in client.market_data_stream.market_data_stream(
            request_iterator()
        ):
            # print(marketdata)
            if marketdata.trade:
                if marketdata.trade.time.minute > 10:
                    local_time = f'{marketdata.trade.time.hour}:{marketdata.trade.time.minute}'
                else:
                    local_time = f'{marketdata.trade.time.hour}:0{marketdata.trade.time.minute}'
                local_price = float(quotation_to_decimal(marketdata.trade.price))
                local_volume = local_price * marketdata.trade.quantity
                local_figi = marketdata.trade.figi
                if marketdata.trade.direction == 1:
                    local_volume_direction = 'buy'
                elif marketdata.trade.direction == 2:
                    local_volume_direction = 'sell'
                else:
                    continue

                if local_time in data.keys():
                    if blue_chips[local_figi] in data[local_time].keys():
                        data[local_time][blue_chips[local_figi]][local_volume_direction] += local_volume
                        data[local_time][blue_chips[local_figi]]['price'] = local_price
                    else:
                        data[local_time][blue_chips[local_figi]] = {'buy': 0, 'sell': 0, 'price': local_price}
                        data[local_time][blue_chips[local_figi]][local_volume_direction] += local_volume
                else:
                    data[local_time] = {
                        blue_chips[local_figi]: {'buy': 0, 'sell': 0, 'price': local_price}
                    }
                    data[local_time][blue_chips[local_figi]][local_volume_direction] += local_volume
                    null_chip = {'buy': 0, 'sell': 0}
                    if len(data.keys()) > 4:
                        normal_keys = list(data.keys())
                        for chip in data[normal_keys[2]].keys():
                            to_review_volume = get_whole_volume(data[normal_keys[2]][chip])
                            if to_review_volume > 12000000 and to_review_volume > get_whole_volume(data[normal_keys[0]].get(chip, null_chip)) * 15 and to_review_volume > get_whole_volume(data[normal_keys[1]].get(chip, null_chip)) * 15 and to_review_volume > get_whole_volume(data[normal_keys[3]].get(chip, null_chip)) * 15:
                                print(data)
                                now = datetime.datetime.now()
                                buying_part = round(data[normal_keys[2]][chip]['buy']//to_review_volume, 2)
                                selling_part = 1 - buying_part
                                print(f'''
#{chip}
{chips_names[chip]}

🔵Аномальный объём
Изменение цены: ...
Объём: {round(to_review_volume//1000000, 1)} ₽
Покупка: {int(buying_part*100)}% Продажа: {int(selling_part*100)}%
Время: {now:%Y-%m-%d} {normal_keys[1]}
Цена: {data[normal_keys[2]][chip]['price']} ₽
Изменение за день: ...
                                ''')
                        data.pop(normal_keys[0])

if __name__ == "__main__":
    asyncio.run(main())
