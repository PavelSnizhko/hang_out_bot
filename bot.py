import telebot
from collections import defaultdict
from loguru import logger

from db import SQLWorker
import requests
import os
from telebot import types

logger.add("debug.log", format="{time} {level} {message}", level="DEBUG", rotation="10:00", compression="zip")
# try to get heroku variable
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
url_media = os.path
bot = telebot.TeleBot(TOKEN, parse_mode=None)

db = SQLWorker('places.db')
db.set_up()


@bot.message_handler(commands=['start', 'help'])
def describe_option(message):
    bot.send_message(message.chat.id, text="""
    Привет этот бот создан для сохранение мест.
    Все доступные функции смотри ниже:
    /start - Начать роботу
    /help - Получить информацию о функцииях бота
    /near_locations - Посмотреть мои локации в районе 500 метров
    /reset - Удалить все места
    /list - Показать список из 10 локаций
    /add - Добавить новое место  """
                     )


def get_img(message) -> str:
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    if not os.path.exists('media'):
        os.makedirs('media')
    with open(f"media/image_{file_id}.jpg", 'wb') as new_file:
        new_file.write(downloaded_file)
    return new_file.name


def output_place(message, data) -> None:
    try:
        bot.send_message(message.chat.id, data[5])
        sent_photo(data[2], message)
        bot.send_location(message.chat.id, data[3], data[4])
    except KeyError as err:
        bot.send_message(message.chat.id, err)


def sent_photo(url, message):
    try:
        with open(url, 'rb') as f:
            img = f.read()
        bot.send_photo(message.chat.id, photo=img)
    except FileNotFoundError:
        bot.send_message(message.chat.id, "Без фото")


def get_near_locations(message):
    """Getting location all location from db and compare with user location """
    found_places = []
    records = db.select_all(message.chat.id)
    if len(records) > 0:
        for record in records:
            origins = f"{message.location.latitude},{message.location.longitude}"
            destinations = f"{record[3]},{record[4]}"
            url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origins}&destinations={destinations}&key=" + API_KEY
            try:
                response = requests.get(url).json()
                distance = float(response['rows'][0]['elements'][0]['distance']['text'].split(' ')[0])
                if distance <= 2:
                    found_places.append(record)
            except Exception as ex:
                bot.send_message(message.chat.id, ex)
        if len(found_places) > 0:
            for place in found_places:
                output_place(message, place)
        else:
            bot.send_message(message.chat.id, "Локаций в районе 2 километров не обнаружено")
    else:
        bot.send_message(message.chat.id, text="У вас нету сохраненных мест нажмите /add что б добвить новое место")


@bot.message_handler(commands=['near_locations'])
def handle_home_position(message) -> None:
    bot.send_message(message.chat.id, text="Отправь локацию на что бы узнать есть ли здесь какие-нибудь места")
    bot.register_next_step_handler(message, get_near_locations)


def make_keyboard(options=('Да', 'Нет')):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(o, callback_data=o) for o in options]
    keyboard.add(*buttons)
    return keyboard


@bot.message_handler(commands=['add'])
def handle_adding(message) -> None:
    start, title, photo, location, success = range(5)
    user_state = defaultdict(lambda: start)
    product_state = defaultdict(lambda: {})

    def get_state(message):
        return user_state[message.chat.id]

    def update_state(message, state):
        user_state[message.chat.id] = state

    def update_product(user_id, key, value):
        product_state[user_id][key] = value

    def get_product(user_id):
        return product_state[user_id]

    if get_state(message) == start:
        if message.text.lower() == 'нет':
            product_state = defaultdict(lambda: {})
            bot.register_next_step_handler(message, describe_option)
        else:
            bot.send_message(message.chat.id, text='Напишите название')
            update_state(message, title)

    @bot.message_handler(func=lambda message: get_state(message) == title)
    def handle_title(message) -> None:
        update_product(message.chat.id, 'title', message.text)
        bot.send_message(message.chat.id, text="Выбери с фото или без", reply_markup=make_keyboard(('Фото', 'Нет')))
        update_state(message, photo)


    @bot.callback_query_handler(func=lambda call: get_state(call.message) == photo)
    def handle_refusal_photo(callback_query) -> None:
        if callback_query.data == 'Нет':
            update_product(callback_query.message.chat.id, 'photo', 'Без фото')
            bot.send_message(callback_query.message.chat.id, text="А теперь отправь локацию")
            update_state(callback_query.message, location)
        elif callback_query.data == 'Фото':
            bot.send_message(callback_query.message.chat.id, text="Давай скорее фото")
            bot.register_next_step_handler(callback_query.message, handle_photo)

    def handle_photo(message):
        try:
            update_product(message.chat.id, 'photo', get_img(message))
            bot.send_message(message.chat.id, text="А теперь отправь локацию ")
            update_state(message, location)
        except TypeError:
            bot.send_message(message.chat.id, text="Упс что-то не так давайте заново.Нажмите /start")
            return

    @bot.message_handler(func=lambda message: get_state(message) == location, content_types=['location'])
    def handle_location(message) -> None:
        try:
            update_product(message.chat.id, 'latitude', message.location.latitude)
            update_product(message.chat.id, 'longitude', message.location.longitude)
            bot.send_message(message.chat.id, "Если вы действительно хотите добавить то нажмите да, иначе нет",
                             reply_markup=make_keyboard())
            update_state(message, success)
        except Exception as ex:
            print(ex)

    def save_to_db(data) -> None:
        db.insert_new_place(data)

    @bot.callback_query_handler(func=lambda call: get_state(call.message) == success)
    def success_handle(callback_query):
        print()
        if callback_query.data == 'Да':
            data = get_product(callback_query.message.chat.id)
            data['user_id'] = callback_query.message.chat.id
            save_to_db(data)
            bot.send_message(callback_query.message.chat.id, text=data['title'])
            try:

                with open(data['photo'], 'rb') as f:
                    img = f.read()
                bot.send_photo(callback_query.message.chat.id, photo=img)
            except FileNotFoundError:
                bot.send_message(callback_query.message.chat.id, data['photo'])
            bot.send_location(callback_query.message.chat.id, latitude=data['latitude'], longitude=data['longitude'])
            bot.send_message(callback_query.message.chat.id, text='Успешно отправленно')
            update_state(callback_query.message, state=start)
        else:
            bot.send_message(callback_query.message.chat.id, text='Вы отменили отправку места')
            update_state(callback_query.message, state=start)
            return




@bot.message_handler(commands=['reset'])
def handle_removing(message):
    users_photos = db.get_all_photos(message.chat.id)
    remove_from_media(users_photos)
    db.remove_all_records(message.chat.id)
    bot.send_message(message.chat.id, 'Удалено все локации')


def remove_from_media(user_photos):
    photos = list(map(lambda photo_path: photo_path[0][6:], user_photos))
    try:
        file_list = [f for f in os.listdir("media/") if f in photos]
        for f in file_list:
            os.remove(os.path.join("media/", f))
    except OSError as e:
        logger.error(e)
        pass


@bot.message_handler(commands=['list'])
def handle_showing(message):
    result = db.select_ten_records(message.chat.id)
    if len(result) > 0:
        for record in result:
            output_place(message, record)
    else:
        bot.send_message(message.chat.id, 'У Вас нету локацый')

@logger.catch()
def main():
    bot.polling(none_stop=True)


if __name__ == '__main__':
    main()


