#!/usr/bin/env python3
import sys
import os
import pprint
import asyncio
from checks import *
import logging
import subprocess
import warnings
from typing import Optional, List, Union, Any, Tuple, Callable, Dict
from functools import partial
from enum import IntEnum
from datetime import timedelta
import string

try:  # These are mandatory.
    import discord
    from discord.ext import commands
    from discord import utils
    import asyncio
    from loguru import logger
    import peewee
    import trio_asyncio
    import trio
    import trio_util
except ImportError:
    raise ImportError(
        "You have some dependencies missing, please install them with pipenv install --deploy"
    )

from database import db, Quote
from loguru_intercept import InterceptHandler


def _restart() -> None:
    try:
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception:
        pass


log = logging.getLogger("discord")
log.setLevel(logging.DEBUG)
log.addHandler(InterceptHandler())

config = getconf()
login = config["Login"]
settings = config["Settings"]
loginID = login.get("Login Token")
debugging = settings.getboolean("Debugging", fallback=False)
logger.remove()
if not debugging:
    log.setLevel(logging.INFO)
    logger.add(
        sys.stderr,
        level="INFO",
        enqueue=True,
        diagnose=False,
        colorize=True,
        backtrace=False,
    )
else:
    logger.add(
        sys.stderr,
        level="DEBUG",
        enqueue=True,
        diagnose=True,
        colorize=True,
        backtrace=True,
    )
log_channel_id: Optional[int] = int(settings.get("Logging Channel", fallback="0"))
if log_channel_id == 0:
    log_channel_id = None
bot_version: str = "0.8.0"
main_channel: Optional[discord.TextChannel] = None
log_channel: Optional[discord.TextChannel] = None
intents = discord.Intents.default()
intents.typing = False
intents.presences = (
    True  # If we want to track presence, we need this privileged intent.
)
intents.members = True  # This allows us to get all members of a guild. Also privileged.
punctuation = string.punctuation  # A list of all punctuation characters

bot: Optional[commands.Bot] = None

# Some shorthands for easier access.
aio_as_trio = trio_asyncio.aio_as_trio
trio_as_aio = trio_asyncio.trio_as_aio
# What is trio_asyncio? That makes it possible to use functions from the libraries asyncio and trio together.
# The main discord code is written for asyncio but trio is generally easier to program for and has saner defaults.
# For example, it doesn't just ignore errors and you can't just call concurrent functions willy nilly.
# That is why for everything new that isn't just sending messages etc, I am using trio.
# All bot functions and events are called using asyncIO by default, so if we want to jump to trio, we need to use
# trio_as_aio. If we want to jump from trio to asyncio, we use aio_as_trio.
# We also use convention to name trio functions, that don't have decorator, as function_trio.
Context = commands.Context

all_commands: List[commands.Command] = []
all_events: List[Callable] = []

global_quotes: Dict[str, str] = {
    "/o/": "\\o\\",
    "\\o\\": "/o/",
    ">_>": "<_<",
    "<_<": ">_>",
    "-_-": "I am sorry that you are annoyed. I want you to be happy!",
    "-.-": "Aww don't be so upsetti, have some spaghetti!",
    "<_>": ">_<",
    ">_<": "<_>",
    "oof": "https://cdn.discordapp.com/attachments/412033002072178689/422739362929704970/New_Piskel_22.gif",
    "thot": "https://cdn.discordapp.com/attachments/343693498752565248/465931036384165888/tenor_1.gif",
    "|o|": "/o\\",
    "XD": "XC",
}


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


def log_startup() -> None:
    assert bot is not None
    logger.info("Logged in as")
    logger.info(bot.user.name)
    logger.info(bot.user.id)
    logger.info(f"The bot prefix is {bot.command_prefix}")
    logger.info(f"Using Bot Version: {bot_version}")
    logger.info("------")
    logger.info("")
    logger.info("I am part of the following servers:")
    for guild in bot.guilds:
        logger.info(f"{guild.name}")
        logger.info(f"{guild.id}")
    logger.info("")
    for user in configOwner:
        logger.info(f"{user} is a Owner of this bot.")
    logger.info("------")


