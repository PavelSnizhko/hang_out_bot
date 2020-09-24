import telebot
from collections import defaultdict
from db import SQLWorker
import requests
import config
import os

bot = telebot.TeleBot(config.TOKEN, parse_mode=None)

db = SQLWorker('places.db')
db.set_up()



def get_img(message):
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(f"media/image_{file_id}.jpg", 'wb') as new_file:
        new_file.write(downloaded_file)
    return new_file.name


def output_place(message, data):
    try:
        bot.send_message(message.chat.id, data[5])
        print(data[2])
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
        bot.send_message(message.chat.id, "Фото відсутнє")


def get_near_locations(message):
    """Getting location all location from db and compare with user location """
    found_places = []
    records = db.select_all(message.chat.id)
    if len(records) > 0:
        for record in records:
            origins = f"{message.location.latitude},{message.location.longitude}"
            destinations = f"{record[3]},{record[4]}"
            url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origins}&destinations={destinations}&key="+config.GOOGLE_API_KEY
            try:
                # Get the API response.
                response = requests.get(url).json()
                distance = float(response['rows'][0]['elements'][0]['distance']['text'].split(' ')[0])
                if distance <= 0.5:
                    found_places.append(record)
            except Exception as ex:
                bot.send_message(message.chat.id, ex)
        if len(found_places) > 0:
            for place in found_places:
                output_place(message, place)
        else:
            bot.send_message(message.chat.id, "Локаций в районе 500 метров не обнаружено")
    else:
        bot.send_message(message.chat.id, text="У вас нету сохраненных мест")





@bot.message_handler(commands=['near_locations'])
def handle_home_position(message):
    bot.send_message(message.chat.id, text="Отправь локацию на что бы узнать есть ли здесь какие-нибудь места")
    bot.register_next_step_handler(message, get_near_locations)



@bot.message_handler(commands=['add'])
def handle_adding(message):
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
            return
        else:
            bot.send_message(message.chat.id, text='Хей бро или сро напиши название')
            update_state(message, title)

    @bot.message_handler(func=lambda message: get_state(message) == title)
    def handle_title(message):
        update_product(message.chat.id, 'title', message.text)
        bot.send_message(message.chat.id, text="Давай скорей фотку кидай, если без фото напиши слово 'нет' ")
        update_state(message, photo)

    @bot.message_handler(func=lambda message: get_state(message) == photo, content_types=['photo'])
    def handle_photo(message):
        update_product(message.chat.id, 'photo', get_img(message))
        bot.send_message(message.chat.id, text="А теперь отправь локацию ")
        update_state(message, location)

    @bot.message_handler(func=lambda message: get_state(message) == photo, content_types=['text'])
    def handle_refusal_photo(message):
        if message.text.lower() == 'нет':
            update_product(message.chat.id, 'photo', 'Без фото')
            bot.send_message(message.chat.id, text="А теперь отправь локацию")
            update_state(message, location)

    @bot.message_handler(func=lambda message: get_state(message) == location, content_types=['location'])
    def handle_photo(message):
        try:
            update_product(message.chat.id, 'latitude', message.location.latitude)
            update_product(message.chat.id, 'longitude', message.location.longitude)
            bot.send_message(message.chat.id, text="Подтвердить, ДА?")
            update_state(message, success)
        except Exception as ex:
            print(ex)

    def save_to_db(data):
        db.insert_new_place(data)

    @bot.message_handler(func=lambda message: get_state(message) == success)
    def success_handle(message):
        data = product_state[message.chat.id]
        data['user_id'] = message.chat.id
        save_to_db(data)
        bot.send_message(message.chat.id, text=data['title'])
        try:

            with open(data['photo'], 'rb') as f:
                img = f.read()
            bot.send_photo(message.chat.id, photo=img)
        except FileNotFoundError:
            bot.send_message(message.chat.id, data['photo'])
        bot.send_location(message.chat.id, latitude=data['latitude'], longitude=data['longitude'])
        bot.send_message(message.chat.id, text='Успешно отправленно')
        update_state(message, state=start)


@bot.message_handler(commands=['reset'])
def handle_removing(message):
    users_photos = db.get_all_photos(message.chat.id)
    print(users_photos)
    remove_from_media(users_photos)
    db.remove_all_records(message.chat.id)
    bot.send_message(message.chat.id, 'Удалено все локации')


def remove_from_media(user_photos):
    photos = list(map(lambda photo_path: photo_path[5:], user_photos))
    for filename in os.listdir("media/"):
        if filename in photos:
            os.remove(filename)



@bot.message_handler(commands=['list'])
def handle_showing(message):
    result = db.select_ten_records(message.chat.id)
    if len(result) > 0:
        for record in result:
            output_place(message, record)
    else:
        bot.send_message(message.chat.id, 'У Вас нету локаций')


if __name__ == '__main__':
    bot.polling()
    db.close()
