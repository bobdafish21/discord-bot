import discord
import os
from dotenv import load_dotenv

from src.utils.logger import handler
from src.features.weight_tracker import WeightTracker
from src.features.music_player import MusicPlayer

load_dotenv()

# set up discord client
token = os.getenv('TOKEN')

intents = discord.Intents.all()
intents.members = True
intents.presences = True
intents.message_content = True
#
client = discord.Client(intents=intents)

# set up weight tracker feature
uri = os.getenv('DB_URI')
username = os.getenv('DB_USERNAME')
password = os.getenv('DB_PASSWORD')
db = os.getenv('DB_DB')

weightTracker = WeightTracker(uri, username, password, db)
musicPlayer = MusicPlayer()

# on client creation


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

# on messages


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    await weightTracker.handle_message(message)

    await musicPlayer.handle_message(message)

# run client
client.run(token, log_handler=handler)
