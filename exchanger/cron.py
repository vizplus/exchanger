import json
import os
import redis
import sys

#Класс обменника
from exchange.Exchange import Exchange
#Библиотека для работы с БЧ VIZ
from tvizbase.api import Api

#Загрузка настроек из файла
path = os.path.dirname(__file__)
if path == '':
    path = '.'
with open(path + '/settings.json', 'r') as sett_file:
    settings = json.load(sett_file)

#Подключение к базе redis
redis = redis.Redis(db=settings['redis_db'])
#Подключение к БЧ VIZ
viz = Api()
#Создание класса обменника
exchange = Exchange(settings, viz=viz, redis=redis)

#Проверка наличия команды от бота
try:
    tgbot_command = redis.get('tgbot_command').decode('utf-8')
except:
    sys.exit()
redis.delete('tgbot_command')
#Старт или остановка обменника
if tgbot_command == 'start':
    os.system('systemctl start exchanger.service')
    exchange.send_alert('Обменник запущен.')
elif tgbot_command == 'stop':
    os.system('systemctl stop exchanger.service')
    exchange.send_alert('Обменник остановлен.')
