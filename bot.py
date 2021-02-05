#!/usr/bin/env python3
import sys
import os
import pprint
from checks import *
import logging
import subprocess
import warnings
from typing import Optional, List, Union, Any, Tuple, Callable
from functools import partial


try:  # These are mandatory.
    import discord
    from discord.ext import commands
    from discord import utils
    import asyncio
    from loguru import logger
    import peewee
    import trio_asyncio
    import trio
except ImportError:
    raise ImportError("You have some dependencies missing, please install them with pipenv install --deploy")

from database import db, Quote
from loguru_intercept import InterceptHandler


def _restart() -> None:
    try:
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception:
        pass


db.connect()
db.create_tables([Quote])


log = logging.getLogger('discord')
log.setLevel(logging.DEBUG)
log.addHandler(InterceptHandler())

config = getconf()
login = config['Login']
settings = config['Settings']
loginID = login.get('Login Token')
if not settings.getboolean('Debugging', fallback=False):
    log.setLevel(logging.INFO)
bot_version = "0.7.1"
main_channel = None
intents = discord.Intents.default()
intents.typing = False
intents.presences = True
intents.members = True

# warnings.simplefilter('ignore', category=trio_asyncio.TrioAsyncioDeprecationWarning)
# This will initialize a asyncio loop, this is supported for now, but deprecated.
bot: Optional[commands.Bot] = None

# Some shorthands for easier access.
aio_as_trio = trio_asyncio.aio_as_trio
trio_as_aio = trio_asyncio.trio_as_aio

all_commands = []
all_events: List[Callable] = []


def input_to_bool(text: str) -> Optional[bool]:
    if text.lower() in ["yes", "y", "yeah", "ja", "j"]:
        return True
    elif text.lower() in ["no", "n", "nah", "nein"]:
        return False
    else:
        return None


async def set_status_text(message: str) -> None:
    assert bot is not None
    game = discord.Game(message)
    await bot.change_presence(activity=game)


def log_startup():
    logger.info('Logged in as')
    logger.info(bot.user.name)
    logger.info(bot.user.id)
    logger.info(f"The bot prefix is {bot.command_prefix}")
    logger.info(f"Using Bot Version: {bot_version}")
    logger.info('------')
    logger.info("")
    logger.info("I am part of the following servers:")
    for guild in bot.guilds:
        logger.info(f"{guild.name}")
        logger.info(f"{guild.id}")
    logger.info("")
    # amount = 0
    # for channel in bot.get_all_channels():
    #     amount += 1
    # logger.info(f"I am in {amount} channels")
    for user in configOwner:
        logger.info(f"{user} is a Owner of this bot.")
    logger.info('------')


@trio_as_aio
async def on_ready_trio():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.to_thread.run_sync, log_startup)
        nursery.start_soon(aio_as_trio(partial(set_status_text, "waiting")))
    logger.debug("Done with setup in trio.")


async def on_ready():
    await on_ready_trio()
    logger.debug("Done with bot setup.")


all_events.append(on_ready)


async def on_guild_join(server):
    logger.success(f"I just joined the server {server.name} with the ID {server.id}")


all_events.append(on_guild_join)


async def on_guild_remove(server):
    logger.warning(f"I left the server {server.name} with the ID {server.id}")

all_events.append(on_guild_remove)


