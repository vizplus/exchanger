import decimal
import json
import sha3
import sys
from ecdsa import SigningKey, SECP256k1
from datetime import datetime

#Библиотека для работы с БЧ ETH
from web3 import Web3, middleware
from web3.gas_strategies.time_based import medium_gas_price_strategy
from web3.gas_strategies.time_based import slow_gas_price_strategy
#Библиотека для работы с Telegram
from telegram import Bot

class Exchange():
    def __init__(self, sett, **kwargs):
        """
        Инициализация класса и настроек

        :param dict sett: настройки класса
            Decimal exchange_ratio - коэффициент, используемый для расчета
                                     обменного курса
            Decimal viz_limit_min - минимальный лимит для продажи VIZ
            float viz_limit_percent - максимальный лимит для продажи VIZ в
                                      процентах от общего их количества в фонде
            int viz_precision - количество знаков после запятой для округления 
                                VIZ
            Decimal usdt_limit_min - минимальный лимит для продажи USDT
            float usdt_limit_percent - максимальный лимит для продажи USDT в
                                       процентах от общего их количества в фонде
            int usdt_precision - количество знаков после запятой для округления
                                 USDT
            float usdt_fee - комиссия обменника в USDT
            Decimal eth_wallet_cost - комиссия обменника в VIZ при создании
                                      кошелька в сети ETH 
            int rate_precision - количество знаков после запятой для округления
                                 обменного курса
            int expiration_block_count - количество блоков из сети VIZ, которые
                                         даются для совершения сделки по продаже
                                         USDT
            int additional_expiration_count - дополнительное количество блоков
                                              из сети VIZ, после которых
                                              удаляются данные о созданных
                                              кошельках USDT из базы обменника
            int redis_db - номер базы данных Redis
            str eth_node - адрес ноды ETH
            dict eth_wallet - словарь с данными о горячем кошельке ETH
                str login - адрес кошелька
                str key - ключ кошелька
            dict viz_wallet - словарь с данными о горячем кошельке VIZ
                str login - логин кошелька
                str key - активный ключ кошелька
            dict rate_account - словарь с данными о кошельке VIZ для размещения
                                custom операций
                str login - логин кошелька
                str key - регулярный или активный ключ кошелька
            },
            str USDT_ABI - ABI контракта USDT
        :param  viz: ссылка на объект для работы с сетью VIZ
        :param  redis: ссылка на объект для работы с Redis
        """
        self.sett = sett
        self.sett['exchange_ratio'] = decimal.Decimal(
            self.sett['exchange_ratio']
        )
        self.sett['usdt_fee'] = decimal.Decimal(self.sett['usdt_fee'])
        self.sett['viz_limit_min'] = decimal.Decimal(
            self.sett['viz_limit_min']
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['viz_precision']))
        self.sett['usdt_limit_min'] = decimal.Decimal(
            self.sett['usdt_limit_min']
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['usdt_precision']))
        self.sett['eth_wallet_cost'] = decimal.Decimal(
            self.sett['eth_wallet_cost']
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['viz_precision']))
        self.viz = kwargs.pop('viz')
        self.redis = kwargs.pop('redis')
        self.tgbot = Bot(self.sett['tg_token'])
        self.get_exchange_rate()
        self.web3 = Web3(Web3.HTTPProvider(self.sett['eth_node']))
        self.web3.eth.setGasPriceStrategy(slow_gas_price_strategy)
        USDT_ABI = self.sett['USDT_ABI']
        self.usdt_contract = self.web3.eth.contract(
            self.web3.toChecksumAddress(
                '0xdac17f958d2ee523a2206206994597c13d831ec7'
            ), 
            abi=USDT_ABI
        )
        self.decimals = self.usdt_contract.functions.decimals().call()

    def change_usdt_to_viz(self, usdt_amount, user_wallet):
        """
        Обмен USDT на VIZ

        :param Decimal usdt_amount: количество полученных от пользователя USDT
        :param str user_wallet: кошелек, на который поступили USDT
        """
        if usdt_amount >= self.sett['usdt_limit_min']:
            if usdt_amount > self.sett['usdt_limit_max']:
                usdt_amount = self.sett['usdt_limit_max']
            usdt_amount -= self.sett['usdt_fee']
            try:
                viz_login = self.redis.get(
                    user_wallet + ':viz_login'
                ).decode('utf-8')
            except:
                self.redis.delete(user_wallet + ':block_num')
                self.send_alert(
                    'Ошибка при покупке VIZ. Не найден аккаунт VIZ.'
                )
                return
            viz_amount = decimal.Decimal(
                self.viz_balance * ((usdt_amount / self.usdt_balance + 1) ** 
                                    self.sett['exchange_ratio'] - 1
                                   )
            ).quantize(decimal.Decimal('1.' + '0'*self.sett['viz_precision']))
            self.viz.transfer(
                viz_login, 
                viz_amount, 
                self.sett['viz_wallet']['login'], 
                self.sett['viz_wallet']['key']
            )
            self.send_alert('Из ' + self.sett['viz_wallet']['login'] + ' на ' + 
                            viz_login + ' переведено ' + viz_amount +
                            ' VIZ. Сделка завершена.')
            self.post_new_rate(
                self.viz_balance - viz_amount, 
                self.usdt_balance + usdt_amount
            )
            self.redis.delete(user_wallet + ':block_num')
            self.redis.set(user_wallet + ':claim', '')
        else:
            self.redis.delete(user_wallet + ':block_num')
            self.send_alert(
                'Пользователь прислал USDT меньше минимального порога.'
            )

    def change_viz_to_usdt(self, viz_amount, user_wallet):
        """
        Обмен VIZ на USDT

        :param float viz_amount: количество полученных от пользователя VIZ
        :param str user_wallet: кошелек, на который переводить USDT
        """
        viz_amount = decimal.Decimal(viz_amount)
        usdt_amount = decimal.Decimal(
            self.usdt_balance * 
            (1 - (1 - viz_amount / self.viz_balance) ** 
             decimal.Decimal(1 / self.sett['exchange_ratio'])
            )
        ) - self.sett['usdt_fee']
        usdt_amount = decimal.Decimal(usdt_amount).quantize(
            decimal.Decimal('1.' + '0'*self.sett['usdt_precision'])
        )
        txn_id = self.transfer_usdt(
            usdt_amount,
            user_wallet,
            self.sett['eth_wallet']['login'],
            self.sett['eth_wallet']['key'],
            medium_gas=True
        )
        self.send_alert('На горячий кошелёк поступили ' + viz_amount +
                        ' VIZ. На ' + user_wallet + ' отправлено ' +
                        usdt_amount + ' USDT.')
        self.post_new_rate(
            self.viz_balance + viz_amount, 
            self.usdt_balance - usdt_amount
        )
        return txn_id

    def claim_balance(self):
        """
        Вывод USDT и остатков ETH с кошелька после завершения обмена
        """
        for key in self.redis.scan_iter('0x*:claim'):
            wallet = key.decode('utf-8')
            i = wallet.find(':')
            wallet = wallet[0:i]
            try:
                txn_id = self.redis.get(wallet + ':txn_id').decode('utf-8')
            except:
                txn_id = ''
            if txn_id != '':
                try: 
                    txn = self.web3.eth.getTransaction(txn_id)
                except TransactionNotFound:
                    txn = None
                    self.redis.set(wallet + ':txn_id', '')
                    self.send_alert('Транзакция ' + txn_id + ' не найдена.')
                if txn != None:
                    if txn['blockNumber'] != None:
                        self.redis.set(wallet + ':txn_id', '')
                    else:
                        continue
            usdt_balance = decimal.Decimal(
                self.usdt_contract.functions.balanceOf(wallet).call() / 
                (10 ** self.decimals)
            ).quantize(decimal.Decimal('1.' + '0'*self.sett['usdt_precision']))
            if usdt_balance < self.sett['usdt_fee']:
                self.redis.delete(key)
                self.delete_wallet_info(wallet)
                continue
            eth_balance = self.web3.eth.getBalance(wallet)
            gas = self.usdt_contract.functions.transfer(
                self.sett['eth_wallet']['login'], 
                int(usdt_balance * (10 ** self.decimals))
            ).estimateGas({'from': wallet})
            gas_to_eth = gas * self.web3.eth.gasPrice;
            if eth_balance > gas_to_eth / 2 and usdt_balance > 0:
                try:
                    private_key = self.redis.get(
                        wallet + ':private_key'
                    ).decode('utf-8')
                except:
                    self.send_alert('Не найден приватный ключ от кошелька ' +
                                    wallet + '.')
                    private_key = ''
                if private_key != '':
                    if gas_to_eth > eth_balance:
                        gas_to_eth = eth_balance
                    txn_id = self.transfer_usdt(
                        usdt_balance, 
                        self.sett['eth_wallet']['login'], 
                        wallet, 
                        private_key, 
                        eth_for_gas=gas_to_eth
                    )
                    self.send_alert('С ' + wallet + ' отправлено ' +
                                    str(usdt_balance) +
                                    ' USDT на горячий кошелек.')
                    self.redis.set(wallet + ':txn_id', txn_id)
            elif usdt_balance > 0:
                txn_id = self.transfer_eth(
                    gas_to_eth - eth_balance,
                    wallet, 
                    self.sett['eth_wallet']['login'], 
                    self.sett['eth_wallet']['key']
                )
                self.redis.set(wallet + ':txn_id', txn_id)
                self.send_alert('На ' + wallet + ' отправлено ' + 
                    str(self.web3.fromWei(gas_to_eth - eth_balance, 'ether')) +
                    ' ETH на газ.'
                )
            else:
                self.redis.delete(key)
                self.delete_wallet_info(wallet)
                viz_login = self.redis.get(wallet + ':viz_login').decode('utf-8')
                self.send_alert(
                    'На горячий кошелек поступили USDT по сделке с ' +
                    viz_login + '.'
                )

    def create_new_address(self, login, block_num):
        """
        Создание нового адреса в сети ETH

        :param str login: логин из сети VIZ, для которого создается адрес 
        :param int block_num: номер блока, после которого закрывается обмен
        """
        keccak = sha3.keccak_256()
        priv = SigningKey.generate(curve=SECP256k1)
        pub = priv.get_verifying_key().to_string()
        keccak.update(pub)
        address = self.web3.toChecksumAddress(keccak.hexdigest()[24:])
        self.redis.set(address + ':private_key', priv.to_string().hex())
        self.redis.set(address + ':viz_login', login)
        self.redis.set(address + ':block_num', block_num)
        self.redis.set('viz:' + login, address)
        self.viz.custom(
            self.sett['viz_custom_name'], # ID custom'а 
            [
                'new_wallet', # название типа данных
                {
                    'datetime': str(datetime.utcnow()),
                    'login': login,
                    'eth_wallet': address,
                    'expiration_block_num': (block_num + 
                                            self.sett['expiration_block_count'])
                }
            ], 
            self.sett['viz_wallet']['login'], 
            self.sett['viz_wallet']['key']
        )
        self.send_alert(login + ' начал покупку. Создан ' + address + '.')

    def delete_wallet_info(self, wallet):
        """
        Удаление информации о пользовательском кошельке ETH из базы

        :param str wallet: адрес кошелька для удаления
        :returns: Результат удаления. Возвращает True в случае успешного
                  удаления. Если на кошельке остались какие-то средства,
                  возвращает False, при этом ставит метку в базе о
                  необходимости вывода остатков из этого кошелька.
        :rtype: bool
        """
        self.redis.delete(wallet + ':not_null_balance')
        usdt_balance = self.usdt_contract.functions.balanceOf(wallet).call()
        eth_balance = self.web3.eth.getBalance(self.sett['eth_wallet']['login'])
        if usdt_balance > 0:
            if (usdt_balance / (10 ** self.decimals) > float(
                                                        self.sett['usdt_fee'])
                                                       ):
                self.redis.set(wallet + ':claim', '')
                return False
            else:
                self.redis.set(wallet + ':not_null_balance', '1')
        if eth_balance > 0:
            self.redis.set(wallet + ':not_null_balance', '1')
        if usdt_balance == 0 and eth_balance == 0:
            private_key = self.redis.get(wallet + ':private_key').decode('utf-8')
            self.send_alert('Информация о кошельке ' + wallet +
                            ' с приватным ключом ' + private_key + ' удалена.')
            for key in self.redis.scan_iter(wallet + '*'):
                self.redis.delete(key)
            return True
        return False

    def get_etherium_txn(self):
        """
        Проверка активных кошельков на факт поступления USDT от пользователя. В
        случае их поступления запускает функцию обмена self.change_usdt_to_viz()
        """
        for key in self.redis.scan_iter('0x*:block_num'):
            wallet = key.decode('utf-8')
            i = wallet.find(':')
            wallet = wallet[0:i]
            balance = decimal.Decimal(
                self.usdt_contract.functions.balanceOf(wallet).call() / 
                (10 ** self.decimals)
            ).quantize(decimal.Decimal('1.' + '0'*self.decimals))
            if balance > 0:
                viz_login = self.redis.get(
                    wallet + ':viz_login'
                ).decode('utf-8')
                self.send_alert('На ' + wallet + ' поступили ' + balance +
                                ' USDT для ' + viz_login + '.')
                self.change_usdt_to_viz(balance, wallet)

    def get_exchange_rate(self):
        """
        Получение обменного курса из custom операции в сети VIZ
        """
        history = self.viz.get_account_history(
            self.sett['rate_account']['login'], 
            age=60*60*24*30, 
            type_op='custom'
        )
        for h in history:
            if h['id'] == self.sett['viz_custom_name']:
                rate = json.loads(h['json'])
                if rate[0] == 'exchanger_data':
                    self.viz_balance = decimal.Decimal(rate[1]['viz_balance'])
                    self.usdt_balance = decimal.Decimal(rate[1]['usdt_balance'])
                    self.rate = decimal.Decimal(
                        rate[1]['rate']
                    ).quantize(
                        decimal.Decimal('1.' + '0'*self.sett['rate_precision'])
                    )
                    self.sett['viz_limit_max'] = decimal.Decimal(
                        float(self.viz_balance) * 
                        (1 - (1 - self.sett['viz_limit_percent']) ** 
                         float(self.sett['exchange_ratio'])
                        )
                    ).quantize(
                        decimal.Decimal('1.' + '0'*self.sett['viz_precision'])
                    )
                    self.sett['usdt_limit_max'] = decimal.Decimal(
                        float(self.viz_balance) * 
                        self.sett['viz_limit_percent'] * float(self.rate)
                    ).quantize(
                        decimal.Decimal('1.' + '0'*self.sett['usdt_precision'])
                    )
                    return
        self.send_alert('Ошибка чтения custom операции. Скрипт остановлен.')
        sys.exit('Exchange rate not found.')

    def post_new_rate(self, viz_balance, usdt_balance):
        """
        Размещение нового курса в custom операции в сети VIZ

        :param float viz_balance: новое значение баланса фонда в VIZ
        :param float usdt_balance: новое значение баланса фонда в USDT
        """
        self.viz_balance = decimal.Decimal(
            viz_balance
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['viz_precision']))
        self.usdt_balance = decimal.Decimal(
            usdt_balance
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['usdt_precision']))
        self.rate = decimal.Decimal(
            usdt_balance / (self.sett['exchange_ratio'] * viz_balance)
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['rate_precision']))
        self.sett['viz_limit_max'] = decimal.Decimal(
            float(self.viz_balance) * 
            (1 - (1 - self.sett['viz_limit_percent']) ** 
             float(self.sett['exchange_ratio'])
            )
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['viz_precision']))
        self.sett['usdt_limit_max'] = decimal.Decimal(
            float(self.usdt_balance) * 
            ((1 + self.sett['usdt_limit_percent']) ** 
             float(1 / self.sett['exchange_ratio']) - 1
            ) + float(self.sett['usdt_fee'])
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['usdt_precision']))
        buy_viz_limit_min = decimal.Decimal(
            self.viz_balance * 
            (((self.sett['usdt_limit_min'] - self.sett['usdt_fee']) / 
              self.usdt_balance + 1) ** self.sett['exchange_ratio'] - 1
            )
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['viz_precision']))
        buy_viz_limit_max = decimal.Decimal(
            float(self.viz_balance) * self.sett['viz_limit_percent']
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['viz_precision']))
        buy_usdt_limit_min = decimal.Decimal(
            self.usdt_balance * 
            (1 - (1 - self.sett['viz_limit_min'] / self.viz_balance) ** 
             decimal.Decimal(1 / self.sett['exchange_ratio'])
            )
        ) - self.sett['usdt_fee']
        buy_usdt_limit_min = decimal.Decimal(
            buy_usdt_limit_min
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['usdt_precision']))
        buy_usdt_limit_max = decimal.Decimal(
            float(self.usdt_balance) * self.sett['usdt_limit_percent']
        ).quantize(decimal.Decimal('1.' + '0'*self.sett['usdt_precision']))
        self.viz.custom(
            self.sett['viz_custom_name'], # ID custom'а 
            [
                'exchanger_data', # название типа данных
                {
                    'datetime': str(datetime.utcnow()),
                    'viz_balance': str(self.viz_balance),
                    'viz_limit_min': str(self.sett['viz_limit_min']),
                    'viz_limit_max': str(self.sett['viz_limit_max']),
                    'buy_viz_limit_min': str(buy_viz_limit_min),
                    'buy_viz_limit_max': str(buy_viz_limit_max),
                    'usdt_balance': str(self.usdt_balance),
                    'usdt_limit_min': str(self.sett['usdt_limit_min']),
                    'usdt_limit_max': str(self.sett['usdt_limit_max']),
                    'buy_usdt_limit_min': str(buy_usdt_limit_min),
                    'buy_usdt_limit_max': str(buy_usdt_limit_max),
                    'rate': str(self.rate),
                    'exchange_ratio': str(
                        decimal.Decimal(
                            self.sett['exchange_ratio']
                        ).quantize(decimal.Decimal('1.00'))
                    ),
                    'usdt_fee': str(self.sett['usdt_fee']),
                    'eth_wallet_cost': str(self.sett['eth_wallet_cost']),
                    'viz_wallet': self.sett['viz_wallet']['login'],
                    'viz_wallet_cold': self.sett['viz_wallet_cold']['login'],
                    'eth_wallet': self.sett['eth_wallet']['login'],
                    'eth_wallet_cold': self.sett['eth_wallet_cold']['login'],
                    'bird_account': self.sett['bird_account']['login']
                }
            ], 
            self.sett['rate_account']['login'], 
            self.sett['rate_account']['key']
        )
        msg_text = ("Состояние обменника:\n" + 
            'viz_balance: ' + str(self.viz_balance) + "\n" +
            'viz_limit_min: ' + str(self.sett['viz_limit_min']) + "\n" +
            'viz_limit_max: ' + str(self.sett['viz_limit_max']) + "\n" +
            'buy_viz_limit_min: ' + str(buy_viz_limit_min) + "\n" +
            'buy_viz_limit_max: ' + str(buy_viz_limit_max) + "\n" +
            'usdt_balance: ' + str(self.usdt_balance) + "\n" +
            'usdt_limit_min: ' + str(self.sett['usdt_limit_min']) + "\n" +
            'usdt_limit_max: ' + str(self.sett['usdt_limit_max']) + "\n" +
            'buy_usdt_limit_min: ' + str(buy_usdt_limit_min) + "\n" +
            'buy_usdt_limit_max: ' + str(buy_usdt_limit_max) + "\n" +
            'rate: ' + str(self.rate) + "\n" +
            'exchange_ratio: ' + str(
                decimal.Decimal(
                    self.sett['exchange_ratio']
                ).quantize(decimal.Decimal('1.00'))
            ) + "\n" +
            'usdt_fee: ' + str(self.sett['usdt_fee']) + "\n" +
            'eth_wallet_cost: ' + str(self.sett['eth_wallet_cost']) + "\n" +
            'viz_wallet: ' + self.sett['viz_wallet']['login'] + "\n" +
            'viz_wallet_cold: ' + self.sett['viz_wallet_cold']['login'] + "\n" +
            'eth_wallet: ' + self.sett['eth_wallet']['login'] + "\n" +
            'eth_wallet_cold: ' + self.sett['eth_wallet_cold']['login'] + "\n" +
            'bird_account: ' + self.sett['bird_account']['login']
        )
        self.send_alert(msg_text)

    def post_status(self):
        """
        Custom операция в сети VIZ со статусом обменника
        """
        self.viz.custom(
            self.sett['viz_custom_name'], # ID custom'а 
            [
                'exchange_status', # название типа данных
                {
                    'datetime': str(datetime.utcnow()),
                    'status': 'OK'
                }
            ], 
            self.sett['bird_account']['login'], 
            self.sett['bird_account']['key']
        )

    def send_alert(self, message):
        date_str = str(datetime.utcnow())
        pos = date_str.find('.')
        date_str = date_str[0:pos]
        for user_id in self.sett['tg_admins']:
            self.tgbot.send_message(user_id, date_str + "\n" + message)

    def transfer_eth(self, amount, _to, _from, private_key):
        """
        Перевод ETH

        :param int amount: количество ETH для перевода
        :param str _to: адрес получателя
        :param str _from: адрес отправителя
        :param str private_key: приватный ключ отправителя
        :returns: Возвращает номер созданной транзакции в сети ETH
        :rtype: str
        """
        _to = self.web3.toChecksumAddress(_to)
        _from = self.web3.toChecksumAddress(_from)
        nonce = self.web3.eth.getTransactionCount(_from)
        gas = self.web3.eth.estimateGas(
            {'to': _to, 'from': _from, 'value': amount}
        )
        txn = {
            'gasPrice': self.web3.eth.gasPrice,
            'gas': gas,
            'to': _to,
            'value': amount,
            'nonce': nonce
        }
        signed_txn = self.web3.eth.account.sign_transaction(
            txn, 
            private_key=private_key
        )
        self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        self.send_alert('Отправлено ' + str(self.web3.fromWei(amount, 'ether'))+
                        ' ETH с ' + _from + ' на ' + _to + '. Газ: ' + gas +
                        '. Цена газа: ' + self.web3.eth.gasPrice +
                        '. Баланс отправителя до операции: ' +
                        str(self.web3.eth.getBalance(_from)) + ' ETH.')
        return self.web3.toHex(self.web3.keccak(signed_txn.rawTransaction))

    def transfer_usdt(self, amount, _to, _from, private_key, **kwargs):
        """
        Перевод USDT

        :param Decimal amount: количество USDT для перевода
        :param str _to: адрес получателя
        :param str _from: адрес отправителя
        :param str private_key: приватный ключ отправителя
        :param int eth_for_gas: количество ETH, используемого для оплаты газа.
                                По умолчанию 0
        :param bool medium_gas: стратегия по газу. Если True, то указывается
                                высокая цена газа. По-умолчанию False
        :returns: Номер созданной транзакции в сети ETH
        :rtype: str
        """
        eth_for_gas = kwargs.pop('eth_for_gas', 0)
        medium_gas = kwargs.pop('medium_gas', False)
        if medium_gas:
            self.web3.eth.setGasPriceStrategy(medium_gas_price_strategy)
        _to = self.web3.toChecksumAddress(_to)
        _from = self.web3.toChecksumAddress(_from)
        nonce = self.web3.eth.getTransactionCount(_from)
        amount *= (10 ** self.decimals)
        if eth_for_gas == 0:
            usdt_txn = self.usdt_contract.functions.transfer(
                _to, 
                int(amount)
            ).buildTransaction({'from': _from, 'chainId': 1, 'nonce': nonce})
        else:
            gas = self.usdt_contract.functions.transfer(
                _to, 
                int(amount)
            ).estimateGas({'from': _from})
            gasPrice = int(eth_for_gas / gas)
            usdt_txn = self.usdt_contract.functions.transfer(
                _to, 
                int(amount)
            ).buildTransaction({
                'from': _from,
                'chainId': 1,
                'nonce': nonce,
                'gas': gas,
                'gasPrice': gasPrice
            })
        signed_txn = self.web3.eth.account.sign_transaction(
            usdt_txn, 
            private_key=private_key
        )
        self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        self.send_alert('Отправлено ' + str(amount / (10 ** self.decimals)) +
                        ' USDT с ' + _from + ' на ' + _to + '. Газ: ' + gas +
                        '. Цена газа: ' + gasPrice +
                        '. Баланс отправителя до операции: ' +
                        str(self.web3.eth.getBalance(_from)) + ' ETH.')
        if medium_gas:
            self.web3.eth.setGasPriceStrategy(slow_gas_price_strategy)
        return self.web3.toHex(self.web3.keccak(signed_txn.rawTransaction))