async def _add_global_quote_trio(
    keyword: str, text: str, author: Optional[discord.User] = None
) -> None:
    keyword = keyword.lower()
    quote = await trio.to_thread.run_sync(
        Quote.get_or_none, -1 == Quote.guildId, keyword == Quote.keyword
    )
    if quote is None:
        logger.info(
            f"Adding global quote {keyword} with text {text} because it is not in the database."
        )
        quote = Quote(guildId=-1, keyword=keyword, result=text, authorId=-1)
        if author is not None:
            quote.authorId = author.id
        await trio.to_thread.run_sync(quote.save)


async def log_to_channel(message: str):
    global log_channel
    if log_channel is not None:
        try:
            await log_channel.send(message)
        except RuntimeError:
            # This happens if the channel gets closed but the bot wants to log something
            log_channel = None
            pass


@aio_as_trio
async def setup_channel_logger() -> Optional[int]:
    format_str = "```{time: HH:mm:ss.SSS} | <level>{level: <8}</level> | {function}:{line} - <level>{message}</level>```"
    if log_channel is not None:
        logger.info(f"Setting up logging to {log_channel.name}")
        return logger.add(
            log_to_channel,
            level="INFO",
            format=format_str,
            colorize=False,
            backtrace=False,
            diagnose=False,
            enqueue=True,
        )
    return None


@aio_as_trio
async def setup_log_channel(nursery: trio.Nursery) -> None:
    global log_channel
    if log_channel_id is not None:
        assert bot is not None
        log_channel = bot.get_channel(log_channel_id)
        if log_channel is not None:
            logger.debug("Found bot log channel.")
            nursery.start_soon(setup_channel_logger)


async def on_ready_trio() -> None:
    async with trio.open_nursery() as nursery:
        nursery.start_soon(trio.to_thread.run_sync, log_startup)
        nursery.start_soon(aio_as_trio(partial(set_status_text, "waiting")))
        for keyword, text in global_quotes.items():
            nursery.start_soon(_add_global_quote_trio, keyword, text, None)
        nursery.start_soon(setup_log_channel, nursery)
    logger.debug("Done with setup in trio.")


async def on_ready() -> None:
    await trio_as_aio(on_ready_trio)()
    logger.debug("Done with bot setup.")


all_events.append(on_ready)


async def on_guild_join(server: discord.Guild) -> None:
    logger.success(f"I just joined the server {server.name} with the ID {server.id}")


all_events.append(on_guild_join)


async def on_guild_remove(server: discord.Guild) -> None:
    global log_channel
    if log_channel is not None:
        if log_channel.guild == server:
            log_channel = None
            logger.warning("Removed the server used for logging, turned it off.")
    logger.warning(f"I left the server {server.name} with the ID {server.id}")


all_events.append(on_guild_remove)


async def _get_quote_trio(guild: discord.Guild, text: str) -> Optional[str]:
    quote = await trio.to_thread.run_sync(
        Quote.get_or_none, guild.id == Quote.guildId, text.lower() == Quote.keyword
    )
    if quote:
        return quote.result
    else:
        quote = await trio.to_thread.run_sync(
            Quote.get_or_none, -1 == Quote.guildId, text.lower() == Quote.keyword
        )
        if quote:
            return quote.result
    return None