async def on_message(message):
    def check(oldmessage):
        text = oldmessage.clean_content.lower()
        agreement = ["yes", "y", "yeah", "ja", "j", "no", "n", "nah", "nein"]
        return text in agreement and oldmessage.author == message.author and oldmessage.channel == message.channel

    if message.author.bot:
        return

    text = message.clean_content.lower()
    channel = message.channel
    guild = message.guild

    if guild:
        quote = Quote.get_or_none(guild.id == Quote.guildId, text == Quote.keyword)
        if quote:
            await channel.send(quote.result)
            return

    if text == "/o/":
        await channel.send("\o\\")
    elif text == "\o\\":
        await channel.send("/o/")
    elif text == ">_>":
        await channel.send("<_<")
    elif text == "<_<":
        await channel.send(">_>")
    elif text == "-_-":
        await channel.send("I am sorry that you are annoyed. I want you to be happy!")
    elif text == "-.-":
        await channel.send("Aww don't be so upsetti, have some spaghetti!")
    elif bot.user.mentioned_in(message):
        await channel.send(f"Can I help you with anything?")
        try:
            tripped = await bot.wait_for('message', timeout=15.0, check=check)
        except TimeoutError:
            tripped = None
        # no = await bot.wait_for('message', timeout=15.0, check=nocheck)
        if tripped:
            if input_to_bool(tripped.clean_content.lower()) is None:
                return
            elif input_to_bool(tripped.clean_content.lower()):
                await channel.send(f"Okay use the {bot.command_prefix}help command to get a list of my commands!")
            elif not input_to_bool(tripped.clean_content.lower()):
                await channel.send(f"""Oh my love... Then maybe don't ping me, {message.author.mention}? ;/""")

        else:
            return
    elif text == "<_>":
        await channel.send(">_<")
    elif text == ">_<":
        await channel.send("<_>")
    elif text == "oof":
        await channel.send("https://cdn.discordapp.com/attachments/412033002072178689/422739362929704970/New_Piskel_22.gif")
    elif text == "thot":
        await channel.send("https://cdn.discordapp.com/attachments/343693498752565248/465931036384165888/tenor_1.gif")
    elif text == "|o|":
        await channel.send("/o\\")
    elif text == "XD":
        await channel.send("XC")
    elif isinstance(channel, discord.DMChannel):
        if text[0] != bot.command_prefix and main_channel is not None and channel.recipient.id in configOwner:
            await main_channel.send(message.content)

    elif channel.id == 529311873330577408:
        if text == "how are you?":
            await channel.send("I am fine.")
        elif text == "what are you doing?":
            await channel.send("Look at my playing status.")
        elif text == "where i can find rules?" or text == "where can i find the rules?":
            await channel.send("Rules are in #rules_and_rules_updates, have a nice day :D.")
        elif text == "where i can post my artworks/book?":
            await channel.send("You can post your artwork in #art_corner and your book in #book_promotes :D.")
        elif text == "where i can dump my memes and shitpost?":
            await channel.send("Meme dumpage happens in #dank_meme_depository and shitposting in #shitposting :D.")
        elif text == "how are you even responding?":
            await channel.send("My master did her magic... :eyes: ")
        elif text == "where i can find a walker #5120's book?":
            await channel.send("Here is the link: https://my.w.tt/LexRMPK1eS. Enjoy reading! :D")
    else:
        await bot.process_commands(message)


all_events.append(on_message)


@commands.command(hidden=True)
async def invite(ctx):
    await ctx.send(f"https://discordapp.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions=8")

all_commands.append(invite)


async def on_reaction(reaction, user):
    pass
    # if reaction == ":star:":
    #    await bot.send_message(channel, "test")
    
    # else:
    #    await bot.process_commands(message)


all_events.append(on_reaction)


@commands.command(hidden=True)
async def version(ctx):
    """Gives back the bot version"""
    await ctx.send(bot_version)


all_commands.append(version)


# Utility Commands
@is_in_owners()
@commands.command(hidden=True, aliases=['stop'])
async def shutdown(ctx):
    """Shuts the bot down
    Only works for the bot owner"""
    await ctx.send("Shutting down!", delete_after=3)
    await asyncio.sleep(5)
    logger.warning(f"Shutting down on request of {ctx.author.name}!")
    db.close()
    try:
        await bot.close()
        sys.exit()
    except Exception:
        sys.exit(1)


all_commands.append(shutdown)


@commands.command(hidden=True)
@is_in_owners()
async def update(ctx):
    """Updates the bot with the newest Version from GitHub
        Only works for the bot owner"""
    await ctx.send("Ok, I am updating from GitHub.")
    import pip
    #pip.main(['install', '--user', '--upgrade', 'discord.py[voice]'])
    try:
        output = subprocess.run(["git", "pull"], stdout=subprocess.PIPE)
        embed = discord.Embed()
        embed.set_author(name="Output:")
        embed.set_footer(text=output.stdout.decode('utf-8'))
        await ctx.send(embed=embed)
    except:
        await ctx.send("That didn't work for some reason...")

