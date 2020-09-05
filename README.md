# exchanger

### Installing:

    $ git clone https://github.com/vizplus/exchanger
    $ cd exchanger/exchanger
    $ sudo apt-get install libffi-dev libssl-dev python-dev python3-dev python3-pip python3-venv
    $ pip3 install --upgrade requests
    $ python3 -m venv venv
    $ . venv/bin/activate
    $ pip install redis web3 bitshares sha3
    $ pip install python-telegram-bot --upgrade
    $ deactivate
    
### Using:

    $ mv settings.json.example settings.json
    
Edit file settings.json and run initial script for post first custom operation in VIZ blockchain:

    $ venv/bin/python ./initial_scipt.py

And run exchange:

    $ venv/bin/python ./exchanger.py