async def on_message(message: discord.Message) -> None:
    assert bot is not None

    if message.author.bot:
        return

    logger.debug(f"Processing Message with ID {message.id}")

    def check(oldmessage) -> bool:
        text = oldmessage.clean_content.lower()
        agreement = ["yes", "y", "yeah", "ja", "j", "no", "n", "nah", "nein"]
        return (
            text in agreement
            and oldmessage.author == message.author
            and oldmessage.channel == message.channel
        )

    text: str = message.clean_content.lower()
    channel: Union[discord.TextChannel, discord.DMChannel] = message.channel
    guild: Optional[discord.Guild] = message.guild

    if guild:
        quote = await trio_as_aio(_get_quote_trio)(guild, text)
        if quote:
            await channel.send(quote)
            return

    if bot.user.mentioned_in(message):
        await channel.send(f"Can I help you with anything?")
        try:
            tripped = await bot.wait_for("message", timeout=15.0, check=check)
            if input_to_bool(tripped.clean_content.lower()):
                await channel.send(
                    f"Okay use the {bot.command_prefix}help command to get a list of my commands!"
                )
            else:
                await channel.send(
                    f"""Oh my love... Then maybe don't ping me, {message.author.mention}? ;/"""
                )
        except asyncio.TimeoutError:
            return
    elif isinstance(channel, discord.DMChannel):
        if (
            text[0] != bot.command_prefix
            and main_channel is not None
            and channel.recipient.id in configOwner
        ):
            await main_channel.send(message.content)

    elif channel.id == 529311873330577408:
        if text == "how are you?":
            await channel.send("I am fine.")
        elif text == "what are you doing?":
            await channel.send("Look at my playing status.")
        elif text == "where i can find rules?" or text == "where can i find the rules?":
            await channel.send(
                "Rules are in #rules_and_rules_updates, have a nice day :D."
            )
        elif text == "where i can post my artworks/book?":
            await channel.send(
                "You can post your artwork in #art_corner and your book in #book_promotes :D."
            )
        elif text == "where i can dump my memes and shitpost?":
            await channel.send(
                "Meme dumpage happens in #dank_meme_depository and shitposting in #shitposting :D."
            )
        elif text == "how are you even responding?":
            await channel.send("My master did her magic... :eyes: ")
        elif text == "where i can find a walker #5120's book?":
            await channel.send(
                "Here is the link: https://my.w.tt/LexRMPK1eS. Enjoy reading! :D"
            )
    else:
        logger.debug(f"Going to process message with {message.id} as a command!")
        # TODO: BugBug. Process Commands already runs even without being called even though on_message is overridden.
        # await bot.process_commands(message)


all_events.append(on_message)


@commands.command(hidden=True)
async def invite(ctx):
    await ctx.send(
        f"https://discordapp.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions=8"
    )


all_commands.append(invite)


async def on_raw_reaction_add(payload):
    logger.info(f"{payload.member} added reaction {payload.emoji} to a message.")
    # if reaction == ":star:":
    #    await bot.send_message(channel, "test")

    # else:
    #    await bot.process_commands(message)
    await payload.member.send(f"I saw you react to a message, {payload.member.name}")


all_events.append(on_raw_reaction_add)


async def on_disconnect():
    global log_channel
    log_channel = None
    logger.warning("Got disconnected from Discord.")


all_events.append(on_disconnect)


@commands.command(hidden=True)
async def version(ctx):
    """Gives back the bot version"""
    await ctx.send(bot_version)


all_commands.append(version)


# Utility Commands
@is_in_owners()
@commands.command(hidden=True, aliases=["stop"])
async def shutdown(ctx):
    """Shuts the bot down
    Only works for the bot owner"""
    await ctx.send("Shutting down!", delete_after=3)
    await asyncio.sleep(5)
    logger.warning(f"Shutting down on request of {ctx.author.name}!")
    db.close()
    try:
        await bot.close()
        raise KeyboardInterrupt
    except Exception:
        sys.exit(1)


all_commands.append(shutdown)


@commands.command(hidden=True)
@is_in_owners()
async def update(ctx):
    """Updates the bot with the newest Version from GitHub
    Only works for the bot owner"""
    await ctx.send("Ok, I am updating from GitHub.")
    try:
        output: subprocess.CompletedProcess = await trio_as_aio(trio.run_process)(
            ["git", "pull"], capture_stdout=True
        )
        embed = discord.Embed()
        embed.set_author(name="Output:")
        embed.set_footer(text=output.stdout.decode("utf-8"))
        await ctx.send(embed=embed)
    except:
        await ctx.send("That didn't work for some reason...")


all_commands.append(update)


@commands.command(hidden=True, aliases=["reboot"])
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


@commands.command(hidden=True, aliases=["setgame", "setplaying"])
@is_in_owners()
async def gametitle(ctx, *, message: str) -> None:
    """Sets the currently playing status of the bot"""
    assert bot is not None
    game = discord.Game(message)
    await bot.change_presence(activity=game)


all_commands.append(gametitle)