all_commands.append(update)


@commands.command(hidden=True, aliases=['reboot'])
@is_in_owners()
async def restart(ctx):
    """Restart the bot
    Only works for the bot owner"""
    await ctx.send("Restarting", delete_after=3)
    await asyncio.sleep(5)
    logger.warning(f"Restarting on request of {ctx.author.name}!")
    db.close()
    try:
        _restart()
    except:
        pass


all_commands.append(restart)


@commands.command(hidden=True, aliases=['setgame', 'setplaying'])
@is_in_owners()
async def gametitle(ctx, *, message: str):
    """Sets the currently playing status of the bot"""
    game = discord.Game(message)
    await bot.change_presence(activity=game)


all_commands.append(gametitle)


@commands.command()
async def ping(ctx):
    """Checks the ping of the bot"""
    m = await ctx.send("Ping?")
    await m.edit(f"Pong, Latency is {m.timestamp - ctx.message.timestamp}.")


all_commands.append(ping)


@commands.command(hidden=True)
async def say(ctx, *, message: str):
    """Repeats what you said"""
    await ctx.send(message)


all_commands.append(say)


@commands.command(hidden=True)
@commands.has_permissions(manage_messages=True)
async def say2(ctx, *, message: str):
    """Repeats what you said and removes it"""
    await ctx.message.delete()
    await ctx.send(message)


all_commands.append(say2)


@commands.command(hidden=True)
@is_in_owners()
async def setchannel(ctx):
    """Sets the channel for PM messaging"""
    global main_channel
    main_channel = ctx.channel
    await ctx.message.delete()
    await ctx.send("Set the default channel to this channel.")


all_commands.append(setchannel)


@commands.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx):
    """Kicks the specified User"""
    user = ctx.message.mentions[0]
    if user is None:
        await ctx.send("No user was specified.")
        return
    try:
        await ctx.kick(user)
        await ctx.send("The user has been kicked from the server.")
    except:
        await ctx.send("I couldn't kick that user.")


all_commands.append(kick)


@commands.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx):
    """Bans the specified User"""
    user = ctx.message.mentions[0]
    if user is None:
        await ctx.send("No user was specified.")
        return
    try:
        await ctx.ban(user)
        await ctx.send("The user has been banned from the server.")
    except:
        await ctx.send("I couldn't ban that user.")


all_commands.append(ban)


@commands.command()
async def info(ctx):
    """Gives some info about the bot"""
    message = f"""📢
    Hello, I'm S.A.I.L, a Discord bot made for simple usage by Gr3ta a.k.a Gh0st4rt1st.
    *~Date when I was created: 2017-10-15.
    *~I was ported to Python by gfrewqpoiu on 2017-12-22.
    *~To see what commands I can perform, use `{bot.command_prefix}help`.
    *~My version currently is: {bot_version} .
    *~I was made in: 
    Country: Lithuania;
    City/Town: Biržai and Klaipėda;
    *~Porting from js to py was done in:
    Country: Germany;
    City/Town: Munich. 
    I am currently being rewritten to work in the new discordpy version.
    
    Fun facts:
    1.)S.A.I.L name comes from Starbound game's AI character S.A.I.L;
    2.)S.A.I.L stands for Ship-based Artificial Intelligence Lattice."""

    await ctx.send(message)


all_commands.append(info)


@commands.command(aliases=['prune', 'delmsgs'])
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    """Removes the given amount of messages from the given channel."""
    try:
        await ctx.channel.purge(limit=(amount+1))
    except discord.Forbidden:
        await ctx.send("I couldn't do that because of missing permissions...")


all_commands.append(purge)


@commands.command(hidden=False)
async def tf2(ctx):
    """Funny Video"""
    await ctx.send("https://www.youtube.com/watch?v=r-u4rA_yZTA")


all_commands.append(tf2)


@commands.command(hidden=False)
async def an(ctx):
    """A command giving link to A->N website"""
    await ctx.send(""">R3DACT3D
    >L1NK_R3M0V3D? = yes""")


