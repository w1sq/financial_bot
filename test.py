data = {
    'open_price': 259.3,
    'close_price': 257.1,
    'max_price': 259.5,
    'min_price': 251.65
    }
print(round((data['close_price']-data['open_price'])/((data['max_price']+data['min_price'])/2)*100, 2))