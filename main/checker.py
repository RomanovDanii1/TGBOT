import asyncio
import logging
import re
import sys
from datetime import datetime, timedelta

import openai
import requests
from bs4 import BeautifulSoup


from investor_parser import get_currency_price_for_currencies, get_last_info_for_selected_currencies, \
    parce_currency_price_for_currencies, start_chat_gpt, parser_for_last_currency_info, chat_gpt_get_whole_info


async def new_event_checker(current_currency_dict, parser_dict, message, currencies_dict):
    today = datetime.now().date()
    yesterday = today
    payload = {
        'country[]': [25, 4, 17, 39, 72, 26, 10, 6, 37, 43, 56, 36, 5, 61, 22, 12, 35],
        'dateFrom': str(yesterday),
        'dateTo': str(today),
        'timeZone': 18,
        'timeFilter': 'timeRemain',
        'currentTab': 'custom',
        'limit_from': 0,
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://ru.investing.com/economic-calendar/',
        'Accept': 'text/html, */*; q=0.01',
    }
    response = requests.post(parser_dict['url'], data=payload, headers=headers)
    if response.status_code == 200:
        temp_arr = []
        json_data = response.json()
        html_string = json_data['data']
        soup = BeautifulSoup(html_string, 'html.parser')
        all_events = soup.find_all(parser_dict['elements_class'][0], parser_dict['elements_class'][1])
        for currency_key, currency_value in current_currency_dict.items():
            last_events = [event for event in all_events if event.find(parser_dict['event_currency_class'][0],
            class_=parser_dict['event_currency_class'][1]).text.strip() == currency_value['currency'] and
            currency_value['event_full_time'] <= datetime.strptime(event[parser_dict['datatime']], '%Y/%m/%d %H:%M:%S')
            and event.find(parser_dict['actual_class'][0], class_=parser_dict['actual_class'][1]).text.strip()
            and event.find(parser_dict['prev_class'][0], class_=parser_dict['prev_class'][1]).text.strip()
            and event.get('id') not in currency_value['id_checker']]

            if last_events:
                for event in last_events:
                    event_id = event.get('id')
                    event_name = event.find(parser_dict['event_class'][0],
                                         class_=parser_dict['event_class'][1]).text.strip()
                    event_full_time = datetime.strptime(event[parser_dict['datatime']], '%Y/%m/%d %H:%M:%S')
                    time = event.find(parser_dict['time_class'][0], class_=parser_dict['time_class'][1]).text.strip()

                    event_currency = event.find(parser_dict['event_currency_class'][0],
                                             class_=parser_dict['event_currency_class'][1]).text.strip()
                    actual = event.find(parser_dict['actual_class'][0],
                                     class_=parser_dict['actual_class'][1]).text.strip()
                    actual = "N/A" if not actual else actual

                    forecast = event.find(parser_dict['forecast_class'][0],
                                       class_=parser_dict['forecast_class'][1]).text.strip()
                    forecast = "N/A" if not forecast else forecast

                    previous = event.find(parser_dict['prev_class'][0],
                                       class_=parser_dict['prev_class'][1]).text.strip()
                    previous = "N/A" if not previous else previous

                    currency_value['id_checker'].append(event_id)

                currency_value.update({
                    "id": event_id,
                    "event_name": event_name,
                    "event_full_time": event_full_time,
                    "currency": event_currency,
                    "time": time,
                    "actual": actual,
                    "forecast": forecast,
                    "previous": previous,
                    "heading": "heading",
                })


                for currency_name_key, currency_name_value in currencies_dict.items():
                    if event_currency in currency_name_key:
                        # currency_current_price, currency_open_price = await parce_currency_price_for_currencies(str(currency_name_value['url']))
                        # currency_name_value.update({'current_price': currency_current_price})
                        temp_arr.append(currency_name_key)

                await message.answer(f"Увага! Нова подія для {event_currency}\n"
                                     f"Опис події: {str(event_name)}\n"
                                     f"Час: {str(time)}\n"
                                     f"Актуальний показник: {str(actual)}\n"
                                     f"Прогноз показника: {str(forecast)}\n"
                                     f"Попередній показника: {str(previous)}\n")
                                     # f"Поточний курс валюти {str(currency_current_price)}\n"
                                     # f"Прогноз від боту: {heading} або {percent}%")
        return current_currency_dict, set(temp_arr)


