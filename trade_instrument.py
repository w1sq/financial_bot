import datetime

from tinkoff.invest import (
    AsyncClient,
    OrderType,
    OrderDirection,
)

TOKEN = "t.Gb6EBFHfF-eQqwR8LXYn6l7A5AM6aFh1vX9QMOmrZJ2V6OEhZdNZuW4dpThKlEH504oN2Og6HLdMXyltEBK5QQ"
ACCOUNT_ID = "2115576035"

# usd_uid = "a22a1263-8e1b-4546-a1aa-416463f104d3"
# usd_figi = "BBG0013HGFT4"

# gazp_figi = "BBG004730RP0"
# gazp_uid = "962e2a95-02a9-4171-abd7-aa198dbe643a"


async def trade(instrument_figi: str, trade_direction: int):
    # trade_direction : buy - 1, sell - 2
    async with AsyncClient(TOKEN) as client:
        order = await client.orders.post_order(
            figi=instrument_figi,
            account_id=ACCOUNT_ID,
            quantity=1,
            direction=trade_direction,
            order_type=OrderType.ORDER_TYPE_MARKET,
            order_id=str(datetime.datetime.utcnow().timestamp()),
        )
        return order
