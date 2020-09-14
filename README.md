# exchanger

### Installing:

    $ git clone https://github.com/vizplus/exchanger
    $ cd exchanger/exchanger
    $ sudo apt-get install libffi-dev libssl-dev python-dev python3-dev python3-pip python3-venv
    $ pip3 install --upgrade requests
    $ python3 -m venv venv
    $ . venv/bin/activate
    $ pip install redis web3 bitshares pysha3
    $ pip install python-telegram-bot --upgrade
    $ deactivate

### Using:

    $ mv settings.json.example settings.json
    $ chmod 666 settings.json   #access for web server
    
Edit file settings.json and run initial script for post first custom operation in VIZ blockchain:

    $ venv/bin/python ./initial_scipt.py

And run exchange:

    $ venv/bin/python ./exchanger.py

### Install Telegram bot

    $ cd ..
    $ cp ./telegramBot /path/to/your/website/
    $ cd /path/to/your/website/telegramBot/
    $ composer require telegram-bot/api
    $ pecl install redis
    $ cd ./sys/inc/
    $ mv cfg.php.example cfg.php

Edit file cfg.php

Configure webhooks from telegram bot on https://your.website/telegramBot/bot.php

Add crontab task

    $ 1 * * * * /path/to/exchanger/exchanger/venv/bin/python /path/to/exchanger/exchanger/cron.py