async def new_event_prediction(last_currencies_event_dict, day_prediction, temp_arr, message):
    for key, val in day_prediction.items():
        new = False
        for currency in temp_arr:
            if currency in key:
                new = True
        if new:
            last_event = {
                "0": last_currencies_event_dict[f"{key[3::]}"],
                "1": last_currencies_event_dict[f"{key[:3:]}"],
            }

            counter = 0
            price_prediction = await start_chat_gpt(last_event)

            while True:
                if str(price_prediction) == "You exceeded your current quota, please check your plan and billing details.":
                    await message.answer("We've run out of requests for the key ")
                    sys.exit()
                elif "Rate limit" in str(price_prediction) or price_prediction is None:
                    await asyncio.sleep(60)
                    price_prediction = await start_chat_gpt(last_event)
                elif isinstance(price_prediction, str):
                    break
                elif counter >= 3:
                    price_prediction = "0%"
                    break
                counter += 1

            counter = 0
            bot_prediction = await chat_gpt_get_whole_info(last_currencies_event_dict, price_prediction ,[last_currencies_event_dict[f"{key[:3:]}"], last_currencies_event_dict[f"{key[3::]}"]])
            while True:
                if str(bot_prediction) == "You exceeded your current quota, please check your plan and billing details.":
                    await message.answer("We've run out of requests for the key ")
                    sys.exit()
                elif "Rate limit" in str(bot_prediction) or bot_prediction is None:
                    await asyncio.sleep(20)
                    bot_prediction = await chat_gpt_get_whole_info(last_currencies_event_dict, price_prediction,[last_currencies_event_dict[f"{key[:3:]}"], last_currencies_event_dict[f"{key[3::]}"]])
                elif isinstance(bot_prediction, str):
                    break
                elif counter >= 3:
                    bot_prediction = "Bullish 50%"
                    break
                counter += 1




            currency_current_price, currency_open_price = await parce_currency_price_for_currencies(val['url'])

            percent = bot_prediction.split(" ")[1]

            if 'Bullish' in bot_prediction:
                val.update({
                    "prediction": ["Bullish", f"▪️ <b>{key}</b> - {percent}\n"]
                })
            elif 'Bearish' in bot_prediction:
                val.update({
                    "prediction": ["Bearish", f"▪️ <b>{key}</b> - {percent}\n"]
                })
            day_prediction[key].update({
                "price_prediction": [currency_current_price, currency_open_price, price_prediction],
                "new": 1,
            })
    return day_prediction

async def show_predicted_info(day_prediction_dict, message, show_prediction=None):
    bullish = ""
    bearish = ""
    more_60_p = ""

    for key, val in day_prediction_dict.items():
        if val['new'] == 1:
            mark = "❗️"
        else:
            mark = ""

        if show_prediction is None:
            price_info = f"current price: {val['price_prediction'][0]}, prediction: {val['price_prediction'][2]}\n"
        else:
            price_info = ""

        match = re.search(r'\d+\.\d+', val["prediction"][1])
        if match:
            number = float(match.group())
        else:
            number = float(0)

        if "Bullish" in val["prediction"]:
            bullish += (f"{mark}{val['prediction'][1]}"
                        f"{price_info}")
        elif "Bearish" in val["prediction"]:
            bearish += (f"{mark}{val['prediction'][1]}"
                        f"{price_info}")
        if number >= 60:
            more_60_p += (f"{mark}{val['prediction'][1]}"
                        f"{price_info}")
    result = (f"📈Ймовірність бичачого дня за валютною парою:\n"
                         f"{bullish}\n\n"
                         f"📉Ймовірність ведвежого дня за валютною парою:\n"
                         f"{bearish}\n\n")
    if more_60_p:
        result += (f"📊Сьогодні торгуємо саме такими парами:\n"
                   f"{more_60_p}\n\n")
    else:
        result += "Сьогодні не торгуємо."
    await message.answer(result)


async def show_day_info(day_prediction_dict, currencies_dict, message):
    result = ""
    for key, val in day_prediction_dict.items():
        currency_current_price, currency_open_price = await parce_currency_price_for_currencies(currencies_dict[key]['url'])
        match = re.search(r'-?\d+(\.\d+)?', val["price_prediction"][2].replace(",", "."))
        number = float(match.group())
        bot_prediction = float(val['price_prediction'][0]) + (float(val['price_prediction'][0]) / 100 * float(number))
        difference = (float(currency_current_price) - float(bot_prediction)) / abs(float(currency_current_price)) * 100
        result += (f"{key}\n"
                   f"Бот вважав, що закриття дня буде: {val['prediction'][0]}\n"
                   f"Результат закриття дня: {float(val['price_prediction'][1]) - float(currency_open_price)}\n"
                   f"Поточний курс: {currency_current_price}\n"
                   f"Передбачення бота стосовно ціни: {round(float(bot_prediction), 3)}\n"
                   f"Різниця між передбаченням і поточною ціною у відсотках: {abs(round(difference, 3))}%\n\n\n")
    await message.answer(str(result))