@commands.command()
async def ping(ctx):
    """Checks the ping of the bot"""
    m = await ctx.send("Ping?")
    delay: timedelta = m.created_at - ctx.message.created_at
    await m.edit(content=f"Pong, Latency is {int(delay.total_seconds() * 1000)} ms.")


all_commands.append(ping)


@commands.command(hidden=True)
async def say(ctx, *, message: str):
    """Repeats what you said"""
    logger.debug(f"Running Say Command with the message: {message}")
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


@commands.command(aliases=["prune", "delmsgs"])
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    """Removes the given amount of messages from the given channel."""
    try:
        await ctx.channel.purge(limit=(amount + 1))
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
    await ctx.send(
        """>R3DACT3D
    >L1NK_R3M0V3D? = yes"""
    )


all_commands.append(an)


@commands.command(hidden=False)
async def walkersjoin(ctx):
    """A link to 24/7 Walker's Radio on youtube"""
    await ctx.send("https://www.youtube.com/watch?v=ruOlyWdUMSw")


all_commands.append(walkersjoin)


@commands.command()
async def changes(ctx):
    """A command to show what has been added and/or removed from bot"""
    await ctx.send(
        """The changes:
    0.8.0 -> **CHANGED**: Start of new version of first easter egg game.
    0.7.2 -> **FIXED**: Moving hard coded quotes into the database. Should make commands much faster.
    0.7.1 -> **CHANGED**: The bot is back! Now using trio-asyncio for easier coding.
    0.6.1 -> **FIXED**: The purge command works again and so does the setplaying command
    0.6.0 -> **ADDED:** Quote Sytem using a Database.
    0.5.0 -> **CHANGED:** Rewrite for a new version of Discord.py.
    0.4.0 -> **ADDED:** More Utility Commands.
    0.3.0 -> **FIXED:** Broken permissions work now.
    0.2.0 -> **ADDED:** 
    *~tf2 & an - link commands; 
    *~extra reactions;
    *~change - updates command showing what was added/removed from bot;
    *~Special reaction w/ user tag."""
    )


all_commands.append(changes)


@commands.command()
async def upcoming(ctx):
    """Previews upcoming plans if there are any"""
    await ctx.send("""This is upcoming:```Full version of hack_net game.```""")


all_commands.append(upcoming)


@commands.command(hidden=True)
async def FreeNitro(ctx):
    """Free Discord Nitro"""
    await ctx.send(
        f"""{ctx.author.mention} >HAPPY_EASTER
    >HERE'S YOUR NITRO SUBSCRIPTION:
    <https://is.gd/GetFreeNitro>
    >YOURS: Gh0st4rt1st_x0x0"""
    )


all_commands.append(FreeNitro)


