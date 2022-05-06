import discord
import asyncio
import feedparser
import time
import re

# Discord settings
BOT_TOKEN = 'OTcxMzc3MTU3OTUzNjkxNjk4.YnJneQ.r58fSM9PK4HP9so2TA34noa5774'
BOT_USER_ID = 971377157953691698
SERVER_ID = 780369833283813427
CHANNEL_ID = 780803869402988565
CHANNEL_NAME = "news"
MAX_HISTORY = 100

# RSS settings
RSS_FEED = 'http://blackspeech.ru/board/extern.php?action=feed&fid=3&type=rss'
CHECK_TIMER = 600 # time in seconds between RSS checks

# timer for repeated RSS check
class PeriodicTask:
    def __init__(self, func, time):
        self.func = func
        self.time = time
        self.is_started = False
        self._task = None

    async def start(self):
        if not self.is_started:
            self.is_started = True
            # Start task to call func periodically:
            try:
                self._task = asyncio.ensure_future(self._run())
            except asyncio.CancelledError:
                self.is_started = False
                pass

    async def stop(self):
        if self.is_started:
            self.is_started = False
            # Stop task and await it stopped:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self.is_started = False
                pass

    async def _run(self):
        while True:
            await asyncio.sleep(self.time)
            await self.func()

#repeated function to check for news
async def rss_check():
    global last_date
    global news_channel
    global message_history
    global client

    if not client.is_ready():
        return False
    
    entries = feedparser.parse(RSS_FEED).entries
    #print(entries)
    if (entries is None) or not entries:
        return False
   
    publish_date = last_date
    entries.reverse()
    for item in entries:
        publish_date = item.published_parsed
        if publish_date > last_date:
            header = "`**" + item.title + "**"
            link = item.link
            raw_html = item.summary # should return sanitized html
            full_msg = header + "\n" + raw_html + "\nNews link: " + link
            msg_list = prepare_html(full_msg)
            for msg in msg_list:
                print(msg)
                print('---')
                await news_channel.send(msg)
    last_date = publish_date 

def match_to_int(match):
    code = match.group(1)
    if code.isnumeric():
        return chr(int(code))
    else:
        return ""

#convert raw HTML to Discord markdown
def html_to_markdown(data):
    pattern = "<a href=\"(.*?)\".*?>(.*?)<\\/a>" # replace links
    result = re.sub(pattern, r"\2 (\1) ", data, flags=re.I)

    pattern = "<img .*? src=\"(.*?)\".*?>" # replace images
    result = re.sub(pattern, r" {{\1}} ", result, flags=re.I)

    pattern = "<b>(.*?)<\\/b>" # replace <B> tags
    result = re.sub(pattern, r"**\1**", result, flags=re.I)
    pattern = "<strong>(.*?)<\\/strong>" # replace <STRONG> tags
    result = re.sub(pattern, r"**\1**", result, flags=re.I)
    pattern = "/<h\\d>(.*?)<\\/h\\d>/gm" # replace header tags
    result = re.sub(pattern, r"**\1**", result, flags=re.I)
    pattern = "<cite>(.*?)<\\/cite>" # replace <CITE> tags
    result = re.sub(pattern, r"**\1**", result, flags=re.I)

    pattern = "<i>(.*?)<\\/i>" # replace <I> tags
    result = re.sub(pattern, r"*\1*", result, flags=re.I)
    pattern = "<em>(.*?)<\\/em>" # replace <EM> tags
    result = re.sub(pattern, r"*\1*", result, flags=re.I)

    pattern = "<u>(.*?)<\\/u>" # replace <U> tags
    result = re.sub(pattern, r"__\1__", result, flags=re.I)

    pattern = "<s>(.*?)<\\/s>" # replace <S> tags
    result = re.sub(pattern, r"~~\1~~", result, flags=re.I)
    pattern = "<strike>(.*?)<\\/strike>" # replace <STRIKE> tags
    result = re.sub(pattern, r"~~\1~~", result, flags=re.I)
    pattern = "<del>(.*?)<\\/del>" # replace <DEL> tags
    result = re.sub(pattern, r"~~\1~~", result, flags=re.I)

    pattern = "<li>(<p>)?(.*?)(<\\/p>)?<\\/li>" # replace <LI> tags
    result = re.sub(pattern, r"\n• \2\n", result, flags=re.I)

    pattern = "<blockquote>(<p>)?(.*?)(<\\/p>)?<\\/blockquote>" # replace <BLOCKQUOTE> tags
    result = re.sub(pattern, r"\n>>>\2\n\n", result, flags=re.I)

    pattern = "<pre>\s*(<code>)?(.*?)(<\\/code>)?\s*<\\/pre>" # replace <code> tags
    result = re.sub(pattern, r"\n```\2```\n", result, flags=re.I)

    pattern = "<p>(.*?)<\\/p>" # replace <P> tags
    result = re.sub(pattern, r"\1\n", result, flags=re.I)
    pattern = "<br\\s?/?>" # line-breaks
    result = re.sub(pattern, r"\n", result, flags=re.I)

    pattern = "</?.*?>" # all other tags
    result = re.sub(pattern, "", result, flags=re.I)

    pattern = "&#(\\d+)?;" # html-entities
    result = re.sub(pattern, match_to_int, result)
    pattern = "&quot;" # html-entities
    result = re.sub(pattern, '"', result)

    return result

