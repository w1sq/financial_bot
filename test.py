data = {
    'open_price': 13.055,
    'close_price': 16.39,
    'max_price': 17.445,
    'min_price': 13.195
    }
print(round((data['close_price']-data['open_price'])/((data['max_price']+data['min_price'])/2)*100, 2))