all_commands.append(an)


@commands.command(hidden=False)
async def walkersjoin(ctx):
    """A link to 24/7 Walker's Radio on youtube"""
    await ctx.send("https://www.youtube.com/watch?v=ruOlyWdUMSw")


all_commands.append(walkersjoin)


@commands.command()
async def changes(ctx):
    """A command to show what has been added and/or removed from bot"""
    await ctx.send("""The changes:
    **NOTE**: Kevin, staph leaving sentences in quotation marks in code without fullstop at end of sentences. -_- ~ Gh0st4rt1st.
    **FIXED & REMOVED**: Two useless commands were removed due to them no longer being needed.
    0.6.1 -> **FIXED**: The purge command works again and so does the setplaying command
    0.6.0 -> **ADDED:** Quote Sytem using a Database.
    0.5.0 -> **CHANGED:** Rewrite for a new version of Discord.py.
    0.4.0 -> **ADDED:** More Utility Commands.
    0.3.0 -> **FIXED:** Broken permissions work now.
    0.2.0 -> **ADDED:** 
    *~tf2 & an - link commands; 
    *~extra reactions;
    *~change - updates command showing what was added/removed from bot;
    *~Special reaction w/ user tag.""")


all_commands.append(changes)


@commands.command()
async def upcoming(ctx):
    """Previews upcoming plans if there are any"""
    await ctx.send("""This is upcoming:```All secret.```""")


all_commands.append(upcoming)


@commands.command(hidden=True)
async def FreeNitro(ctx):
    """Free Discord Nitro"""
    await ctx.send(f"""{ctx.author.mention} >HAPPY_EASTER
    >HERE'S YOUR NITRO SUBSCRIPTION:
    <https://is.gd/GetFreeNitro>
    >YOURS: Gh0st4rt1st_x0x0""")


all_commands.append(FreeNitro)


@commands.command(hidden=False)
async def probe(ctx):
    """Use this command to check for open ports (ps. this is first step command of Easter egg)"""
    await ctx.send(""">1_OPEN_PORT_HAD_BEEN_FOUND
    >USE_ssh_TO_CRACK_IT""")


all_commands.append(probe)


@commands.command(hidden=True)
async def ssh(ctx):
    """This command hacks the port"""
    await ctx.send(""">CRACKING_SUCCESSFUL
    >USE_porthack_TO_GAIN_ACCESS""")


all_commands.append(ssh)


@commands.command(hidden=True)
async def porthack(ctx):
    """This command lets you inside"""
    await ctx.send(""">HACK_SUCCESSFUL
    >USE_ls_TO_ACCESS_FILES""")


all_commands.append(porthack)


@commands.command(hidden=True)
async def ls(ctx):
    """This command scans bot and lets you into files of bot"""
    await ctx.send(""">1_DIRECTORY_FOUND
    >DIRECTORY:home
    >USE_cdhome_TO_ACCESS_FILES""")


all_commands.append(ls)


@commands.command(hidden=True)
async def cdhome(ctx):
    """This command scans existing folders of bot and let's you access folder"""
    await ctx.send(""">ONE_DIRECTORY_FOUND
    >File: README.txt
    >USE_catREADME_TO_VIEW_FILE_CONTENTS""")


all_commands.append(cdhome)


@commands.command(hidden=True)
async def catREADME(ctx):
    """This command shows what's inside of file"""
    await ctx.send("""VIEWING_File:README.txt
    >Congratz! You found Hacknet Easter egg;
    >The Easter egg code was written by: Gh0st4rt1st a.k.a Gr3ta;
    >Code was edited by: gfrewqpoiu;
    >The Easter egg code is based on Hacknet game;
    >Have a nice day! *Gh0st4rt1st* *x0x0* """)


all_commands.append(catREADME)


@commands.command(hidden=True)
async def annoyeveryone(ctx):
    for i in range(10):
        await ctx.send("Don't you like it when your cat goes: Meow. Meow? Meow! Meow. Meow Meow. Meow? Meow! Meow. Meow Meow? Meow! Meow. Meow",  tts=True)
        await asyncio.sleep(30)