# split long message in chunks of 2000 symbols, return as list
def split_message(message):
    result = message
    result_arr = []
    while len(result) > 2000:
        i = 2000
        # prevent hyperlinks from splitting
        pattern = r"\(http.*?\)"
        for match in re.finditer(pattern, result, re.I):
            if (match.start() < i) and (match.end() > i):
                i = match.start()
        if i < 2000:
            result_arr.append(result[0 : i - 1])
            result = result[i:]
            continue
        
        # now prevent image url from splitting
        pattern = r"{{http.*?}}"
        for match in re.finditer(pattern, result, re.I):
            if (match.start() < i) and (match.end() > i):
                i = match.start()
        if i < 2000:
            result_arr.append(result[0 : i - 1])
            result = result[i:]
            continue
        
        # now can split simple text at whitespace characters
        while not result[i].isspace() and (i > 0):
            i = i - 1
        if (i == 0):
            i = 2000
        else:
            i = i + 1
        result_arr.append(result[0 : i - 1])
        result = result[i:]

    result_arr.append(result)
    return result_arr

def prepare_html(html):
    return split_message(html_to_markdown(html))  

# start Discord bot
intents = discord.Intents.default()
client = discord.Client(intents=intents)
guild = None
news_channel = None
message_history = []

start_date = time.localtime()
#start_date = time.struct_time((2000,12,31, 0,0,0, 0,0,0))
last_date = start_date

rt = PeriodicTask(rss_check, CHECK_TIMER)
#rt = RepeatedTimer(CHECK_TIMER, rss_check) # initialize timer for check RSS-feed
#rss_check()

@client.event
async def on_ready():
    global message_history
    global news_channel
    global guild 
    global last_date

    print(f'We have logged in as {client.user}')
    guild = client.get_guild(SERVER_ID)
    print("Server: ", guild)
    #news_channel = client.get_channel(CHANNEL_ID)  #id of #news channel of Black Speech School server
    news_channel = discord.utils.get(guild.text_channels, name = CHANNEL_NAME)
    print("Channel: ", news_channel)

    #message_history = get_channel_history(news_channel, BOT_USER_ID, MAX_HISTORY) # check only messages by bot
    message_history = await get_channel_history(news_channel, 0, MAX_HISTORY) # check all messages (e.g. in case another bot or manual posting were used before)
    last_date = message_history[0].created_at.timetuple()
    await rt.start()
    #print("Last news:", message_history)

async def get_channel_history(channel, user_id = 0, limit = MAX_HISTORY):
    result = []
    async for message in channel.history(limit=limit):        
        if (user_id == 0) or (message.author.id == user_id):
            result.append(message)
    return result

loop = asyncio.get_event_loop()
#loop.run_until_complete(main())
client.run(BOT_TOKEN)