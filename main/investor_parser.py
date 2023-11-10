import asyncio
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import openai
import re


async def get_currency_current_price(url, parse_info):
    response = requests.get(url)
    if response.status_code == 200:
        page_content = response.text

        soup = BeautifulSoup(page_content, 'html.parser')

        current_current_price_div = soup.find(parse_info[0], parse_info[1])

        current_current_price_value = current_current_price_div.text.strip()

        return current_current_price_value
    else:
        return 0

async def day_currency_price(currency_price_dict):
    response = requests.get(currency_price_dict['url'])
    if response.status_code == 200:
        page_content = response.text

        soup = BeautifulSoup(page_content, 'html.parser')

        open_current_price_div = soup.find(currency_price_dict['open_current_price'][0],
                                           currency_price_dict['open_current_price'][1])
        open_current_price_value = open_current_price_div.text.strip()

        current_current_price_div = soup.find(currency_price_dict['current_currency_price'][0],
                                              currency_price_dict['current_currency_price'][1])
        current_current_price_value = current_current_price_div.text.strip()

        return current_current_price_value, open_current_price_value


async def start_chat_gpt(last_info):
    try:
        openai.api_key = "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"

        prompt = (
            f"What is the expected impact if an event happened today, and we know that {str(last_info['event_name'])} has the following data:\n"
            f"Current exchange rate/index/event indicator: {str(last_info['actual'])}\n"
            f"Forecast for the current exchange rate/index/event indicator: {str(last_info['forecast'])}\n"
            f"Previous exchange rate/index/event indicator: {str(last_info['previous'])}\n"
            f"In your opinion, by what percentage can the price of {last_info['currency']} on the foreign exchange market increase or decrease, taking into account the event's impact?\n"
            f"Even if you predict a very small percentage change, please state it clearly, for example, (+0.03%) or (-0.03%) or (The price will remain stable)."
            f"Take into account that it is incredibly rare for the price of a currency on the exchange to rise or fall by more than 5 percent"
        )
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150,
            temperature=0.7,
        )

        answer = response.choices[0].text
        if 'The price will remain stable' in answer:
            answer = 0
        return answer

    except Exception as err:
        logging.error(err)


async def OpenAI_forecast(last_event_currencies, message=None):
    for index in range(len(last_event_currencies)):
        new_answer = await start_chat_gpt(last_event_currencies[index])
        if message:
            while True:
                if new_answer is None:
                    await message.answer("Вибачте...\n"
                                         "Боту потрібно відпочити 1 хвилинку")
                    await asyncio.sleep(60)
                    new_answer = await start_chat_gpt(last_event_currencies[index])
                else:
                    break
        last_event_currencies[index].update({'bot_prediction': str(new_answer)})
    return last_event_currencies