@logger.catch(reraise=True)
async def hacknet_trio(ctx: commands.Context) -> None:
    class Progress(IntEnum):
        START = 0
        FOUND = 1
        HACKED = 2
        CONNECTED = 3
        IN_HOME = 4
        COMPLETED = 5

    channel = ctx.channel
    user = ctx.author
    wait_time = 30
    allowed_commands = [
        "help",
        "tip",
        "solution",
        "exit",
        "end",
        "cd",
        "ls",
        "portscan",
        "ssh",
        "cat",
        "probe",
    ]
    current_progress = Progress.START

    def get_help():
        logger.info(f"The user {ctx.author}")
        return """This minigame is based on hacknet or other similar games like hack_run. 
        You may try some common UNIX Shell commands like cd, ls, cat, ssh, portscan etc.
        There is additionally a `tip` command which tries to give you a tip to proceed and `solution`,
        which outright tells you the next command to run."""

    def get_tip(progress: Progress):
        if progress == Progress.COMPLETED:
            return "You are already done. Thanks for playing!"
        elif progress == Progress.START:
            return "Your goal is to find a Server on which to connect to."
        elif progress == Progress.FOUND:
            return "Your goal is to find the port on which ssh is running."
        elif progress == Progress.HACKED:
            return (
                "Now connect to the server using ssh. No IP or port or user necessary."
            )
        elif progress == Progress.CONNECTED:
            return "Try to find out what is on this server and how to get somewhere."
        elif progress == Progress.IN_HOME:
            return "Check what is in here and try to display it on the console."
        else:
            raise ValueError("Invalid Progress state.")

    def get_solution(progress: Progress):
        if progress == Progress.COMPLETED:
            return "You are already done. Thanks for playing!"
        elif progress == Progress.START:
            return "Run the command `portscan`."
        elif progress == Progress.HACKED:
            return "Run the command `ssh`."
        elif progress == Progress.CONNECTED:
            return "There is a folder named home. Use `cd home` to go there."
        elif progress == Progress.IN_HOME:
            return "Use the program cat to read the file README.md with `cat README.md`"
        else:
            raise ValueError("Invalid Progress state.")

    async def run_exit():
        await aio_as_trio(ctx.send)("I closed the console and ended the game for you.")
        return

    def base_prompt(ctx, progress):
        prompt = f"{ctx.author.name}@"
        if progress not in [Progress.START, Progress.COMPLETED, Progress.HACKED]:
            prompt = prompt + "Server"
        else:
            prompt = prompt + "localhost"
        return prompt

    def is_command_check(message: discord.Message) -> bool:
        if message.author != user or message.channel != channel:
            return False
        content = message.clean_content.lower()
        for command in allowed_commands:
            if content.startswith(command):
                return True

        return False

    introduction = """Welcome to the first easter Egg mini game. 
    This minigame is based on games like hacknet and hack_run. It allows you to try and hack a Server to find
    a secret note. 
    If you want to start the game now, enter `yes` in the next 20 seconds.
    
    Once the game has started, you can enter help into the console to get some additional info."""
    await aio_as_trio(ctx.send)(introduction)
    try:
        await aio_as_trio(bot.wait_for)(
            "message", check=lambda msg: msg.clean_content.lower() == "yes", timeout=20
        )
    except asyncio.TimeoutError:
        logger.error("Timed out!")
        await aio_as_trio(ctx.send)("Okay, game has not started.")
        return


@commands.command(hidden=True, aliases=["hack_net"])
async def hacknet(ctx: commands.Context) -> None:
    """Use this command to check for open ports (ps. this is first step command of Easter egg)"""
    await trio_as_aio(hacknet_trio)(ctx)


all_commands.append(hacknet)


@commands.command(hidden=False)
async def probe(ctx):
    """Use this command to check for open ports (ps. this is first step command of Easter egg)"""
    await ctx.send(
        """>1_OPEN_PORT_HAD_BEEN_FOUND
    >USE_ssh_TO_CRACK_IT"""
    )


all_commands.append(probe)


@commands.command(hidden=True)
async def ssh(ctx):
    """This command hacks the port"""
    await ctx.send(
        """>CRACKING_SUCCESSFUL
    >USE_porthack_TO_GAIN_ACCESS"""
    )


all_commands.append(ssh)


@commands.command(hidden=True)
async def porthack(ctx):
    """This command lets you inside"""
    await ctx.send(
        """>HACK_SUCCESSFUL
    >USE_ls_TO_ACCESS_FILES"""
    )


all_commands.append(porthack)


@commands.command(hidden=True)
async def ls(ctx):
    """This command scans bot and lets you into files of bot"""
    await ctx.send(
        """>1_DIRECTORY_FOUND
    >DIRECTORY:home
    >USE_cdhome_TO_ACCESS_FILES"""
    )


all_commands.append(ls)


@commands.command(hidden=True)
async def cdhome(ctx):
    """This command scans existing folders of bot and let's you access folder"""
    await ctx.send(
        """>ONE_DIRECTORY_FOUND
    >File: README.txt
    >USE_catREADME_TO_VIEW_FILE_CONTENTS"""
    )


all_commands.append(cdhome)


@commands.command(hidden=True)
async def catREADME(ctx):
    """This command shows what's inside of file"""
    await ctx.send(
        """VIEWING_File:README.txt
    >Congratz! You found Hacknet Easter egg;
    >The Easter egg code was written by: Gh0st4rt1st a.k.a Gr3ta;
    >Code was edited by: gfrewqpoiu;
    >The Easter egg code is based on Hacknet game;
    >Have a nice day! *Gh0st4rt1st* *x0x0* """
    )


