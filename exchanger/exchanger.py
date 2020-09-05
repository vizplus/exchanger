import time
import decimal
import json
import os
import re
import redis
import sys
from datetime import datetime

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

decimal.getcontext().rounding = 'ROUND_HALF_UP'
#Подключение к базе redis
redis = redis.Redis(db=settings['redis_db'])
#Подключение к БЧ VIZ
viz = Api()
#Создание класса обменника
exchange = Exchange(settings, viz=viz, redis=redis)
#Получение номера последнего обработанного блока
try:
    last_block_num = int(redis.get('viz_last_block_num'))
except:
    exchange.send_alert('Ошибка чтения custom операции. Скрипт остановлен.')
    sys.exit()
#Получение и обработка новых блоков каждые 3 секунды
one_minute = three_minute = datetime.timestamp(datetime.now())
while (True):
    block_num = viz.get_dynamic_global_properties()['head_block_number']
    while (last_block_num < block_num):
        last_block_num += 1
        block = viz.get_block(last_block_num)
        for tr in block['transactions']:
            for op in tr['operations']:
                #Обработка входящих транзакций в БЧ VIZ
                if op[0] == 'transfer':
                    op[1]['memo'] = op[1]['memo'].strip()
                    #Обмен полученных VIZ на USDT
                    if (op[1]['to'] == exchange.sett['viz_wallet']['login']
                            and len(op[1]['memo']) > 0):
                        #Адрес кошелька пользователя для перевода USDT
                        eth_wallet = op[1]['memo'].strip().lower()
                        if re.fullmatch('0x[0-9a-f]{40}', eth_wallet):
                            #Количество полученных от пользователя VIZ
                            viz_amount = decimal.Decimal(
                                float(op[1]['amount'][0:-4])
                            ).quantize(decimal.Decimal(
                                '1.' + '0'*exchange.sett['viz_precision']
                            ))
                            #Проверка лимитов полученных от пользователя VIZ
                            if viz_amount >= exchange.sett['viz_limit_min']:
                                if viz_amount > exchange.sett['viz_limit_max']:
                                    viz_amount = exchange.sett['viz_limit_max']
                                #Обмен VIZ на USDT и получение ID транзакции
                                #перевода в сети ETH
                                txn_id = exchange.change_viz_to_usdt(
                                    viz_amount, 
                                    eth_wallet
                                )
                                exchange.send_alert('Сделка с ' + op[1]['from']+
                                                    'завершена.')
                            else:
                                exchange.send_alert('Неверное количество VIZ.')
                        else:
                            exchange.send_alert('Неверно указан кошелек ETH.')
                    #Создание и публикация нового кошелька для пользователя при
                    #обменен USDT на VIZ
                    elif (op[1]['to'] == exchange.sett['rate_account']['login']
                          and 
                          decimal.Decimal(op[1]['amount'][0:-4]).quantize(
                              decimal.Decimal(
                                  '1.' + '0'*exchange.sett['viz_precision']
                              )
                          ) == exchange.sett['eth_wallet_cost']):
                        if block_num - last_block_num < 100:
                            exchange.create_new_address(
                                op[1]['from'], 
                                last_block_num
                            )
                        else:
                            viz.transfer(
                                op[1]['from'],
                                exchange.sett['eth_wallet_cost'],
                                self.sett['rate_account']['login'],
                                self.sett['rate_account']['key']
                            )
        new_time = datetime.timestamp(datetime.now())
        #Ежеминутная проверка кошельков в сети ETH
        delta_time = new_time - one_minute
        if delta_time > 60:
            one_minute = new_time
            #Проверка переводов на кошельки в сети ETH
            exchange.get_etherium_txn()
            #Перевод средств с кошельков ETH на горячий кошелек после окончания
            #обмена
            exchange.claim_balance()
            for key in exchange.redis.scan_iter('0x*:block_num'):
                wallet = key.decode('utf-8')
                i = wallet.find(':')
                wallet = wallet[0:i]
                expiration_block_num = (int(exchange.redis.get(key)) + 
                                        exchange.sett['expiration_block_count'] + 
                                        exchange.sett['additional_expiration_count']
                                       )
                if expiration_block_num < last_block_num:
                    exchange.redis.delete(key)
                    exchange.send_alert(
                        'Начало удаление информации о кошельке ' + wallet
                    )
                    exchange.delete_wallet_info(wallet)
        #События каждые 3 минуты
        delta_time = new_time - three_minute
        if delta_time > 180:
            three_minute = new_time
            exchange.post_status()
        #Обновление номера последнего обработанного блока
        redis.set('viz_last_block_num', last_block_num)
    #Трехсекундная задержка перед запросом следующего блока
    time.sleep(3)
