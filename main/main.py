import asyncio
import logging
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters.command import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from datetime import datetime, timedelta

import config


from investor_parser import investing_parce_data, show_last_info, day_currency_price
from checker import checker_new_events


logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.TOKEN)
form_router = Router()
dp = Dispatcher()


class Form(StatesGroup):
  currency = State()
  currency1_direction = State()
  currency2_direction = State()
  currency1_price = State()
  currency2_price = State()
  open_day_currency1 = State()
  open_day_currency2 = State()
  bot_prediction_currency1 = State()
  bot_prediction_currency2 = State()
  notification = State()
  dict_investor = State()
  las_event_currency_1 = State()
  las_event_currency_2 = State()
  details = State()
  id_checker = State()
  exit = State()


async def keyboard_builder():
  el = ReplyKeyboardBuilder()
  el.add(types.KeyboardButton(text="Yes"))
  el.add(types.KeyboardButton(text="No"))
  return el


@form_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
  currency_pairs = ["EURUSD", "GBPUSD", "USDCHF", "USDCAD", "USDJPY", "AUDUSD", "NZDUSD"]
  await state.set_state(Form.currency)
  keyboard_pairs = ReplyKeyboardBuilder()
  for pair in currency_pairs:
      keyboard_pairs.add(types.KeyboardButton(text=str(pair)))
  await message.answer("Яку валютну пару ви хочете обрати?", reply_markup=keyboard_pairs.as_markup(resize_keyboard=True, one_time_keyboard=True))


@form_router.message(Form.currency)
async def process_currency_choice(message: types.Message, state: FSMContext):
  data = await state.get_data()
  data['currency'] = message.text
  currency1 = data['currency'][:3:]
  currency2 = data['currency'][3::]

  await message.answer("Ви обрали:\n"
                       f"Валютна пара: {currency1}/{currency2}\n")
  await state.set_state(Form.dict_investor)
  data["dict_investor"] = {
      "chosen_currency1": currency1,
      "chosen_currency2": currency2,
      "url": "https://ru.investing.com/economic-calendar/Service/getCalendarFilteredData",
      "website_name": "investing.com",
      "elements_class": ["tr", {'class': 'js-event-item', 'event_attr_id': True}],
      "datatime": "data-event-datetime",
      "time_class": ["td", 'time'],
      "event_currency_class": ["td", "flagCur"],
      "event_class": ["td", "event"],
      "actual_class": ["td", "bold"],
      "forecast_class": ["td", "fore"],
      "prev_class": ["td", "prev"],
  }


  url_currency1 = f"https://ru.investing.com/currencies/{currency1.lower()}-{currency2.lower()}"
  url_currency2 = f"https://ru.investing.com/currencies/{currency2.lower()}-{currency1.lower()}"

  currency_price_dict = {
      "url": url_currency1,
      "open_current_price": ["dd", {"data-test": "open"}],
      "current_currency_price": ["span", {"data-test": "instrument-price-last"}],
  }

  currency1_price, open_day_currency1 = await day_currency_price(currency_price_dict)
  currency_price_dict.update({"url": url_currency2})
  currency2_price, open_day_currency2 = await day_currency_price(currency_price_dict)

  data["currency1_price"] = currency1_price
  data["open_day_currency1"] = open_day_currency1
  data["currency2_price"] = currency2_price
  data["open_day_currency2"] = open_day_currency2
  await state.update_data(data)


  await message.answer(f"Курс на сьогодні:\n"
                       f"Відкриття {currency1}/{currency2} = {open_day_currency1}\n"
                       f"Відкриття {currency2}/{currency1} = {open_day_currency2}\n"
                       f"Актуальний курс для {currency1}/{currency2} = {currency1_price}\n"
                       f"Актуальний курс для {currency2}/{currency1} = {currency2_price}\n")

  # keyboard_full_info = await keyboard_builder()
  # await message.answer(f"Чи хочете ви подивитись повну інформацію?",
  #                      reply_markup=keyboard_full_info.as_markup(resize_keyboard=True, one_time_keyboard=True))
  # await state.update_data(data)
