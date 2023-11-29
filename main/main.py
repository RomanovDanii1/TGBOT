import asyncio
import logging
from datetime import datetime, time, timedelta

from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters.command import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder

import config
from investor_parser import (from_arr_to_set, from_arr_to_dict, get_currency_price_for_currencies,
                             get_last_info_for_selected_currencies, show_day_prediction)
from checker import new_event_checker, new_event_prediction, show_predicted_info, show_day_info

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.TOKEN, parse_mode='HTML')
form_router = Router()
dp = Dispatcher()

#Список валютних пар, які може обрати користувач
currency_pairs = ["EURUSD", "GBPUSD", "USDCHF", "USDCAD", "USDJPY", "AUDUSD", "NZDUSD"]
class Form(StatesGroup):
    parser_dict = State()
    current_currency_dict = State()
    all_currencies_dict = State()
    exit = State()

#Обробник команди "/start"

@form_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    data = await state.get_data()



    await message.answer("Бот потрібно трішки подумати...")

    #Створюємо словник, в якому описуємо базовий вигляд для валютної пари
    await state.set_state(Form.parser_dict)
    #Створюємо словник, в якому описуємо усі, потрібні для парсингу інформації, дані
    data["parser_dict"] = {
        "url": "https://ru.investing.com/economic-calendar/Service/getCalendarFilteredData", #Посилання на сторінку для парсингу
        "website_name": "investing.com", #Назва сайту
        "elements_class": ["tr", {'class': 'js-event-item', 'event_attr_id': True}], #Тег і поля для отримання всіх публікацій
        "datatime": "data-event-datetime", #Поле для отримання повної інформації про час публікації події
        "time_class": ["td", 'time'], #Тег і полу для отримання часу (тільки години) проведення події
        "event_currency_class": ["td", "flagCur"], #Тег і поле для отримання назви валюти
        "event_class": ["td", "event"], #Тег і полк для отримання опису події
        "actual_class": ["td", "bold"], #Тег і поле для отримання актуального курсу події
        "forecast_class": ["td", "fore"], #Тег і поле для отримання прогнозу курсу події
        "prev_class": ["td", "prev"], #Тег і поле для отримання попереднього курсу події
    }

    currencies = await from_arr_to_set(currency_pairs)

    currencies_dict = await from_arr_to_dict(currency_pairs)

    currencies_dict = await get_currency_price_for_currencies(currencies_dict)

    last_currencies_event_dict = await get_last_info_for_selected_currencies(currencies, data["parser_dict"], message)

    day_prediction = await show_day_prediction(currencies_dict, last_currencies_event_dict, message)

    await show_predicted_info(day_prediction, message)

    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]



    await message.answer("Ми дамо вам знати, коли з'являться нові події.")
    now = datetime.now()
    if datetime.combine(now.date(), time(3, 0)) > now:
        time_for_day_prediction = datetime.combine(now.date(), time(3, 0))
    else:
        time_for_day_prediction = datetime.combine(now.date(), time(3, 0)) + timedelta(days=1)
    time_for_day_info = datetime.combine(now.date(), time(0, 0)) + timedelta(days=1)

    while days[time_for_day_info.weekday()] in ["суббота", "воскресенье"]:
        time_for_day_info += timedelta(days=1)
    while days[time_for_day_prediction.weekday()] in ["суббота", "воскресенье"]:
        time_for_day_prediction += timedelta(days=1)


    await state.set_state(Form.exit)
    data['exit'] = False
    await state.update_data(data)
    await message.answer("Щоб припинити отримувати повідомлення введіть 'exit'")
    # Запускаємо нескінченний цикл для інтервальної перевірки сайту на нові події.
    while not data['exit']:
        now = datetime.now()
        now = now.replace(microsecond=0, second=0)
        today = datetime.now()
        day_of_week = today.weekday()
        day_name = days[day_of_week]
        if day_name not in ["суббота", "воскресенье"]:
            last_currencies_event_dict, temp_arr = await new_event_checker(last_currencies_event_dict, data["parser_dict"], message, currencies_dict)
            if temp_arr:
                day_prediction = await new_event_prediction(last_currencies_event_dict, day_prediction, temp_arr, message)
                temp_arr = []
                await show_predicted_info(day_prediction, message)

        if now >= time_for_day_info and day_name not in ["суббота", "воскресенье"]:
            await message.answer("Інформація за минулий день")
            time_for_day_info += timedelta(days=1)
            while days[time_for_day_info.weekday()] in ["суббота", "воскресенье"]:
                time_for_day_info += timedelta(days=1)
            await show_day_info(day_prediction, currencies_dict, message)

        if now >= time_for_day_prediction and day_name not in ["суббота", "воскресенье"]:
            await message.answer("Передбачення на день")
            time_for_day_prediction += timedelta(days=1)
            while days[time_for_day_prediction.weekday()] in ["суббота", "воскресенье"]:
                time_for_day_prediction += timedelta(days=1)
            await show_predicted_info(day_prediction, message, True)

        await asyncio.sleep(60)
        data = await state.get_data()
        if data['exit']:
            break
    await state.clear()
    await message.answer("Дякую за користування.")


@dp.message(F.text.casefold() == "exit")
async def exit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(Form.exit)
    data['exit'] = True
    await state.update_data(data)

async def main():
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())






