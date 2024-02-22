def analysis_input_data(
    input_link: str,
) -> tuple[List[TradeData], List[Candle], List[str]]:
    f = open(input_link, "r")
    situation = []
    candles = []
    candles_types = []

    for line in f:
        (
            info_name,
            info_type,
            day_data_date,
            day_data_time,
            day_data_open,
            day_data_high,
            day_data_low,
            day_data_close,
            day_data_vol,
        ) = line.split(",")
        (
            day_data_open,
            day_data_high,
            day_data_low,
            day_data_close,
            day_data_vol,
        ) = map(
            float,
            (
                day_data_open,
                day_data_high,
                day_data_low,
                day_data_close,
                day_data_vol,
            ),
        )

        candle_low_shadow_val = min(day_data_open, day_data_close) - day_data_low
        candle_body_val = abs(day_data_open - day_data_close)
        candle_high_shadow_val = day_data_high - max(day_data_open, day_data_close)

        if (
            day_data_high == day_data_low
        ):  # отработка нуля, пример 20220107 в файле IMOEX_2022-2023_220101_230910.txt
            candle_low_shadow_perc = 0
            candle_high_shadow_perc = 0
            candle_body_perc = 0
        else:
            candle_high_shadow_perc = (
                100 * candle_high_shadow_val / (day_data_high - day_data_low)
            )
            candle_low_shadow_perc = (
                100 * candle_low_shadow_val / (day_data_high - day_data_low)
            )
            candle_body_perc = 100 * candle_body_val / (day_data_high - day_data_low)
        candle_length = day_data_high - day_data_low

        if day_data_open > day_data_close:
            candle_color = "red"
        else:
            candle_color = "green"

        candle = Candle(
            high_shadow_val=candle_high_shadow_val,
            low_shadow_val=candle_low_shadow_val,
            high_shadow_perc=candle_high_shadow_perc,
            low_shadow_perc=candle_low_shadow_perc,
            body_val=candle_body_val,
            body_perc=candle_body_perc,
            length=candle_length,
            color=candle_color,
            type=None,
        )
        candle_type = candle_type_analysis(candle, day_data_vol)
        candle.type = candle_type
        day_data = TradeData(
            date=day_data_date,
            time=day_data_time,
            open=day_data_open,
            high=day_data_high,
            low=day_data_low,
            close=day_data_close,
            volume=day_data_vol,
            candle=candle,
        )

        situation.append(day_data)
        candles.append(candle)
        candles_types.append(candle.type)

    f.close()

    return situation, candles, candles_types


def get_out_data(link):
    situation, candles, candles_only_types = analysis_input_data(link)
    pure_and_cross_candles_list = pure_candles_list(situation)

    with open(f"out/pure candles {link}", "w", encoding="utf-8") as file:
        for elem in pure_and_cross_candles_list[0]:
            file.write(elem + "\n")

    with open(f"out/cross candles {link}", "w", encoding="utf-8") as file:
        for elem in pure_and_cross_candles_list[1]:
            file.write(elem + "\n")

    with open(f"out/triggers {inp_link}", "w", encoding="utf-8") as file:
        for elem in trigger_hammer_middle(situation):
            file.write(elem + "\n")

    with open(f"out/all candles {inp_link}", "w", encoding="utf-8") as file:
        for elem in candles_only_types:
            file.write(elem + "\n")

    with open(f"out/candles data {inp_link}", "w", encoding="utf-8") as file:
        for elem in candles:
            for key in elem.to_dict():
                file.write(key + ": " + str(elem.to_dict()[key]) + "; ")
            file.write("\n")


if __name__ == "__main__":
    inp_link = "IMOEX_2018-2019_180101_191231.txt"
    get_out_data(inp_link)

    inp_link = "IMOEX_2020-2021_200101_211231.txt"
    get_out_data(inp_link)

    inp_link = "IMOEX_2022-2023_220101_230910.txt"
    get_out_data(inp_link)
