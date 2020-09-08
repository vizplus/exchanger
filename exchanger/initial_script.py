import decimal
import json
import os
import redis
from datetime import datetime

#Класс обменника
from exchange.Exchange import Exchange
#Библиотека для работы с БЧ VIZ
from tvizbase.api import Api

decimal.getcontext().rounding = 'ROUND_HALF_UP'
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
#exchange = Exchange(settings, viz=viz, redis=redis)

#exchange.post_new_rate(2800000, 5000)
viz_balance = 2000000
usdt_balance = 2100
rate = decimal.Decimal(
    usdt_balance / (settings['exchange_ratio'] * viz_balance)
).quantize(decimal.Decimal('1.' + '0'*settings['rate_precision']))
settings['viz_limit_max'] = decimal.Decimal(
    float(viz_balance) * 
    (1 - (1 - settings['viz_limit_percent']) ** 
        float(settings['exchange_ratio'])
    )
).quantize(decimal.Decimal('1.' + '0'*settings['viz_precision']))
settings['usdt_limit_max'] = decimal.Decimal(
    float(usdt_balance) * 
    ((1 + settings['usdt_limit_percent']) ** 
        float(1 / settings['exchange_ratio']) - 1
    ) + float(settings['usdt_fee'])
).quantize(decimal.Decimal('1.' + '0'*settings['usdt_precision']))
buy_viz_limit_min = decimal.Decimal(
    viz_balance * 
    (((settings['usdt_limit_min'] - settings['usdt_fee']) / 
        usdt_balance + 1) ** settings['exchange_ratio'] - 1
    )
).quantize(decimal.Decimal('1.' + '0'*settings['viz_precision']))
buy_viz_limit_max = decimal.Decimal(
    float(viz_balance) * settings['viz_limit_percent']
).quantize(decimal.Decimal('1.' + '0'*settings['viz_precision']))
buy_usdt_limit_min = decimal.Decimal(
    usdt_balance * 
    (1 - (1 - settings['viz_limit_min'] / viz_balance) ** 
        (1 / settings['exchange_ratio'])
    )
) - settings['usdt_fee']
buy_usdt_limit_min = decimal.Decimal(
    buy_usdt_limit_min
).quantize(decimal.Decimal('1.' + '0'*settings['usdt_precision']))
buy_usdt_limit_max = decimal.Decimal(
    float(usdt_balance) * settings['usdt_limit_percent']
).quantize(decimal.Decimal('1.' + '0'*settings['usdt_precision']))
viz.custom(
    'vizplus_exchange', # ID custom'а 
    [
        'exchange_data', # название типа данных
        {
            'datetime': str(datetime.utcnow()),
            'viz_balance': str(viz_balance),
            'viz_limit_min': str(settings['viz_limit_min']),
            'viz_limit_max': str(settings['viz_limit_max']),
            'buy_viz_limit_min': str(buy_viz_limit_min),
            'buy_viz_limit_max': str(buy_viz_limit_max),
            'usdt_balance': str(usdt_balance),
            'usdt_limit_min': str(settings['usdt_limit_min']),
            'usdt_limit_max': str(settings['usdt_limit_max']),
            'buy_usdt_limit_min': str(buy_usdt_limit_min),
            'buy_usdt_limit_max': str(buy_usdt_limit_max),
            'rate': str(rate),
            'exchange_ratio': str(
                decimal.Decimal(
                    settings['exchange_ratio']
                ).quantize(decimal.Decimal('1.00'))
            ),
            'usdt_fee': str(settings['usdt_fee']),
            'eth_wallet_cost': str(settings['eth_wallet_cost']),
            'viz_wallet': settings['viz_wallet']['login'],
            'viz_wallet_cold': settings['viz_wallet_cold']['login'],
            'eth_wallet': settings['eth_wallet']['login'],
            'eth_wallet_cold': settings['eth_wallet_cold']['login'],
            'bird_account': settings['bird_account']['login']
        }
    ], 
    settings['rate_account']['login'], 
    settings['rate_account']['key']
)