#   await state.set_state(Form.details)
#
#
# @form_router.message(Form.details)
# async def process_currency_choice(message: types.Message, state: FSMContext):
  data = await state.get_data()
  data["details"] = message.text
  await state.update_data(data)
  las_event_currency_1, las_event_currency_2, id_checker, currencies_heading = await investing_parce_data(data["dict_investor"], message, data["details"])
  data["bot_prediction_currency1"] = currencies_heading[0]
  await state.update_data(data)
  data["bot_prediction_currency2"] = currencies_heading[1]
  await state.update_data(data)
  data["id_checker"] = id_checker
  await state.update_data(data)
  await state.set_state(Form.las_event_currency_1)
  data["las_event_currency_1"] = las_event_currency_1
  await state.update_data(data)
  await state.set_state(Form.las_event_currency_2)
  data["las_event_currency_2"] = las_event_currency_2
  await state.update_data(data)
  # await state.set_state(Form.notification)
  # keyboard_notification = await keyboard_builder()
  # await message.answer(f"Чи хочете ви отримувати повідомлення про нові події стосовно валют {data['currency'][:3:]}/{data['currency'][3::]}",
  #                      reply_markup=keyboard_notification.as_markup(resize_keyboard=True, one_time_keyboard=True))


# @form_router.message(Form.notification, F.text.casefold() == "yes")
# async def process_currency_choice(message: types.Message, state: FSMContext):
  data = await state.get_data()
  time_str = "12:37"
  time = datetime.strptime(time_str, "%H:%M").time()
  currencies_last_event = [data["las_event_currency_1"], data["las_event_currency_2"]]
  id_checker = data["id_checker"]
  url_currency1 = f"https://ru.investing.com/currencies/{data['currency'][:3:].lower()}-{data['currency'][3::].lower()}"
  url_currency2 = f"https://ru.investing.com/currencies/{data['currency'][3::].lower()}-{data['currency'][:3:].lower()}"
  currency_close_price_urls = [url_currency1, url_currency2]
  currency_close_price_parser = ["dd", {"data-test": "open"}]
  alive_checker = (datetime.now() + timedelta(minutes=1)).time()
  await message.answer(f"Ми дамо вам знати, коли з'являться нові події.")

  await state.set_state(Form.exit)
  data['exit'] = False
  await state.update_data(data)
  days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

  await message.answer("Щоб припинити отримувати повідомлення введіть 'exit'")
  while not data['exit']:
      heading_arr = [data['bot_prediction_currency1'], data['bot_prediction_currency2']]
      las_event_currency_1, las_event_currency_2, new_id_checker, heading_arr = await checker_new_events(data["dict_investor"], message, currencies_last_event, id_checker, heading_arr)
      await state.set_state(Form.bot_prediction_currency1)
      data['bot_prediction_currency1'] = heading_arr[0]
      await state.set_state(Form.bot_prediction_currency2)
      data['bot_prediction_currency2'] = heading_arr[1]
      await state.update_data(data)
      currencies_last_event = [las_event_currency_1, las_event_currency_2]
      id_checker = new_id_checker
      now = datetime.now().replace(second=0, microsecond=0).time()
      today = datetime.now()
      day_of_week = today.weekday()
      day_name = days[day_of_week]
      if now.strftime("%H:%M") == alive_checker.strftime("%H:%M"):
          await message.answer("Я живий")
          alive_checker = (datetime.now() + timedelta(minutes=1)).time()
      if now == time and day_name not in ["суббота", "воскресенье"]:

          open_day_currencies = [data['open_day_currency1'], data['open_day_currency2']]

          open_day_currency1, open_day_currency2 = await show_last_info(currencies_last_event,
                                                  message, currency_close_price_parser, data['currency'][:3:],
                                                  data['currency'][3::], currency_close_price_urls, open_day_currencies,
                                                  data["bot_prediction_currency1"], data["bot_prediction_currency2"])
          await state.set_state(Form.open_day_currency1)
          data['open_day_currency1'] = open_day_currency1
          await state.set_state(Form.open_day_currency2)
          data['open_day_currency2'] = open_day_currency2
          await state.update_data(data)
          await asyncio.sleep(50)
          time_str = "12:41"
          time = datetime.strptime(time_str, "%H:%M").time()
          now = datetime.now().replace(second=0, microsecond=0).time()
      await asyncio.sleep(20)
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
