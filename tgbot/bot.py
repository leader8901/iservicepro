from django.core.management.base import BaseCommand
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "iservicepro.settings")
import django

django.setup()

import telebot
from telebot import apihelper, types, StateMemoryStorage  # Нужно для работы Proxy
import re
from telebot import custom_filters
from telebot.handler_backends import StatesGroup, State
import schedule
from iservicepro import settings
from siteservice.models import Phone, NewiPhone, Memory, AllColors, Region, MacBook
from tgbot import keyboard as kb
import environ
# import urllib.request  # request нужен для загрузки файлов от пользователя
from tgbot.models import Profile, Message
import datetime
import time
from telethon.sync import TelegramClient
import csv
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

env = environ.Env()
environ.Env.read_env()
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(settings.TOKEN, state_storage=state_storage)  # Передаём токен из файла setting.py
# apihelper.proxy = {'http': settings.proxy}  # Передаём Proxy из файла config.py
# Initialise environment variables

print('Start BOT')

user_repear = ['ремонт', 'починить', 'отремонтировать', 'почистить', 'замена', 'заменить']
user_buy = ['покупка', 'купить', 'покупать']
user_sale = ['продать', 'продажа', 'продаю', 'продавать']
user_other = ['другое']
admin = env('admin_commands')


# States group.
class MyStates(StatesGroup):
    # Just name variables differently
    price = State()  # с этого момента достаточно создавать экземпляры класса State
    end = State()


def log_errors(f):
    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = f'Произошла ошибка: {e}'
            print(error_message)
            raise e

    return inner


import requests
from bs4 import BeautifulSoup as b

URL = 'https://umma.ru/'


def parser(url):
    r = requests.get(url)
    if r.status_code == 200:
        soup = b(r.text, 'html.parser')
        timenamze = soup.find_all('div', class_='timenamaz__events-item-value')
        return [n.text for n in timenamze]
    else:
        return 'Не удалось получить время'


# Тут работаем с командой start
@bot.message_handler(commands=['start'])
def welcome_start(message):
    user_name = message.from_user.first_name
    chat_id = message.chat.id
    send_mess = f'Приветсвую Вас {user_name}!' \
                "\nДанный бот создан с целью сэкономить Свое и ваше время на телефонные разговоры.\n" \
                "\n" \
                "Узнать стоимость ремонта.\n" \
                "Узнать стоимость новых и б\у телефонов.\n" \
                "Оставить заявку на ремонт, чтобы Мы связались с вами\n" \
                "\n" \
                "\n" \
                "Если все же вы не нашли то, что вам нужно! Пишите\n" \
                "\n" \
                "@leaderisaev \n"
    try:

        # Добавляем пользователя после запуска бота
        profile, _ = Profile.objects.get_or_create(external_id=chat_id, defaults={'name': message.from_user.first_name})
        user_id = Message(profile=profile)
        user_id.save()
        # print('Логин добавлен')
        bot.send_message(message.chat.id, send_mess, reply_markup=kb.markup_menu)

    except Exception as m:
        error_message = f'Произошла ошибка: {m}'
        print(error_message)
        raise m


def update_price(message):
    bot.set_state(message.from_user.id, MyStates.price, message.chat.id)
    bot.send_message(message.chat.id, 'Напишите прайс')