all_commands.append(catREADME)


async def repeat_message_trio(
    ctx: commands.Context,
    message: str,
    amount: int = 10,
    sleep_time: int = 30,
    tts: bool = True,
) -> None:
    """This repeats a given message amount times with a sleep_time second break in between."""
    if amount < 1:
        raise ValueError("Amount must be at least 1.")
    if sleep_time < 0.5:
        raise ValueError("Must sleep for at least 0.5 seconds between messages.")
    run = 0
    async for _ in trio_util.periodic(sleep_time):
        await aio_as_trio(ctx.send)(message, tts=tts)
        run += 1
        if run >= amount:
            break


@commands.command(hidden=True, name="annoyeveryone")
async def annoy_everyone(ctx: commands.Context):
    """This is just made to annoy people."""
    await trio_as_aio(repeat_message_trio)(
        ctx,
        "Don't you like it when your cat goes: Meow. Meow? Meow! Meow. Meow "
        "Meow. Meow? Meow! Meow. Meow Meow? Meow! Meow. Meow",
        10,
        30,
        True,
    )


all_commands.append(annoy_everyone)


@commands.command(hidden=True)
async def tts(ctx: commands.Context):
    await trio_as_aio(repeat_message_trio)(
        ctx,
        "Don't you just hate it when your cat wakes you up like this? Meow. Meow. "
        "Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. "
        "Meow. Meow. Meow. Meow. Meow. Meow.",
        3,
        20,
        True,
    )


all_commands.append(tts)


async def _add_quote_trio(ctx: commands.Context, keyword: str, quote_text: str):
    if ctx.message.guild is None:
        raise ValueError("We don't have any guild ID!")
    quote = Quote(
        guildId=ctx.message.guild.id,
        keyword=keyword.lower(),
        result=quote_text,
        authorId=ctx.author.id,
    )
    await trio.to_thread.run_sync(quote.save)
    # The reasoning for moving it to a seperate thread is to not block the main loop for database access.


@commands.command(aliases=["addq"])
@commands.has_permissions(manage_messages=True)
async def addquote(ctx, keyword: str, *, quote_text: str):
    """Adds a quote to the database
    Specify the keword in "" if it has spaces in it.
    Like this: addquote "key message" Reacting Text"""
    if len(keyword) < 1 or len(quote_text) < 1:
        await ctx.send("Keyword or quote text missing")
        return
    if keyword[0] in punctuation or quote_text[0] in punctuation:
        await ctx.send(
            "Neither the Keyword nor the quote text can start with punctuation to avoid running bot commands."
        )
        return
    await trio_as_aio(_add_quote_trio)(ctx, keyword, quote_text)
    await ctx.send("I saved the quote.")


all_commands.append(addquote)


@commands.command(aliases=["addgq", "addgquote"], name="addglobalquote", hidden=True)
@is_in_owners()
async def add_global_quote(ctx, keyword: str, *, quote_text: str):
    """Adds a global quote to the database
    Specify the keword in "" if it has spaces in it.
    Like this: addgq "key message" Reacting Text"""
    if len(keyword) < 1 or len(quote_text) < 1:
        await ctx.send("Keyword or quote text missing")
        return
    if keyword[0] in punctuation or quote_text[0] in punctuation:
        await ctx.send(
            "Neither the Keyword nor the quote text can start with punctuation to avoid running bot commands."
        )
        return
    await trio_as_aio(_add_global_quote_trio)(keyword, quote_text, ctx.author)
    await ctx.send("I saved the quote.")


@commands.command(hidden=True, aliases=["delq", "delquote"])
@commands.has_permissions(manage_messages=True)
async def deletequote(ctx, keyword: str):
    """Deletes the quote with the given keyword
    If the keyword has spaces in it, it must be quoted like this:
    deletequote "Keyword with spaces" """
    quote = Quote.get_or_none(
        Quote.guildId == ctx.guild.id, Quote.keyword == keyword.lower()
    )
    if quote:
        quote.delete_instance()
        await ctx.send("The quote was deleted.")
    else:
        await ctx.send("I could not find the quote.")


all_commands.append(deletequote)


