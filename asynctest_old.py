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
)
import tinkoff
import aiogram
from db.storage import UserStorage

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

chips_lots = {
    'ALRS': 10,
    'GAZP': 10,
    'GMKN': 1,
    'IRAO': 100,
    'LKOH': 1,
    'MGNT': 1,
    'MTSS': 10,
    'NVTK': 1,
    'PLZL': 1,
    'ROSN': 1,
    'RUAL': 10,
    'SBER': 10,
    'SNGS': 100,
    'TATN': 1,
    'YNDX': 1,
}

TOKEN = "t.nb6zNANS5GyESI_e_9ledD8iWDqVpgEK9ewrQu6Orr6F9N-NNdklR5r9VkwFs8RXiPzkXgxeUtcGSf_LxFgXAw"

def get_whole_volume(trade_dict:dict) -> float:
    return trade_dict['buy'] + trade_dict['sell']

async def market_review(tg_bot:aiogram.Bot, user_storage:UserStorage):
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
            # for user in await user_storage.get_all_members():

            #     await tg_bot._bot.send_message(user.user_id, 'test')
            if marketdata.trade:
                if marketdata.trade.time.minute > 10:
                    local_time = f'{marketdata.trade.time.hour}:{marketdata.trade.time.minute}'
                else:
                    local_time = f'{marketdata.trade.time.hour}:0{marketdata.trade.time.minute}'
                local_figi = marketdata.trade.figi
                local_price = float(quotation_to_decimal(marketdata.trade.price))
                local_volume = local_price * marketdata.trade.quantity * chips_lots[blue_chips[local_figi]]
                if marketdata.trade.direction == 1:
                    local_volume_direction = 'buy'
                elif marketdata.trade.direction == 2:
                    local_volume_direction = 'sell'
                else:
                    continue

                if local_time in data.keys():
                    if blue_chips[local_figi] in data[local_time].keys():
                        data[local_time][blue_chips[local_figi]][local_volume_direction] += local_volume
                        data[local_time][blue_chips[local_figi]]['close_price'] = local_price
                        if local_price > data[local_time][blue_chips[local_figi]]['max_price']:
                            data[local_time][blue_chips[local_figi]]['max_price'] = local_price
                        if local_price < data[local_time][blue_chips[local_figi]]['min_price']:
                            data[local_time][blue_chips[local_figi]]['min_price'] = local_price
                    else:
                        data[local_time][blue_chips[local_figi]] = {'buy': 0, 'sell': 0, 'open_price': local_price, 'close_price': local_price, 'max_price': local_price, 'min_price': local_price}
                        data[local_time][blue_chips[local_figi]][local_volume_direction] += local_volume
                else:
                    data[local_time] = {
                        blue_chips[local_figi]: {'buy': 0, 'sell': 0, 'open_price': local_price, 'close_price': local_price, 'max_price': local_price, 'min_price': local_price}
                    }
                    data[local_time][blue_chips[local_figi]][local_volume_direction] += local_volume
                    null_chip = {'buy': 0, 'sell': 0}
                    if len(data.keys()) > 3:
                        print(data)
                        normal_keys = list(data.keys())
                        for chip in data[normal_keys[2]].keys():
                            to_review_volume = get_whole_volume(data[normal_keys[2]][chip])
                            koef = 12
                            big_chips = ['SBER', 'GAZP', 'LKOH']
                            if to_review_volume > 50000000 and chip not in big_chips or to_review_volume > 12000000 and to_review_volume > get_whole_volume(data[normal_keys[0]].get(chip, null_chip)) * koef and to_review_volume > get_whole_volume(data[normal_keys[1]].get(chip, null_chip)) * koef:
                                now = datetime.datetime.now()
                                buying_part = round(data[normal_keys[2]][chip]['buy']/to_review_volume, 2)
                                selling_part = 1 - buying_part
                                trade_time = datetime.datetime.strptime(normal_keys[2], "%H:%M") + datetime.timedelta(hours=3)
                                price_delta = round((data[normal_keys[2]][chip]['close_price']-data[normal_keys[2]][chip]['open_price'])/((data[normal_keys[2]][chip]['max_price']+data[normal_keys[2]][chip]['min_price'])/2)*100, 2)
                                # db_users = await user_storage.get_all_members()
                                for user in await user_storage.get_all_members():
                                    try:
                                        await tg_bot._bot.send_message(user.user_id, f'''
#{chip} {price_delta}% {round(to_review_volume/1000000, 1)}М ₽
{chips_names[chip]}

🔵Аномальный объём
Изменение цены: {price_delta}%
Объём: {round(to_review_volume/1000000, 1)}М ₽
Покупка: {int(buying_part*100)}% Продажа: {int(selling_part*100)}%
Время: {now:%Y-%m-%d} {trade_time:%H:%M}
Цена: {data[normal_keys[2]][chip]['close_price']} ₽
Изменение за день: ...
                                        ''')
                                    except Exception:
                                        pass
                        data.pop(normal_keys[0])

if __name__ == "__main__":
    with Client(TOKEN) as tinkoff_client:
        for figi in blue_chips.keys():
            instruments = tinkoff_client.instruments
            for method in ["share_by"]:
                item = getattr(instruments, method)(id_type=tinkoff.invest.services.InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id =figi).instrument
                print(item.ticker, item.lot)
    # asyncio.run(market_review())