async def show_last_info(last_event_currencies, message, currency_close_price_parser=None, currency1=None,
                         currency2=None, urls=None, open_day_currencies=None, bot_prediction_currency1=None, bot_prediction_currency2=None):
    last_event_currencies = await OpenAI_forecast(last_event_currencies, message)
    if currency_close_price_parser:
        close_currencies = []
        for url in urls:
            response = requests.get(url)
            if response.status_code == 200:
                page_content = response.text

                soup = BeautifulSoup(page_content, 'html.parser')

                open_current_price_div = soup.find(currency_close_price_parser[0],
                                                   currency_close_price_parser[1])

                close_currencies.append(open_current_price_div.text.strip())

        close_currency1 = close_currencies[0].replace(",", ".")
        close_currency2 = close_currencies[1].replace(",", ".")
        open_day_currency1 = open_day_currencies[0].replace(",", ".")
        open_day_currency2 = open_day_currencies[1].replace(",", ".")
        currency1_day_result = (float(open_day_currency1) - float(close_currency1)) / float(open_day_currency1) * 100
        if float(close_currency1) < float(open_day_currency1):
            currency1_day_result *= -1
        currency2_day_result = (float(open_day_currency2) - float(close_currency2)) / float(open_day_currency2) * 100
        if float(close_currency2) < float(open_day_currency2):
            currency2_day_result *= -1
        different2_percent = ((float(bot_prediction_currency2) - float(close_currency2)) / float(close_currency2)) * 100
        different1_percent = ((float(bot_prediction_currency1) - float(close_currency1)) / float(close_currency1)) * 100

        await message.answer(f"Результати закриттяn\n\n"
                             f"Валютна пара {currency1}/{currency2}\n"
                             f"Поточний курс: {close_currency1}\n"
                             f"Прогноз від бота: {bot_prediction_currency1}\n"
                             f"Різниця між прогнозом і поточним курсом: {round(different1_percent, 5)}%\n"
                             f"Вчора ціна змінилась на {round(currency1_day_result, 5)}%\n\n\n"
                             f"Валютна пара {currency2}/{currency1}\n"
                             f"Поточний курс: {close_currency2}\n"
                             f"Прогноз від бота: {bot_prediction_currency2}\n"
                             f"Різниця між прогнозом і поточним курсом: {round(different2_percent, 5)}%\n"
                             f"Вчора ціна змінилась на {round(currency2_day_result, 5)}%\n"
                             )

    current_currency_parser = ["span", {"data-test": "instrument-price-last"}]
    currency_heading = []
    for index in range(len(last_event_currencies)):
        if index == 0:
            url = f"https://ru.investing.com/currencies/{last_event_currencies[0]['currency'].lower()}-{last_event_currencies[1]['currency'].lower()}"
        else:
            url = f"https://ru.investing.com/currencies/{last_event_currencies[1]['currency'].lower()}-{last_event_currencies[0]['currency'].lower()}"

        current_currency_price = await get_currency_current_price(url, current_currency_parser)
        heading = str(last_event_currencies[index]['bot_prediction'])

        match = re.search(r'-?\d+\.\d+', heading)
        if match:
            heading = match.group()
        else:
            heading = 0

        current_currency_price = current_currency_price.replace(",",".")

        percent = str(heading)
        if "-" not in percent:
            percent = f"+{percent}"

        heading = float(current_currency_price) + (float(current_currency_price) / 100) * float(heading)
        await message.answer(f"Остання подія для {str(last_event_currencies[index]['currency'])}\n"
                             f"Дата: {str(last_event_currencies[index]['event_full_time'].date())}\n"
                             f"Деталі: {str(last_event_currencies[index]['event_name'])}\n"
                             f"Час: {str(last_event_currencies[index]['time'])}\n"
                             f"Актуальне значення: {str(last_event_currencies[index]['actual'])}\n"
                             f"Прогноз: {str(last_event_currencies[index]['forecast'])}\n"
                             f"Попередній курс: {str(last_event_currencies[index]['previous'])}\n"
                             f"Поточний курс валюти {current_currency_price}\n"
                             f"Прогноз від боту: {round(float(heading), 5)} або {percent}%\n")
        currency_heading.append(round(float(heading), 5))
    if not currency_close_price_parser:
        return currency_heading
    if currency_close_price_parser:
        return close_currency1, close_currency2


async def get_currency_parser(dict_investor, last_day_events, message, details):
    currency_id_checker = []
    for tr in last_day_events:
        event_id = tr.get('id')
        event_name = tr.find(dict_investor['event_class'][0], class_=dict_investor['event_class'][1]).text.strip()
        event_full_time = datetime.strptime(tr[dict_investor['datatime']], '%Y/%m/%d %H:%M:%S')
        time = tr.find(dict_investor['time_class'][0], class_=dict_investor['time_class'][1]).text.strip()

        event_currency = tr.find(dict_investor['event_currency_class'][0],
                                 class_=dict_investor['event_currency_class'][1]).text.strip()
        actual = tr.find(dict_investor['actual_class'][0], class_=dict_investor['actual_class'][1]).text.strip()
        actual = "N/A" if not actual else actual

        forecast = tr.find(dict_investor['forecast_class'][0],
                           class_=dict_investor['forecast_class'][1]).text.strip()
        forecast = "N/A" if not forecast else forecast

        previous = tr.find(dict_investor['prev_class'][0], class_=dict_investor['prev_class'][1]).text.strip()
        previous = "N/A" if not previous else previous

        if actual != "N/A" and previous != "N/A":
            actual_to_float = actual.replace(",", ".")
            previous_to_float = previous.replace(",", ".")
            forecast_to_float = forecast.replace(",", ".")
            if actual_to_float.count(".") <= 1 and previous_to_float.count(".") <= 1:
                if actual[-1] in "BKMT%" and previous[-1] in "BKMT%":
                    actual_to_float = float(actual_to_float[:-1])
                    previous_to_float = float(previous_to_float[:-1])
                    if forecast_to_float != "N/A":
                        forecast_to_float = float(forecast_to_float[:-1])
                actual_to_float = float(actual_to_float)
                previous_to_float = float(previous_to_float)
                actual_to_float = float(actual_to_float)
                previous_to_float = float(previous_to_float)
                if forecast_to_float != "N/A":
                    forecast_to_float = float(forecast_to_float)
                    if previous_to_float < actual_to_float > forecast_to_float:
                        heading = "Значне збільшення."
                    elif previous_to_float < actual_to_float < forecast_to_float:
                        heading = "Невелике збільшення."
                    elif previous_to_float > actual_to_float > forecast_to_float:
                        heading = "Невелике збільшення."
                    elif previous_to_float > actual_to_float < forecast_to_float:
                        heading = "Значне зменшення."
                    elif previous_to_float < actual_to_float == forecast_to_float:
                        heading = ("Ціна може вирости або залишитись залишитись стабільною.\n"
                                   "Для визначення руху ціни недостатньо інформації.")
                    elif previous_to_float > actual_to_float == forecast_to_float:
                        heading = ("Ціна може впасти або залишитись на місці.\n"
                                   "Для визначення руху ціни недостатньо інформації.")
                    elif (previous_to_float == actual_to_float == forecast_to_float):
                        heading = "Для визначення руху ціни недостатньо інформації."
                else:
                    if previous_to_float > actual_to_float:
                        heading = "Зменшення."
                    elif previous_to_float < actual_to_float:
                        heading = "Збільшення."
                    elif previous_to_float == actual_to_float:
                        heading = "Ціна повинна залишитись стабільною."

                currency_id_checker.append(event_id)

                last_event_currency = {
                    "id": event_id,
                    "event_name": event_name,
                    "event_full_time": event_full_time,
                    "currency": event_currency,
                    "time": time,
                    "actual": actual,
                    "forecast": forecast,
                    "previous": previous,
                    "bot_prediction": heading,
                }
        else:
            heading = "Чекаємо закінчення події"
        if details == "Yes":
            await message.answer("\n\n"
                                 f"Час проведення події: {event_full_time}\n"
                                 f"Валюта: {event_currency}\n"
                                 f"Актуальне значення: {actual}\n"
                                 f"Прогноз значення: {forecast}\n"
                                 f"Попереднє значення: {previous}\n"
                                 f"Прогноз від боту: {heading}\n")

    return last_event_currency, currency_id_checker