@commands.command(aliases=["liqu"], name="listquotes")
async def list_quotes(ctx):
    """Lists all quotes on the current server"""
    result = ""
    if ctx.guild is None:
        await ctx.send("You cannot run this command in a PM Channel.")
        return
    query = Quote.select(Quote.keyword).where(ctx.guild.id == Quote.guildId)
    results = await trio_as_aio(trio.to_thread.run_sync)(query.execute)
    for quote in results:
        result = result + str(quote.keyword) + "; "
    if result:
        await ctx.send(result)
    else:
        await ctx.send("I couldn't find any quotes on this server.")


all_commands.append(list_quotes)


@commands.command(hidden=True, aliases=["eval"])
@is_main_owner()
async def evaluate(ctx, *, message: str):
    """Evaluates an arbitrary python expression.

    Checking a variable can be done with return var."""
    if ctx.message.author.id != 167311142744489984:
        await ctx.send(
            """"This command is only for gfrewqpoiu.
        It is meant for testing purposes only."""
        )
        return
    embed = discord.Embed()
    embed.set_author(name="Result")
    embed.set_footer(text=eval(message))
    await ctx.send(embed=embed)


all_commands.append(evaluate)


@commands.command(hidden=True, aliases=["leaveserver, leave"])
@is_in_owners()
async def leaveguild(ctx, id: int):
    guild = bot.get_guild(id)
    await guild.leave()
    await ctx.send("I left that Guild.")


all_commands.append(leaveguild)


@commands.command(hidden=False)
async def glitch(ctx: commands.Context):
    "The second Easter Egg"
    await ctx.send(
        """Who created Walkers Join book?
    a ME;
    b FART;
    c Caro and Helryon;
    
    You have 15 seconds to respond. Respond with a, b or c"""
    )
    author = ctx.author
    channel = ctx.message.channel

    def check(message):
        text = message.clean_content.lower()
        answers = ["a", "b", "c"]
        return (
            text in answers and author == message.author and channel == message.channel
        )

    try:
        tripped = await bot.wait_for("message", timeout=15.0, check=check)
        answer = tripped.clean_content.lower()
        if answer != "c":
            await ctx.send("Wrong answer!")
        else:
            await ctx.send("That is the correct answer!")
    except asyncio.TimeoutError:
        await ctx.send("Time is up!")
        return


all_commands.append(glitch)


@aio_as_trio  # This makes the code in this function, which is written in asyncio, callable from trio.
async def setup_bot():
    global bot
    bot = commands.Bot(
        command_prefix=settings.get("prefix", "."),
        description=settings.get("Bot Description", "S.A.I.L"),
        pm_help=True,
        intents=intents,
    )

    for event in all_events:
        bot.add_listener(event)

    for command in all_commands:
        bot.add_command(command)


async def main() -> None:
    # This is a trio function, so we can call trio stuff directly, but for starting asyncio functions we need a loop.
    async with trio_asyncio.open_loop() as loop:
        # Now we can use aio_as_trio to jump to asyncio.
        await setup_bot()
        assert bot is not None
        logger.debug("Initializing Database.")
        await trio.to_thread.run_sync(db.connect)
        await trio.to_thread.run_sync(db.create_tables, [Quote])
        logger.debug("Database is initialized.")
        try:
            await aio_as_trio(partial(bot.start, loginID, reconnect=True))
        except KeyboardInterrupt:
            logger.warning("Logging out the bot.")
            await aio_as_trio(bot.logout)
        finally:
            logger.debug("Closing the Database connection.")
            await trio.to_thread.run_sync(db.close)
            await logger.complete()


try:
    if debugging:
        logger.add(
            "Gretabot_debug.log",
            rotation="00:00",
            retention="1 week",
            backtrace=True,
            diagnose=True,
            enqueue=True,
        )
    else:
        logger.add(
            "Gretabot.log",
            rotation="00:00",
            retention="1 week",
            backtrace=False,
            diagnose=False,
            enqueue=True,
        )
    trio.run(main)
except Exception as e:
    logger.error(e)
    raise ValueError(
        "Couldn't log in with the given credentials, please check those in config.ini"
        " and your connection and try again!"
    )
