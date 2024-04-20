from pymongo import MongoClient
from discord import Message
from datetime import datetime, timedelta
import io
import pandas as pd
import matplotlib.pyplot as plt
import urllib.parse
import math
import discord
from matplotlib.font_manager import FontProperties
import matplotlib.dates as mdates
from pytz import timezone


# TODO add logging to this class
# TODO add weighted average line and logarythmic future estimation curve

class WeightTracker:
    _MIN_WEIGHT = 40
    _MAX_WEIGHT = 130
    _MAX_DAILY_WEIGHT_DELTA = 5

    def __init__(self, uri: str, username: str, password: str, database: str):
        """Initialises Class with database connection"""
        new_uri = uri.replace('<username>', urllib.parse.quote(username)).replace(
            '<password>',  urllib.parse.quote(password))

        self.client = MongoClient(new_uri)
        self.db = self.client[database]
        self.weights_collection = self.db.weights

    def _stringToColour(self, string: str) -> str:
        """Hashes a string into a valid hex colour"""
        hash = 0
        for cha in string:
            hash = ord(cha) + ((hash << 5) - hash)
        colour = '#'
        for i in range(3):
            value = hash >> (i * 8) & 0xff
            colour += hex(value)[2:].zfill(2)
        return colour

    def _add_weight(self, date: str, user: str, weight: float):
        """Adds a users weight for a given date to the database"""
        if self.weights_collection.find_one({'date': date}) == None:
            self.weights_collection.insert_one({'date': date, user: weight})
        else:
            self.weights_collection.update_one(
                {'date': date}, {'$set': {user: weight}})

    def _get_weights(self):
        """Gets all recorded weights from the database into an dataframe"""
        results = self.weights_collection.find({})
        results_array = []
        for row in results:
            results_array.append(row)
        df = pd.DataFrame(results_array)
        df = df.drop("_id", axis=1)
        df = df.set_index('date').sort_index()
        return df

    def _get_graph(self, members: list[str]):
        """Takes a list of Global Usernames and returns a buffer of a graph of their weights"""
        buff = io.BytesIO()
        df = self._get_weights()

        # plt.get_cmap('jet')
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
        plt.gca().xaxis.set_major_locator(mdates.DayLocator())
        name_list = []
        for member in df.columns:
            if member in members:
                member_data = df[member]
                member_data = member_data.values.tolist()
                axis_data = df.index.values.tolist()
                y_axis = [
                    datum for datum in member_data if not math.isnan(datum)]
                x_axis = [datetime.strptime(axis_data[i], '%Y-%m-%d').date()
                          for i, datum in enumerate(member_data) if not math.isnan(datum)]
                colour = self._stringToColour(member)
                plt.plot(x_axis, y_axis, c=colour,
                         linewidth=2, markersize=0, alpha=1)
                name_list.append(member)

        # Create graph
        plt.gcf().autofmt_xdate()
        fontP = FontProperties()
        fontP.set_size('xx-small')
        plt.legend(name_list, loc='upper left', bbox_to_anchor=(
            0.95, 1), frameon=False, prop=fontP)
        plt.gcf().savefig(buff, format="png")
        buff.seek(0)
        plt.clf()
        plt.cla()

        return buff

    async def _record_weight(self, message: Message):
        """Takes a message and verifies and records the given weight information to the database,
        graphing the new data at the end"""
        text = message.content
        msg_date = datetime.date(message.created_at.astimezone(
            timezone('Australia/Melbourne')))
        author = str(message.author.global_name)
        weight = 0.0

        # try convert weight string to float
        try:
            weight = float(text.split()[1].strip('abcdefghijklmnopqrstuvwxyz'))
        except:
            return await message.channel.send('Recording didn\'t work. Try again, correct format example given below:\nrecord: 38.2')

        # check for weight extremes
        if not (self._MIN_WEIGHT < weight < self._MAX_WEIGHT):
            return await message.channel.send('Impossible. You\'re a liar. Bitch. Fuck you.')

        # check for too large of weight change
        try:
            yday = (msg_date - timedelta(days=1)).__str__()
            yesterday_data = self.weights_collection.find_one({'date': yday})
            if yesterday_data != None and abs(yesterday_data[author] - weight) > self._MAX_DAILY_WEIGHT_DELTA:
                return await message.channel.send("Impossible. You're a liar. Bitch. Fuck you.")
        except:
            pass

        # check if message has update date
        try:
            date = ''.join(text.split(' ', 2)[2])
            update_date = None
            if date[0:4].isnumeric():
                date_split = date.split(date[4])
                update_date = datetime(int(date_split[0]), int(
                    date_split[1]), int(date_split[2])).date()
            else:
                date_split = date.split(date[2])
                update_date = datetime(int(date_split[2]), int(
                    date_split[1]), int(date_split[0])).date()
            if update_date > msg_date:
                return await message.channel.send("Can't update future dates")
            self._add_weight(update_date.__str__(), author, weight)
            await message.channel.send(f'Updated date {update_date} with weight {weight}')
            buff = self._get_graph([author])
            return await message.channel.send(file=discord.File(buff, "plot.png"))
        except:
            pass

        self._add_weight(msg_date.__str__(), author, weight)
        await message.channel.send(f'Updated date {msg_date} with weight {weight}')
        buff = self._get_graph([author])
        return await message.channel.send(file=discord.File(buff, "plot.png"))

    async def _show_graphs(self, message: Message):
        """Show graph for all mentioned members or the author if no mentions"""
        members = []
        if message.mentions:
            for member in message.mentions:
                members.append(str(member.global_name))
        else:
            members.append(message.author.global_name)

        buff = self._get_graph(members)
        await message.channel.send(file=discord.File(buff, "plot.png"))
        plt.clf()
        plt.cla()

    async def handle_message(self, message: Message):
        """Handle message for all weight tracker commands"""
        if message.content.lower().startswith('record '):
            await self._record_weight(message)
        if message.content.lower().startswith('graph'):
            await self._show_graphs(message)
