import ast
import asyncio
import logging
import re
import sys
from datetime import datetime, timedelta
import json

import requests
from bs4 import BeautifulSoup
import openai


async def from_arr_to_set(arr):
    new_arr = []
    for el in arr:
        new_arr.extend([el[:3], el[3:]])
    return list(set(new_arr))

async def from_arr_to_dict(arr):
    new_dict = {}
    for currency_pair in arr:
        new_dict.update({
            f"{currency_pair}": {
                    "url": f"https://ru.investing.com/currencies/{currency_pair[:3:].lower()}-{currency_pair[3::].lower()}",
            }
        })
    return new_dict

async def get_currency_price_for_currencies(current_currency_dict):
    for pair_key, pair_value in current_currency_dict.items():
        # Викликаємо функцію, щоб розпарсити потрібні нам дані з сайту для поточної валюти.
        # У функцію передаємо поле 'current_price_url'(посилання для парсингу) з поточного 'currency_val'(слвовник поточної валюти)
        current_price, open_price = await parce_currency_price_for_currencies(pair_value["url"])
        # У словник поточної валюти 'currency_val' додаємо інформацію про поточний курс та курс на момент відкриття торгів.
        pair_value.update({
            'current_price': current_price,
            'open_day_price': open_price
        })
    return current_currency_dict



async def parce_currency_price_for_currencies(url):
    response = requests.get(url)
    if response.status_code == 200:
        page_content = response.text

        soup = BeautifulSoup(page_content, 'html.parser')

        open_current_price_div = soup.find("dd", {"data-test": "open"})
        open_current_price_value = open_current_price_div.text.strip()

        current_current_price_div = soup.find("span", {"data-test": "instrument-price-last"})
        current_current_price_value = current_current_price_div.text.strip()

        return current_current_price_value.replace(",","."), open_current_price_value.replace(",", ".")



