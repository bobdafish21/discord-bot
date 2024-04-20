import discord
from discord import Message, TextChannel, VoiceClient
from youtube_dl import YoutubeDL
import asyncio
from async_timeout import timeout
import itertools

ytdlopts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

ffmpegopts = {
    'before_options': '-nostdin',
    'options': '-vn'
}


def format_time(timeSeconds: int):
    SECONDS_IN_HOUR = 60 * 60
    SECONDS_IN_MINUTE = 60
    hours = 0
    mins = 0
    seconds = 0

    hours = timeSeconds // SECONDS_IN_HOUR
    mins = int((timeSeconds % SECONDS_IN_HOUR) / SECONDS_IN_MINUTE)
    seconds = timeSeconds - (hours * SECONDS_IN_HOUR) - \
        (mins * SECONDS_IN_MINUTE)

    hours = str(hours).rjust(2, '0')
    mins = str(mins).rjust(2, '0')
    seconds = str(seconds).rjust(2, '0')
    if hours != '00':
        return f'{hours}:{mins}:{seconds}'
    else:
        return f'{mins}:{seconds}'


class QueueItem:

    def __init__(self, youtube_url: str, title: str, duration: int, requester: str):
        self.youtube_url = youtube_url
        self.title = title
        self.duration = duration
        self.requester = requester


class MusicPlayerLooper:
    NO_SONG_TIMEOUT = 60 * 5
    IS_PLAYING = True

    def __init__(self, textChannel: TextChannel, voiceClient: VoiceClient, volumne: float = 0.5):
        self.queue = asyncio.Queue()
        self.viewableQueue = []
        self.next = asyncio.Event()
        self.ytdl = YoutubeDL(ytdlopts)
        self.textChannel = textChannel
        self.voiceClient = voiceClient
        self.volume = volumne
        self.now_playing = None

    def hanle_callback(self, error):
        self.next.set
        print(error)

    async def prepare_url(self, url: str):
        data = self.ytdl.extract_info(url, download=False)
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(data['url'], before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn"))

    async def add_song_to_queue(self, message: Message):
        requester = message.author.global_name
        search = message.content.lstrip('play ')

        try:
            data = self.ytdl.extract_info(url=search, download=False)
            if 'entries' in data:
                # take first item from a playlist
                data = data['entries'][0]
            item = QueueItem(data['webpage_url'],
                             data['title'], data['duration'], requester)
            await self.queue.put(item)
            self.viewableQueue.append(item)
            return await message.channel.send(f'Added "{data['title']}" to the queue: position {
                self.queue.qsize()}')
        except Exception as e:
            print(e)
            return await message.channel.send(f'Could not add song "{
                search}" to the queue')

    async def pause_song(self, message: Message):
        self.textChannel = message.channel
        if not self.voiceClient or not self.voiceClient.is_playing():
            await self.textChannel.send('Cannot pause, nothing is playing')
        elif self.voiceClient.is_paused():
            return
        else:
            self.voiceClient.pause()
            await self.textChannel.send('Music has been paused')

    async def unpause_song(self, message: Message):
        self.textChannel = message.channel
        if not self.voiceClient or not self.voiceClient.is_connected():
            await self.textChannel.send('Cannot unpause, nothing is playing')
        elif not self.voiceClient.is_paused():
            return
        else:
            self.voiceClient.resume()
            await self.textChannel.send('Resuming music')

    async def skip_song(self, message: Message):
        self.textChannel = message.channel
        if not self.voiceClient or not self.voiceClient.is_connected() or not self.voiceClient.is_playing():
            await self.textChannel.send('Cannot skip, nothing is playing')
        else:
            self.voiceClient.stop()
            await self.textChannel.send(f'Skipping song {self.now_playing.title}')

    async def queue_list(self, message: Message):
        print('hihihihi')
        self.textChannel = message.channel
        if not self.voiceClient or not self.voiceClient.is_playing():
            await self.textChannel.send('Nothing is playing')
        elif self.queue.empty():
            await self.textChannel.send('Nothing is queue')
        else:
            fmt = '\n'.join([f'{i}. {song.title}: {
                            format_time(song.duration)}' for i, song in enumerate(self.viewableQueue)])
            embed = discord.Embed(
                title=f'Currently playing: {self.now_playing.title}', description=fmt)
            await self.textChannel.send(embed=embed)

    async def shuffle(self, message: Message):
        pass

    async def leave(self, message: Message):
        pass

    async def now_playing(self, message: Message):
        pass

    async def volume(self, message: Message):
        pass

    async def player_loop(self):
        while self.IS_PLAYING:
            self.next.clear()
            try:
                async with timeout(self.NO_SONG_TIMEOUT):
                    next_queue_item = await self.queue.get()
                    self.viewableQueue.pop(0)
            except:
                await self.textChannel.send(
                    'Leaving because of inactivity. Bye bye :3')
                return

            try:
                source = await self.prepare_url(next_queue_item.youtube_url)
            except Exception as e:
                print(e)
                await self.textChannel.send(f'Error playing song "{next_queue_item.title}"')
            source.volume = self.volume
            self.voiceClient.play(
                source, after=lambda _: self.next.set())
            self.now_playing = next_queue_item
            await self.textChannel.send(f'Now playing {self.now_playing.title}: {format_time(self.now_playing.duration)} requested by {self.now_playing.requester}')

            await self.next.wait()
            source.cleanup()
            self.now_playing = None


class MusicPlayer:
    def __init__(self):
        self.looper = None

    async def make_looper(self, message: Message):
        if message.author.voice:
            voiceChannel = message.author.voice.channel
            textChannel = message.channel
            voiceClient = await voiceChannel.connect()
            self.looper = MusicPlayerLooper(textChannel, voiceClient)
            await textChannel.send('Joining voice chat')
            await self.looper.add_song_to_queue(message)
            await self.looper.player_loop()
            await voiceClient.disconnect()
            del self.looper
            self.looper = None
        else:
            return await message.channel.send('Join a voice channel first to use music player feature')

    async def play_song(self, message: Message):
        if not self.looper:
            await self.make_looper(message)
        else:
            await self.looper.add_song_to_queue(message)

    async def skip_song(self, message: Message):
        pass

    async def pause_song(self, message: Message):
        pass

    async def unpause_song(self, message: Message):
        pass

    async def now_playing(self, message: Message):
        pass

    async def shuffle_queue(self, message: Message):
        pass

    async def leave(self, message: Message):

        pass

    async def handle_message(self, message: Message):
        if message.content.lower().startswith('play '):
            await self.play_song(message)
        if message.content.lower().startswith('pause'):
            if self.looper:
                await self.looper.pause_song(message)
        if message.content.lower().startswith('unpause'):
            if self.looper:
                await self.looper.unpause_song(message)
        if message.content.lower().startswith('resume'):
            if self.looper:
                await self.looper.unpause_song(message)
        if message.content.lower().startswith('skip'):
            if self.looper:
                await self.looper.skip_song(message)
        if message.content.lower().startswith('stop'):
            if self.looper:
                self.looper.voiceClient.disconnect()
                del self.looper
                self.looper = None
                await message.channel.send('Oki bye bye 😭')
        if message.content.lower().startswith('leave'):
            if self.looper:
                self.looper.voiceClient.disconnect()
                del self.looper
                self.looper = None
                await message.channel.send('Oki bye bye 😭')
        if message.content.lower().startswith('queue'):
            if self.looper:
                await self.looper.queue_list(message)