@bot.message_handler(state=MyStates.price)
def name_get(message):
    bot.set_state(message.from_user.id, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['price'] = message.text
        write_data(data['price'])
        # print(data['price'])
    bot.delete_state(message.from_user.id, message.chat.id)
    send_ok(message)


def send_ok(message):
    answer = bot.send_message(message.chat.id, 'Отправлено', reply_markup=kb.markup_menu)
    return answer


def write_data(data, filename='price.txt'):
    with open(filename, "w+") as f:
        f.write(f'{data}\n')
        f.close()
    create_price()


def if_error(message):
    bot.send_message(message.chat.id, 'Что-то пошло не так', reply_markup=kb.markup_menu)


def create_price(count=3000):
    with open('price.txt', 'r+') as s:
        file = s.readlines()
        for line in file:
            t = re.sub('[.,-]', ' ', line)
            phone_data = t.split()
            try:
                if len(phone_data) >= 7:
                    model = ' '.join(phone_data[:3])
                    memory = phone_data[3]
                    color = phone_data[4]
                    region = phone_data[5][-2:]
                    price = int(phone_data[6]) + count
                    add_data_in_db(model, memory, color, region, price)
                elif len(phone_data) == 6:
                    model = ' '.join(phone_data[:2])
                    memory = phone_data[2]
                    color = phone_data[3]
                    price = int(phone_data[5]) + count
                    region = phone_data[4][-2:]
                    add_data_in_db(model, memory, color, region, price)
                elif len(phone_data) == 5:
                    model = ' '.join(phone_data[:1])
                    memory = phone_data[1]
                    color = phone_data[2]
                    price = int(phone_data[4]) + count
                    region = phone_data[3][-2:]
                    add_data_in_db(model, memory, color, region, price)
            except ValueError as v:
                print(v)


def add_data_in_db(model, memory, color, region, price):
    try:
        p, _ = Phone.objects.get_or_create(name=model)
        m, _ = Memory.objects.get_or_create(memory=memory)
        c, _ = AllColors.objects.get_or_create(colors=color)
        r, _ = Region.objects.get_or_create(regions=region)
        data = NewiPhone.objects.filter(model_phone=p, memory_phone=m, colors_phone=c, region_phone=r).exists()
        if data:
            print(f"в наборе есть объекты {data}")
            data = NewiPhone.objects.filter(model_phone=p, memory_phone=m, colors_phone=c, region_phone=r).update(
                price_phone=price)

        else:
            print(f'Нет данных {data}')
            new = NewiPhone(model_phone=p, memory_phone=m, colors_phone=c, region_phone=r, price_phone=price)
            new.save()

    except Phone.DoesNotExist as m:
        error_message = f'Произошла ошибка: {m}'
        print(error_message)
        raise m


def if_error(message):
    error_msg = bot.send_message(message.chat.id, 'Что-то пошло не так', reply_markup=kb.markup_menu)
    return error_msg


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        if call.data == 'sale_new_iphone':
            bot.send_message(call.message.chat.id, text="iPhone 📱", reply_markup=kb.inline_kb_chose_new_model_iphone)
        elif call.data == 'sale_new_macbook':
            bot.send_message(call.message.chat.id, text="MacBook 💻", reply_markup=kb.inline_mac_menu)
        elif call.data == 'sale_iphone14':
            try:
                model = NewiPhone.objects.filter(model_phone__name=f'14').exclude(status='not')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, text=f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone14plus':
            try:
                model = NewiPhone.objects.filter(model_phone__name=f'14 plus').exclude(status='not')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, text=f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone14pro':
            try:
                model = NewiPhone.objects.filter(model_phone__name=f'14 pro').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, text=f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone14promax':
            try:
                model = NewiPhone.objects.filter(model_phone__name=f'14 pro max').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, text=f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone13':
            try:
                model = NewiPhone.objects.filter(model_phone__name=f'13').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, text=f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone13pro':
            try:
                model = NewiPhone.objects.filter(model_phone__name='13 pro').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone13promax':
            try:
                model = NewiPhone.objects.filter(model_phone__name='13 pro max').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone13mini':
            try:
                model = NewiPhone.objects.filter(model_phone__name='13 mini').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone_12promax':
            try:
                model = NewiPhone.objects.filter(model_phone__name='12 pro max').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone_12pro':
            try:
                model = NewiPhone.objects.filter(model_phone__name='12 pro').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone12':
            try:
                model = NewiPhone.objects.filter(model_phone__name='12').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, '⬇️ Отлично! Отправляю прайс ⬇️')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone_12mini':
            try:
                model = NewiPhone.objects.filter(model_phone__name='12 mini').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)

                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone_se2':
            try:
                model = NewiPhone.objects.filter(model_phone__name='SE (2-го поколения)').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone_11pro':
            try:
                model = NewiPhone.objects.filter(model_phone__name='11 pro').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone_11promax':
            try:
                model = NewiPhone.objects.filter(model_phone__name='11 Pro Max').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)

        elif call.data == 'sale_iphone_11':
            try:
                model = NewiPhone.objects.filter(model_phone__name='11').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'iPhone {item}')
            except NewiPhone.DoesNotExist as s:
                print(s)
        elif call.data == 'macbook_air13_22':
            try:
                model = MacBook.objects.filter(model__macbook_name='MacBook Air 13 (mid 2022)').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'{item}')
            except MacBook.DoesNotExist as s:
                print(s)
        elif call.data == 'macbook_pro13_22':
            try:
                model = MacBook.objects.filter(model__macbook_name='MacBook Pro 13(mid 2022)').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'{item}')
            except MacBook.DoesNotExist as s:
                print(s)
        elif call.data == 'macbook_air13_20':
            try:
                model = MacBook.objects.filter(model__macbook_name='MacBook Air 13(mid 2020)').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'{item}')
            except MacBook.DoesNotExist as s:
                print(s)
        elif call.data == 'macbook_pro13_20':
            try:
                model = MacBook.objects.filter(model__macbook_name='MacBook Pro 13(mid 2020)').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'{item}')
            except MacBook.DoesNotExist as s:
                print(s)
        elif call.data == 'macbook_pro14_21':
            try:
                model = MacBook.objects.filter(model__macbook_name='MacBook Pro 14(mid 2021)').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'{item}')
            except MacBook.DoesNotExist as s:
                print(s)
        elif call.data == 'macbook_pro16_21':
            try:
                model = MacBook.objects.filter(model__macbook_name='MacBook Pro 16(mid 2021)').exclude(status='n')
                if not model:
                    bot.send_message(call.message.chat.id, 'Увы! Пока в наличии нет ☹️', reply_markup=kb.markup_menu)
                else:
                    bot.send_message(call.message.chat.id, 'Отлично! Отправляю прайс')
                    for item in model:
                        bot.send_message(call.message.chat.id, f'{item}')
            except MacBook.DoesNotExist as s:
                print(s)
        else:
            bot.send_message(call.message.chat.id, 'Мы работаем над этим 🤧')
    except Exception as e:
        bot.send_message(call.message.chat.id, 'Упс 🤧 что-то не работает ⚙️')
        print(e)


