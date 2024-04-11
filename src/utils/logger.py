import logging
from datetime import datetime

_now = datetime.now()

_filename = f'./logs/{_now.strftime('%Y-%m-%dT%H%M%S')}.log'

handler = logging.FileHandler(filename=_filename, encoding='utf-8', mode='w')