all_commands.append(annoyeveryone)


@commands.command(hidden=True)
async def tts(ctx):
    for i in range(10):
        await ctx.send("Don't you just hate it when your cat wakes you up like this? Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow.", tts=True)
        await asyncio.sleep(30)


all_commands.append(tts)


@commands.command(aliases=['addq'])
async def addquote(ctx, keyword: str, *, quotetext: str):
    """Adds a quote to the database
    Specify the keword in "" if it has spaces in it.
    Like this: addquote "key message" Reacting Text"""
    quote = Quote(guildId=ctx.message.guild.id, keyword=keyword.lower(), result=quotetext, authorId=ctx.author.id)
    quote.save()
    await ctx.send("I saved the quote.")


all_commands.append(addquote)


@commands.command(hidden=True, aliases=['delq', 'delquote'])
@commands.has_permissions(manage_messages=True)
async def deletequote(ctx, keyword: str):
    """Deletes the quote with the given keyword
    If the keyword has spaces in it, it must be quoted like this:
    deletequote "Keyword with spaces" """
    quote = Quote.get_or_none(Quote.guildId == ctx.guild.id, Quote.keyword == keyword.lower())
    if quote:
        quote.delete_instance()
        await ctx.send("The quote was deleted.")
    else:
        await ctx.send("I could not find the quote.")


all_commands.append(deletequote)


@commands.command(aliases=['liqu'])
async def listquotes(ctx):
    """Lists all quotes on the current server"""
    result = ""
    for quote in Quote.select(Quote.keyword).where(ctx.guild.id == Quote.guildId):
        result=result+str(quote.keyword)+"; "
    if result:
        await ctx.send(result)
    else:
        await ctx.send("I couldn't find any quotes on this server.")


all_commands.append(listquotes)


@commands.command(hidden=True, aliases=['eval'])
async def evaluate(ctx, *, message:str):
    """Evaluates an arbitrary python expression"""
    if (ctx.message.author.id != 167311142744489984):
        await ctx.send(""""This command is only for gfrewqpoiu.
        It is meant for testing purposes only.""")
        return
    embed = discord.Embed()
    embed.set_author(name="Result")
    embed.set_footer(text=eval(message))
    await ctx.send(embed=embed)


all_commands.append(evaluate)


@commands.command(hidden=True, aliases=['leaveserver, leave'])
@is_in_owners()
async def leaveguild(ctx, id: int):
    guild = bot.get_guild(id)
    await guild.leave()
    await ctx.send("I left that Guild.")


all_commands.append(leaveguild)


@commands.command(hidden=False)
async def glitch(ctx):
    "The second Easter Egg"
    await ctx.send("""Who created Walkers Join book?
    a ME;
    b FART;
    c Caro and Helryon;
    Type answer as ``.letter``""")


all_commands.append(glitch)


@commands.command(hidden=True)
async def c(ctx):
    "Answer"
    await ctx.send("Correct, Walkers Join book was created by Caro and Helryon")


all_commands.append(c)


@commands.command(hidden=True)
async def a(ctx):
    "Answer"
    await ctx.send("Wrong...")


all_commands.append(a)


@commands.command(hidden=True)
async def b(ctx):
    "Answer"
    await ctx.send("Wrong...")


all_commands.append(b)


@aio_as_trio
async def setup_bot():
    global bot
    bot = commands.Bot(command_prefix=settings.get('prefix', '.'),
                       description=settings.get('Bot Description', 'S.A.I.L'), pm_help=True, intents=intents)

    for event in all_events:
        bot.add_listener(event)

    for command in all_commands:
        bot.add_command(command)


async def main() -> None:
    async with trio_asyncio.open_loop() as loop:
        await setup_bot()
        assert bot is not None
        try:
            await aio_as_trio(partial(bot.start, loginID, reconnect=True))
        except KeyboardInterrupt:
            await aio_as_trio(bot.logout)


try:
    trio.run(main)
except Exception as e:
    logger.error(e)
    raise ValueError(
        "Couldn't log in with the given credentials, please check those in config.ini"
        " and your connection and try again!")