def callback_mac_query(data, message):
    ...
    # chat_id = message.chat.id
    # user_message, _ = Profile.objects.get_or_create(external_id=chat_id, defaults={'message': data})
    # user_id = Message(profile=user_message)
    # print(user_id)
    # bot.send_message(data.message.chat.id, text="MacBook", reply_markup=kb.inline_mac_menu)


class SearchInDb:
    def __init__(self, data):
        self.data = data


# Тут улавливает тексты пользователей
@bot.message_handler(content_types=['text'])
def text_user(message):
    chat_id = message.chat.id
    text_user = message.text.lower()
    if text_user in admin and chat_id == 113129447:
        update_price(message)
    elif text_user in user_buy:
        bot.send_message(chat_id, text="Прайc на Apple", reply_markup=kb.inline_kb_sale_menu)
    elif text_user in user_repear:
        bot.send_message(chat_id,
                         text='Я так понимаю вас интересует ремонт, мы работаем над этим')
    elif text_user in user_sale:
        bot.send_message(chat_id,
                         text='Я так понимаю вы хотите что-то продать, мы работаем над этим')
    elif text_user in user_other:
        bot.send_message(chat_id,
                         text='Если не нашли то, что вам нужно вы можете написать:\n @leaderisaev')
    else:
        bot.send_message(chat_id,
                         text='А вот это мне не знакомо, пожалуй запомню ☺️', reply_markup=kb.markup_menu)
        if not message.chat.id == 113129447:
            try:
                user_name, _ = Profile.objects.get_or_create(external_id=chat_id,
                                                             defaults={'name': message.from_user.first_name})
                user_message = Message(profile=user_name, text=text_user)
                user_message.save()
            except Exception as m:
                error_message = f'Произошла ошибка: {m}'
                print(error_message)
                raise m


def job(fajr, shuruk, zuxr, asr, magrib, isha, ):
    dt_now = datetime.datetime.now()
    if dt_now == fajr:
        return fajr


def send_time_namaz():
    schedule.every().hour.do(job)
    time_namaze = parser(URL)
    fajr = time_namaze[0]
    shuruk = time_namaze[1]
    zuxr = time_namaze[2]
    asr = time_namaze[3]
    magrib = time_namaze[4]
    isha = time_namaze[5]
    return job(fajr, shuruk, zuxr, asr, magrib, isha)


def main():
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            time.sleep(3)
            print(e)


bot.add_custom_filter(custom_filters.StateFilter(bot))

if __name__ == '__main__':
    main()

# __gt для сравнений если больше
# __ls если меньше
# __gte больше или равно
# exclude не равно
# __isnull true or false
# schedule.every(10).minutes.do(job)
# schedule.every().day.at().do(job)
# schedule.every(5).to(10).minutes.do(job)
# schedule.every().monday.do(job)
# schedule.every().wednesday.at("13:15").do(job)
# schedule.every().minute.at(":17").do(job)
# нужно иметь свой цикл для запуска планировщика с периодом в 1 секунду:
# for object in data:
#     object.save(update_fields=["price_phone"])
#     print(object)

# def main():
#     try:
#         bot.polling(none_stop=True, timeout=123, interval=1)
#         while True:
#             schedule.run_pending()
#             time.sleep(10)
#     except Exception as e:
#         print(f'Error {e}')
#     except UnboundLocalError as connect:
#         return main
