import json
import os
import redis

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
last_block_num = viz.get_dynamic_global_properties()['head_block_number']
redis.set('viz_last_block_num', last_block_num)
#Создание класса обменника
exchange = Exchange(settings, viz=viz, redis=redis)

exchange.post_new_rate(2800000, 5000)