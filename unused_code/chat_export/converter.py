import json

import pandas


with open("chat_export/new_result.json", "r", encoding="utf-8") as donor:
    all_messages = json.loads(donor.read())["messages"]
    signals = []
    count = 0
    for message in all_messages:
        if message["from_id"] == "user6455568913":
            data = message["text"]
            if (
                isinstance(data[0], dict)
                and data[0]["type"] == "hashtag"
                and len(data) == 4
            ):
                # count += 1
                if data[1].strip()[0].isdigit() or data[1].strip()[1].isdigit():
                    price_delta, volume = data[1].strip().split()[:-1]
                else:
                    price_delta, volume = data[1].strip().split()[1:-1]
                message_data = data[3].strip().split()
                # if count in (2, 895):
                #     print(message_data)
                #     print(len(message_data))
                if len(message_data) == 22:
                    signal = {
                        "ticker": data[0]["text"][1:],
                        "price": message_data[16],
                        "price_delta": message_data[4],
                        "volume(Миллионы рублей)": volume[:-1],
                        "volume_delta": "-",
                        "name": data[2]["text"],
                        "time": message_data[13] + " " + message_data[14],
                    }
                elif len(message_data) == 19:
                    signal = {
                        "ticker": data[0]["text"][1:],
                        "price": message_data[17],
                        "price_delta": message_data[5],
                        "volume(Миллионы рублей)": volume[:-1],
                        "volume_delta": "-",
                        "name": data[2]["text"],
                        "time": message_data[14] + " " + message_data[15],
                    }
                elif len(message_data) == 20 or not message_data[9][0].isdigit():
                    continue
                else:
                    signal = {
                        "ticker": data[0]["text"][1:],
                        "price": message_data[13],
                        "price_delta": message_data[6],
                        "volume(Миллионы рублей)": volume[:-1],
                        "volume_delta": message_data[9],
                        "name": data[2]["text"],
                        "time": message_data[11],
                    }
                # signal["len"] = len(message_data)
                # if count in (2, 895):
                #     print(signal)
                # print(signal)
                signals.append(signal)
            elif (
                isinstance(data[0], str) and data[0].startswith("❗️") and len(data) == 5
            ):
                # print(data)
                message_data = data[4].strip().split()
                # print(message_data)
                signal = {
                    "ticker": data[1]["text"][1:],
                    "price": message_data[-2],
                    "price_delta": message_data[2],
                    "volume(Миллионы рублей)": message_data[4][:-1],
                    "volume_delta": "-",
                    "name": data[3]["text"],
                    "time": message_data[11] + " " + message_data[12],
                }
                # print(signal)
                signals.append(signal)
    dataframe = pandas.DataFrame.from_dict(signals)
    dataframe.to_excel("result.xlsx", index=False)
