from pymongo import MongoClient
from discord import Message
from datetime import datetime, timedelta, date
import urllib.parse

class WeightTracker:
    MIN_WEIGHT = 40
    MAX_WEIGHT = 130
    MAX_DAILY_WEIGHT_DELTA = 5

    # initialise class with db connection
    def __init__(self, uri: str, username: str, password: str, database: str):
        new_uri = uri.replace('<username>', urllib.parse.quote(username)).replace('<password>',  urllib.parse.quote(password))
        print(new_uri)

        self.client = MongoClient(new_uri)
        self.db = self.client[database]
        self.weights_collection = self.db.weights

    def _add_weight(self, date, user, weight):
        print(date, weight, user)
        if self.weights_collection.find_one({'date': date}) == None:
            self.weights_collection.insert_one({'date': date, user: weight})
        else:
            self.weights_collection.update_one({'date': date}, {'$set': {user: weight}})

    def get_weights(self):
        results = self.weights_collection.find({})
        results_array = []
        for row in results:
            results_array.append(row)
        return results_array
    
    async def __record_weight(self, message: Message):
        text = message.content
        msg_date = datetime.date(message.created_at)
        author = str(message.author)
        weight = 0.0

        # try convert weight string to float
        try: weight = float(text.split()[1].strip('abcdefghijklmnopqrstuvwxyz'))
        except: return await message.channel.send('Recording didn\'t work. Try again, correct format example given below:\nrecord: 38.2')
        
        # check for weight extremes
        if not (self.MIN_WEIGHT < weight < self.MAX_WEIGHT):
                return await message.channel.send('Impossible. You\'re a liar. Bitch. Fuck you.')
        
        # check for too large of weight change
        try:
            yesterday_data = self.weights_collection.find_one({'date': msg_date - timedelta(days=1)})
            if yesterday_data != None and abs(yesterday_data[author] - weight) > self.MAX_DAILY_WEIGHT_DELTA:
                return await message.channel.send("Impossible. You're a liar. Bitch. Fuck you.")
        except:
            pass

        # check if message has update date
        try:
            date_split = text.split()[2].split('/')
            update_date = date(date_split[0], date_split[1], date_split[2])
            if update_date > msg_date:
                return await message.channel.send("Can't update future dates")
            self._add_weight(update_date.__str__(),author , weight)
            return await message.channel.send(f'Updated date {update_date} with weight {weight}')
        except:
            pass

        self._add_weight(msg_date.__str__(),author , weight)
        return await message.channel.send(f'Updated date {msg_date} with weight {weight}')

    async def handle_message(self, message: Message):
        text = message.content
        date = datetime.date(message.created_at)
        author = str(message.author)
        if message.content.startswith('record'):
           await self.__record_weight(message)