async def get_last_info_for_selected_currencies(currencies, parser_dict, message):
    temporary_dict = {}
    for currency in currencies:
        period = datetime.now().date()
        # Запускаємо нескінченний цикл, який буде перевіряти наявність подій з поточною валютою у 'period'. У разі відсутності
        # подій 'period' змінюється на -1 день. Нескінченний цикл дозволяє робити цю перевірку стільки - скільки це буде потрібно.
        while True:
            payload = {
                'country[]': [25, 4, 17, 39, 72, 26, 10, 6, 37, 43, 56, 36, 5, 61, 22, 12, 35],
                'dateFrom': str(period),
                'dateTo': str(period),
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
                json_data = response.json()
                html_string = json_data['data']
                soup = BeautifulSoup(html_string, 'html.parser')
                all_events = soup.find_all(parser_dict['elements_class'][0], parser_dict['elements_class'][1])
                # Записуємо в масив всі події, в яких:
                # 1. Дата публікації події відповідає 'period'
                # 2. Актуальна та попередня ціни вже відомі
                # 3. Валюта події дорівнює поточній валюті
                last_day_events = [event for event in all_events if
                       datetime.strptime(event[parser_dict['datatime']],'%Y/%m/%d %H:%M:%S').date() <= period and event.find(
                       parser_dict['actual_class'][0],class_=parser_dict['actual_class'][1]).text.strip() and event.find(
                       parser_dict['prev_class'][0],class_=parser_dict['prev_class'][1]).text.strip() and event.find(
                       parser_dict['event_currency_class'][0], class_=parser_dict['event_currency_class'][1]).text.strip() == currency]
                if not last_day_events: # Якщо масив порожній, зменшуємо 'period' на -1 день і ще раз виконуємо цикл 'True'.
                    period -= timedelta(days=1)
                else:
                    break
            else:
                await message.answer(f"Request failed with status code {response.status_code}")
                await message.answer(response.text)
        # Викликаємо функцію, яка розпарсить всю потрібну інформацію, яку ми отримали і записали у 'last_day_events'
        # Передаємо аргументи: Всі події за останній день, пов'язані з поточною валютою 'last_day_events',
        # словник для парсингу 'parser_dict', назву поточної валюти
        last_event = await parser_for_last_currency_info(last_day_events, parser_dict, currency, message)

        temporary_dict.update({
            f"{currency}": last_event
        })
    return temporary_dict


async def parser_for_last_currency_info(last_day_events, parser_dict, currency, message):
    id_checker = [] # Створюємо масив для зберігання айді всіх події, пов'язаних з обраною валютою.
    # Запускаємо цикл для кожної події і парсимо портібну інформацію.
    for event in last_day_events:
        event_id = event.get('id') # Айді події
        event_name = event.find(parser_dict['event_class'][0],
                                class_=parser_dict['event_class'][1]).text.strip() # Опис події
        event_full_time = datetime.strptime(event[parser_dict['datatime']],
                                            '%Y/%m/%d %H:%M:%S') # Повний час публікації події
        time = event.find(parser_dict['time_class'][0],
                          class_=parser_dict['time_class'][1]).text.strip() # Година, проведення події

        event_currency = event.find(parser_dict['event_currency_class'][0],
                                    class_=parser_dict['event_currency_class'][1]).text.strip() # Валюта події
        actual = event.find(parser_dict['actual_class'][0],
                            class_=parser_dict['actual_class'][1]).text.strip() # Актуальний курс події
        actual = "N/A" if not actual else actual

        forecast = event.find(parser_dict['forecast_class'][0],
                           class_=parser_dict['forecast_class'][1]).text.strip() # Прогноз курсу події
        forecast = "N/A" if not forecast else forecast

        previous = event.find(parser_dict['prev_class'][0],
                              class_=parser_dict['prev_class'][1]).text.strip() # попередній курс події
        previous = "N/A" if not previous else previous

        if actual == "N/A":
            continue



        id_checker.append(event_id) # Додаємо до списку айді кожної події, яка містить інформацію про 'actual'

        last_event = {
            "id": event_id,
            "event_name": event_name,
            "event_full_time": event_full_time,
            "currency": event_currency,
            "time": time,
            "actual": actual,
            "forecast": forecast,
            "previous": previous,
        }

    last_event.update({"id_checker": id_checker})

    return last_event


async def start_chat_gpt(last_info):
    try:
        openai.api_key = "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"

        currency1 = last_info['0']
        currency2 = last_info['1']
        message = (
            f"I have 2 events related to specific {currency1['currency']} and {currency2['currency']}.\n"
            f"I need you to estimate the effect of this event on the rate of {currency1['currency']}/{currency2['currency']} necessarily in percent. Your answer should be"
            "in JSON format. For example: {{'prediction': '+0.78%'}}. If you can't determine the direction of currency movement, just reply with {{'prediction': '+0%'}}."
            f"Information for the event associated with {currency1['currency']}:\n"
            f"Event details: {currency1['event_name']}\n"
            f"Actual indicator/index/rate = {str(currency1['actual'])}\n"
            f"Previous Indicator/Index/Currency = {str(currency1['previous'])}\n"
            f"Forecast rate/index/exchange rate = {str(currency1['forecast'])}\n"
            f"Information for the event related to {currency2['currency']}:\n"
            f"Event details: {currency2['event_name']}\n"
            f"Actual indicator/index/rate = {str(currency2['actual'])}\n"
            f"Previous Indicator/Index/Currency = {str(currency2['previous'])}\n"
            f"Forecast indicator/index/exchange rate = {str(currency2['forecast'])}\n"
            "Even if the change is minimal, provide your prediction, e.g., {'prediction': '-0.01%'}"
        )

        messages = ([
            {'role': 'system', 'content': 'You are an expert in the currency exchange'},
            {'role': 'user', 'content': message}
        ])

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
        )

        response_text = ast.literal_eval(response.choices[0].message.content)
        response_text = response_text.get('prediction')
        if response_text:
            return response_text
        else:
            return "0%"

    except Exception as err:
        return err