async def get_currency_info(dict_investor, tr_elements_currency, currencies, today, message, details):
    id_checker = []
    for index in range(len(currencies)):
        today = datetime.now().date()
        while True:
            last_day_events = [tr for tr in tr_elements_currency if datetime.strptime(tr[dict_investor['datatime']],
                                                                                      '%Y/%m/%d %H:%M:%S').date() <= today and tr.find(
                dict_investor['actual_class'][0],
                class_=dict_investor['actual_class'][1]).text.strip() and tr.find(dict_investor['prev_class'][0],
                                                                                  class_=dict_investor['prev_class'][
                                                                                      1]).text.strip() and tr.find(
                dict_investor['event_currency_class'][0],
                class_=dict_investor['event_currency_class'][1]).text.strip() == currencies[index]]
            if last_day_events:
                break
            today -= timedelta(days=1)
        currencies[index], currency_id_checker = await get_currency_parser(dict_investor, last_day_events, message,
                                                                           details)
        id_checker += currency_id_checker
    await message.answer(f"Інформація за {today}")
    return currencies[0], currencies[1], id_checker


async def investing_parce_data(dict_investor, message, details):
    global last_event_currency_1, last_event_currency_2

    today = datetime.now().date()
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    day_of_week = today.weekday()
    day_name = days[day_of_week]
    if day_name == "суббота":
        termin = today - timedelta(days=2)
    elif day_name in ["воскресенье", "понедельник"]:
        termin = today - timedelta(days=4)
    else:
        termin = today - timedelta(days=1)
    payload = {
        'country[]': [25, 4, 17, 39, 72, 26, 10, 6, 37, 43, 56, 36, 5, 61, 22, 12, 35],
        'dateFrom': str(termin),
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

    response = requests.post(dict_investor['url'], data=payload, headers=headers)
    currencies = [dict_investor['chosen_currency1'], dict_investor['chosen_currency2']]
    await message.answer(f"Сайт -> {dict_investor['website_name']}")
    if response.status_code == 200:
        json_data = response.json()
        html_string = json_data['data']
        soup = BeautifulSoup(html_string, 'html.parser')
        tr_elements_currency = soup.find_all(dict_investor['elements_class'][0], dict_investor['elements_class'][1])

        last_event_currency_1, last_event_currency_2, id_checker = await get_currency_info(dict_investor,
                                                                                           tr_elements_currency,
                                                                                           currencies, today, message,
                                                                                           details)

        last_event_currencies = [last_event_currency_1, last_event_currency_2]


        currencies_heading = await show_last_info(last_event_currencies, message)

        return last_event_currency_1, last_event_currency_2, id_checker, currencies_heading
    else:
        await message.answer("err")

