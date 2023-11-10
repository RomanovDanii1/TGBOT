import asyncio
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from investor_parser import start_chat_gpt, get_currency_current_price


async def checker_new_events(dict_investor, message, currencies_last_event, id_checker, current_heading_arr):
    today = datetime.now().date()

    payload = {
        'country[]': [25, 4, 17, 39, 72, 26, 10, 6, 37, 43, 56, 36, 5, 61, 22, 12, 35],
        'dateFrom': str(today),
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
    if response.status_code == 200:
        json_data = response.json()
        html_string = json_data['data']
        soup = BeautifulSoup(html_string, 'html.parser')
        tr_elements_currency = soup.find_all(dict_investor['elements_class'][0], dict_investor['elements_class'][1])
        heading_arr = current_heading_arr
        for index in range(len(currencies_last_event)):
            for tr in tr_elements_currency:
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

                if (event_currency == currencies_last_event[index]['currency']
                        and currencies_last_event[index]['event_full_time'] <= event_full_time
                        and actual != "N/A" and previous != "N/A" and (event_id not in id_checker)):

                    id_checker.append(event_id)

                    currencies_last_event[index] = {
                        "id": event_id,
                        "event_name": event_name,
                        "event_full_time": event_full_time,
                        "currency": event_currency,
                        "time": time,
                        "actual": actual,
                        "forecast": forecast,
                        "previous": previous,
                    }
                    parse_info = ["span", {"data-test": "instrument-price-last"}]
                    if index == 0:
                        url = f"https://ru.investing.com/currencies/{dict_investor['chosen_currency1'].lower()}-{dict_investor['chosen_currency2'].lower()}"
                        current_currency_price = await get_currency_current_price(url, parse_info)
                    else:
                        url = f"https://ru.investing.com/currencies/{dict_investor['chosen_currency2'].lower()}-{dict_investor['chosen_currency1'].lower()}"
                        current_currency_price = await get_currency_current_price(url, parse_info)
                    heading = await start_chat_gpt(currencies_last_event[index])
                    while True:
                        if heading == None:
                            await message.answer("Вибачте...\n"
                                                 "Боту потрібно відпочити 1 хвилинку")
                            await asyncio.sleep(60)
                            heading = await start_chat_gpt(currencies_last_event[index])
                        else:
                            break
                    match = re.search(r'-?\d+\.\d+', str(heading))
                    if match:
                        heading = match.group()
                    else:
                        heading = 0
                    percent = str(heading)
                    if "-" not in percent:
                        percent = f"+{percent}"
                    current_currency_price = current_currency_price.replace(",", ".")
                    heading = float(current_currency_price) + (float(current_currency_price) / 100) * float(heading)
                    heading_arr[index] = heading

                    currencies_last_event[index].update({"bot_prediction": heading})
                    await message.answer(f"Увага! Нова подія для {event_currency}\n"
                                         f"Опис події: {str(event_name)}\n"
                                         f"Час: {str(time)}\n"
                                         f"Актуальний показник: {str(actual)}\n"
                                         f"Прогноз показника: {str(forecast)}\n"
                                         f"Попередній показника: {str(previous)}\n"
                                         f"Поточний курс валюти {current_currency_price}\n"
                                         f"Прогноз від боту: {heading} або {percent}%")

        return currencies_last_event[0], currencies_last_event[1], id_checker, heading_arr