async def show_day_prediction(currencies_dict, last_currencies_event_dict, message):
    for key, val in currencies_dict.items():
        last_event = {}
        counter = 0
        for event_key, event_val in last_currencies_event_dict.items():

            if event_key in key:
                last_event.update({
                    "0": last_currencies_event_dict[f'{key[:3:]}'],
                    "1": last_currencies_event_dict[f'{key[3::]}'],
                })
                counter += 1

        currency_current_price, currency_open_price = await parce_currency_price_for_currencies(str(val['url']))

        price_prediction = await start_chat_gpt(last_event)
        price_prediction_counter = 0

        while True:
            if str(price_prediction) == "You exceeded your current quota, please check your plan and billing details.":
                await message.answer("We've run out of requests for the key ")
                sys.exit()
            elif "Rate limit" in str(price_prediction) or price_prediction is None:
                await asyncio.sleep(60)
                price_prediction = await start_chat_gpt(last_event)
            elif isinstance(price_prediction, str):
                break
            elif price_prediction_counter >= 3:
                price_prediction = "0%"
            price_prediction_counter += 1



        bot_prediction = await chat_gpt_get_whole_info(last_event, price_prediction)
        bot_prediction_counter = 0

        while True:
            if str(bot_prediction) == "You exceeded your current quota, please check your plan and billing details.":
                await message.answer("We've run out of requests for the key ")
                sys.exit()
            elif "Rate limit" in str(bot_prediction) or bot_prediction is None:
                await asyncio.sleep(60)
                bot_prediction = await chat_gpt_get_whole_info(last_event, price_prediction)
            elif isinstance(bot_prediction, str):
                break
            elif bot_prediction_counter >= 3:
                bot_prediction = "Bullish 50%"
                break
            bot_prediction_counter += 1


        percent = bot_prediction.split(" ")[1]
        if 'Bullish' in bot_prediction:
            val.update({
                "prediction": ["Bullish", f"▪️ <b>{key}</b> - {percent}\n"],
            })
        elif 'Bearish' in bot_prediction:
            val.update({
                "prediction": ["Bearish", f"▪️ <b>{key}</b> - {percent}\n"],
            })
        val.update({
            "price_prediction": [currency_current_price, currency_open_price, price_prediction],
            "new": 0,
        })


    return currencies_dict




async def chat_gpt_get_whole_info(last_events_dict, price_prediction, new_dict=None):
    try:
        openai.api_key = "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"
        if new_dict is None:
            event_info_1 = last_events_dict['0']
            event_info_2 = last_events_dict['1']
        else:
            event_info_1 = new_dict[0]
            event_info_2 = new_dict[1]
        message = (
    f"Analyze recent events for {event_info_1['currency']}/{event_info_2['currency']}.\n"
    f"Prediction of price change for {event_info_1['currency']}/{event_info_2['currency']} from an expert: {price_prediction}\n"
    f"{event_info_1['currency']} data:\n"
    f"{event_info_1['currency']} event info: {event_info_1['event_name']}\n"
    f"Fact: {event_info_1['actual']}\n"
    f"Forecast: {event_info_1['forecast']}\n"
    f"Previous: {event_info_1['previous']}\n"
    f"{event_info_2['currency']} data:\n"
    f"{event_info_2['currency']} event information: {event_info_2['event_name']}\n"
    f"Fact: {event_info_2['actual']}\n"
    f"Forecast: {event_info_2['forecast']}\n"
    f"You need to predict today's close for {event_info_1['currency']}/{event_info_2['currency']} currency pair "
    f"and choose the higher probability between bullish and bearish.\n"
    "Your prediction must be in JSON format.\n"
    "'sentiment' must be 'Bullish' or 'Bearish'.\n"
    "'percentage' should be in the range of 50-70.\n"
    "Your forecast should be very accurate and you should take"
    " into account that if the indicators of these events do "
    "not have a big growth, the forecast is unlikely to be more than 60%."
    " You should also take into account the significance of each event..\n"
    "Examples: {'prediction': 'Bullish 51.82%'}"
)
        messages = ([
            {'role': 'system', 'content': 'You are an expert in the currency exchange'},
            {'role': 'user', 'content': message}
        ])

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
        )

        response_text = ast.literal_eval(response.choices[0].message.content)
        response_text = response_text.get('prediction')
        if response_text:
            return response_text
        else:
            return "Bullish 50%"
    except Exception as err:
        return err


