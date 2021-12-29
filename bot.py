#!/usr/bin/env python3
from __future__ import annotations
import sys
import os
import logging
import subprocess

# noinspection PyUnresolvedReferences
from typing import (
    Optional,
    List,
    Union,
    Any,
    Tuple,
    Callable,
    Dict,
    Iterator,
    Final,
    Coroutine,
    Set,
    cast,
    Mapping,
)
from functools import partial
from enum import IntEnum
from datetime import timedelta
import string
import random
import warnings
import time
import re

try:  # These are mandatory.
    import aiohttp
    import discord
    from discord.ext import commands, Command
    from discord import utils, Guild
    from discord.abc import PrivateChannel, GuildChannel
    import asyncio
    from loguru import logger
    import peewee
    import sniffio
    from tenacity import (
        Retrying,
        AsyncRetrying,
        RetryError,
        stop_never,
        retry_if_exception_type,
        wait_fixed,
    )
    from discord_slash import SlashCommand, SlashContext
    from discord_slash.utils import manage_commands
    import attr
    import anyio
    from anyio.abc import TaskGroup
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from anyio.streams.text import TextStream
    import edgedb
except ImportError as e:
    raise ImportError(
        "You have some dependencies missing, please install them with pipenv install --deploy"
    ) from e

from database import db, Quote
from loguru_intercept import InterceptHandler
from checks import getconf, configOwner, is_in_owners


@attr.s(auto_attribs=True)
class SlashCommandInfo:
    """Represents a slash command for later adding to the client"""
    command: Coroutine[Any, Any, None] | Command
    name: str
    description: Optional[str] = None
    options: List[Any] = attr.Factory(list)


# noinspection PyBroadException
def _restart() -> None:
    # pylint: disable=broad-except
    try:
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception:
        pass


log = logging.getLogger("discord")
log.setLevel(logging.DEBUG)
log.addHandler(InterceptHandler())  # This makes discord use loguru for logging.

config = getconf()
login = config["Login"]
settings = config["Settings"]
loginID = login.get("Login Token")
debugging = settings.getboolean("Debugging", fallback=False)
logger.remove()  # This removes the default loguru logger.
if not debugging:
    log.setLevel(
        logging.INFO
    )  # This means, ignore all messages that are debug or trace messages.
    logger.add(  # Here we add the default loguru logger back but with different settings.
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
try:
    log_channel_id: Optional[int] = int(settings.get("Logging Channel", fallback="0"))
except ValueError:
    logger.warning(
        "Couldn't read log_channel_id from the config file, disabling logging to Discord."
    )
    log_channel_id = None
if log_channel_id == 0:
    log_channel_id = None

intents = (
    discord.Intents.default()
)  # This basically tells the bot, for what events it should ask Discord.
intents.typing = False  # This tells Discord that we don't care if someone is typing, so don't send that to us.
intents.presences = (
    True  # If we want to track presence, we need this privileged intent.
    # Presence refers to going online and offline, changing playing status or profile picture, etc.
)
intents.members = True  # This allows us to get all members of a guild. Also privileged.
# Without this, we only get the people that actively run commands in the bot.
punctuation = string.punctuation  # A list of all punctuation characters

bot: Optional[commands.Bot] = None
bot_version: Final[str] = "3.0.0-dev"
main_channel: Optional[discord.TextChannel] = None
log_channel: Optional[discord.TextChannel] = None

# Some shorthands for easier access.
Context = Union[commands.Context, SlashContext]
DiscordException = discord.DiscordException

all_commands: List[
    commands.Command
] = []  # This will be a list of all commands, that the bot will later activate.
all_events: List[
    Union[
        Callable[[Any], Coroutine[Any, Any, None]],
        Callable[[], Coroutine[Any, Any, None]],
    ]
] = []  # This will be a list of all the events that the bot should listen to.

all_slash_commands: List[SlashCommandInfo] = []
# noinspection SpellCheckingInspection
global_quotes: Dict[
    str, str
] = {  # This is a dictionary of all the quotes that should work on any server.
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

shutting_down_event: anyio.Event  # This is basically just a boolean False value, that can be waited for.
started_up_event: anyio.Event
global_task_group: TaskGroup  # A task group is a way to run multiple things at the same time. This will be set later.
log_send_channel: MemoryObjectSendStream[str]
log_recv_channel: MemoryObjectReceiveStream[str]
log_send_channel, log_recv_channel = anyio.create_memory_object_stream(10, str)


def input_to_bool(text: str) -> Optional[bool]:
    """Tries to convert input text to a boolean.

    :param text: The text to convert to a boolean value
    :return: A boolean if the input text was convertible to boolean, or None.
    """
    if text.lower() in ["yes", "y", "yeah", "ja", "j"]:
        return True
    elif text.lower() in ["no", "n", "nah", "nein"]:
        return False
    else:
        return None


@logger.catch(reraise=True)
async def sleep_both(sleep_time: float) -> None:
    """A sleep function that can be called from anyio.

    :param sleep_time: For how long the current task should sleep in seconds.
    """
    try:
        lib = sniffio.current_async_library()
        logger.debug(f"Called sleep from {lib} for {sleep_time} seconds.")
        await anyio.sleep(sleep_time)
    except sniffio.AsyncLibraryNotFoundError:
        warnings.warn("Sleep was called without async context.")
        time.sleep(sleep_time)


@logger.catch(reraise=True)
async def set_status_text_anyio(message: str) -> None:
    """Sets the status of the bot as "playing message"

    Can be called using anyio.
    :param message: The message the bot should display in it's status."""
    assert bot is not None
    await started_up_event.wait()
    logger.debug(f"Setting playing status to {message}")
    # noinspection PyArgumentList
    game = discord.Game(message)
    try:
        lib = sniffio.current_async_library()
        if lib == "asyncio":
            await bot.change_presence(activity=game)
        else:
            raise RuntimeError("Trio is no longer supported")
    except sniffio.AsyncLibraryNotFoundError:
        warnings.warn("Not in async context.", RuntimeWarning)
        global_task_group.start_soon(partial(bot.change_presence, activity=game))


@logger.catch(reraise=True)
async def send_message_both(
    target: discord.abc.Messageable,
    message: str,
    no_log: bool = False,
    **kwargs,
) -> None:
    """Sends a message to `target`.

    Can be called both from anyio.

    :rtype: None
    :param target: discord.abc.Messageable: Where to send the message
    :param message: str: The message to send
    :param no_log: bool: Whether to not log the message. Defaults to False, so to log the message.
    :param kwargs: Additional arguments to provide to target.send()
    :raises: discord.Forbidden if it can't send the message
    :raises: discord.HTTPException if the sending failed.
    :return: None"""
    assert bot is not None

    if shutting_down_event.is_set():
        return

    if isinstance(target, SlashContext):
        target = target.channel

    if isinstance(target, commands.Context):
        target = target.channel

    def chunks(long_string: str) -> Iterator[str]:
        """Produce `n`-character chunks from `s`."""
        for start in range(0, len(long_string), 1950):
            yield long_string[start : start + 1950]

    async def log_sent_message(
        to: discord.abc.Messageable, message_to_send: str
    ) -> None:
        """Logs the message sending."""
        if isinstance(to, discord.TextChannel):
            name = to.name
        elif isinstance(to, discord.DMChannel):
            name = to.recipient.name
        elif isinstance(to, discord.GroupChannel) and to.name is not None:
            name = to.name
        else:
            name = str(to)
        from_library = sniffio.current_async_library()
        logger.debug(f"Sending message {message_to_send} to {name} from {from_library}")

    if len(message) > 1950:
        for sub_message in chunks(message):
            await send_message_both(target, sub_message, no_log, kwargs=kwargs)
            await sleep_both(3)
        return

    try:
        if not no_log:
            await log_sent_message(target, message)
        library = sniffio.current_async_library()
        if library == "asyncio":
            await target.send(content=message, **kwargs)
        else:
            raise RuntimeError("Trio is no longer supported")
    except sniffio.AsyncLibraryNotFoundError:
        warnings.warn("Not in async Context.", RuntimeWarning)
        task = partial(target.send, content=message, **kwargs)
        logger.warning(
            f"Sending message {message} to {str(target)} from outside async context."
        )
        global_task_group.start_soon(task)


async def wait_for_event_both(
    event: str,
    check: Any,
    timeout: float = 15.0,
) -> Any:
    """Uses the bot to wait for a specific Discord Event.

    :param event: A string representing the Discord Event to wait for (without the on_).
    :param check: A boolean callable with a check whether to trigger the Event or None to always trigger.
    :param timeout: How long to wait for until raising TimeoutError.
    :return: None or the result from the event.
    :raises: TimeoutError
    """
    assert bot is not None
    try:
        lib = sniffio.current_async_library()
        if lib == "asyncio":
            return await bot.wait_for(event, timeout=timeout, check=check)
        else:
            raise RuntimeError("Not using asyncio!")
    except sniffio.AsyncLibraryNotFoundError as se:
        raise RuntimeError("Not in async Context.") from se
    except asyncio.TimeoutError as at:
        raise TimeoutError("The event didn't happen.") from at


def log_startup() -> None:
    """This logs the startup messages to the console."""
    assert bot is not None
    if started_up_event.is_set():
        return
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


async def _add_global_quote_anyio(
    keyword: str, text: str, author: Optional[discord.User] = None
) -> None:
    """This adds a global quote to the database.

    Global quotes work on any server and in Private messages with the bot.

    :param keyword: The keyword of the quote
    :param text: The text that the bot should send when the keyword is detected.
    :param author: Optional,
    """
    keyword = keyword.lower()
    quote = await anyio.to_thread.run_sync(
        Quote.get_or_none, -1 == Quote.guildId, keyword == Quote.keyword
    )
    if quote is None:
        logger.info(
            f"Adding global quote {keyword} with text {text} because it is not in the database."
        )
        quote = Quote(guildId=-1, keyword=keyword, result=text, authorId=-1)
        if author is not None:
            quote.authorId = author.id
        await anyio.to_thread.run_sync(quote.save)


def log_to_channel(message: str) -> None:
    """Puts a message into the queue for the logging task to log it.

    This function should be passed as the sink to logger.add() but the logger MUST NOT have enqueue=True.

    :param message: The message that should be logged.
    """
    global log_channel  # pylint: disable=global-statement

    # There are probably better ways to do this, but we are constrained by three things.
    # 1. We only get message as a parameter and cannot add any other parameters. Maybe Contextvars?
    # 2. This function needs to be callable from sync context, asyncio context, and anyio context.
    # 3. If this errors, there is a high likelihood to cause a deadlock and crash so we need to avoid that.
    try:
        if log_channel is not None:
            assert bot is not None
            if not shutting_down_event.is_set() and started_up_event.is_set():
                library = sniffio.current_async_library()
                if debugging:
                    print(f"Logging to Discord from Library: {library}")
                try:
                    # logging_queue.put_nowait(message)
                    log_send_channel.send_nowait(message)
                except anyio.WouldBlock as e:
                    raise RuntimeError("Queue is full") from e

        else:
            return
    except DiscordException:
        pass
    except sniffio.AsyncLibraryNotFoundError:
        # This happens when calling logger from weird edge cases.
        # Sadly, nothing seems to be transferred to this state.
        # We just ignore the message in this case, it gets logged to file and console anyway.
        print(
            f"Logging to Discord failed for message: {message} because of unknown async context."
        )
    except RuntimeError:
        print(
            f"Logging to Discord failed for message: {message} because the queue is full"
        )


def setup_channel_logger() -> Optional[int]:
    """Sets up a logger and returns the ID of the logger."""
    format_str = (
        "```{time: HH:mm:ss.SSS} | <level>{level: <8}</level> | {function}:{line} - <level>{"
        "message}</level>```"
    )
    if log_channel is not None:
        logger.info(f"Setting up logging to {log_channel.name}")
        return int(
            logger.add(
                log_to_channel,
                level="INFO",
                format=format_str,
                colorize=False,
                backtrace=False,
                diagnose=False,
                enqueue=False,
            )
        )
    return None


def setup_log_channel() -> None:
    """Starts the setup of the Discord Log Channel if one is defined in the config."""
    global log_channel  # pylint: disable=global-statement
    if log_channel_id is not None:
        assert bot is not None
        log_channel = bot.get_channel(log_channel_id)
        if log_channel is not None:
            logger.debug("Found bot log channel.")
            setup_channel_logger()


async def on_ready_anyio() -> None:
    """This runs the setup of other things that depend on the bot being fully ready."""
    global log_channel, shutting_down_event, started_up_event  # pylint: disable=global-statement
    shutting_down_event = anyio.Event()
    log_channel = None
    started_up_event = anyio.Event()
    async with anyio.create_task_group() as task_group:
        # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
        # noinspection PyAsyncCall
        task_group.start_soon(anyio.to_thread.run_sync, log_startup)
    # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
    # noinspection PyAsyncCall
    started_up_event.set()
    async with anyio.create_task_group() as task_group:
        # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
        # noinspection PyAsyncCall
        task_group.start_soon(set_status_text_anyio, "waiting")
        for keyword, text in global_quotes.items():
            task = partial(_add_global_quote_anyio, keyword, text, None)
            # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
            # noinspection PyAsyncCall
            task_group.start_soon(task)
        # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
        # noinspection PyAsyncCall
        task_group.start_soon(anyio.to_thread.run_sync, setup_log_channel)

    # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
    # noinspection PyAsyncCall
    global_task_group.start_soon(logging_task_anyio)
    logger.debug("Done with setup in anyio.")


async def on_ready() -> None:
    """This runs whenever the bot is ready to accept commands."""
    await on_ready_anyio()
    logger.success("Done with bot setup.")


all_events.append(on_ready)


async def on_guild_join(server: discord.Guild) -> None:
    """This runs whenever the bot gets invited into a new guild."""
    logger.success(f"I just joined the server {server.name} with the ID {server.id}")


all_events.append(on_guild_join)


async def on_guild_remove(server: discord.Guild) -> None:
    """This runs whenever the bot leaves a guild."""
    global log_channel  # pylint: disable=global-statement
    if log_channel is not None:
        if log_channel.guild == server:
            log_channel = None
            logger.warning("Removed the server used for logging, turned it off.")
    logger.warning(f"I left the server {server.name} with the ID {server.id}")


all_events.append(on_guild_remove)


def _get_quote_sync(guild: discord.Guild, text: str) -> Optional[str]:
    """This gets a quote from the database.

    It prefers a guild specific quote, but if it can't find a guild quote, it will also look for a global quote.
    :param guild: The discord.Guild that should be checked for quotes
    :param text: The keyword to search for
    :return: Either the found string, or None if nothing was found.
    """
    logger.debug(f"Looking for quote with text: {text} in guild {guild.name}")
    quote = Quote.get_or_none(guild.id == Quote.guildId, text.lower() == Quote.keyword)
    if quote:
        return str(quote.result)
    else:
        quote = Quote.get_or_none(-1 == Quote.guildId, text.lower() == Quote.keyword)
        if quote:
            return str(quote.result)
    logger.debug("No quote found.")
    return None


async def get_quote_anyio(guild: Optional[discord.Guild], text: str) -> Optional[str]:
    if guild:
        return cast(
            Optional[str],
            await anyio.to_thread.run_sync(_get_quote_sync, guild, text),
        )
    else:
        task = partial(
            Quote.get_or_none, -1 == Quote.guildId, text.lower() == Quote.keyword
        )
        quote = await anyio.to_thread.run_sync(task)
        if quote:
            return str(quote.result)
        else:
            return None


async def on_message(message: discord.Message) -> None:
    """This function runs whenever the bot sees a new message in Discord.

    :param message: The discord.Message that the bot received.
    :return: None
    """
    assert (
        bot is not None
    )  # assert means, check that this is the case, otherwise raise an Assertion Error.

    if (
        message.author.bot
    ):  # If the message is from a bot, we ignore it and just end here.
        return

    logger.debug(f"Processing Message with ID {message.id}")

    # noinspection SpellCheckingInspection
    def booleanable(old_message: discord.Message) -> bool:
        message_text = old_message.clean_content.lower()
        agreement = ["yes", "y", "yeah", "ja", "j", "no", "n", "nah", "nein"]
        return (
            message_text in agreement
            and old_message.author == message.author
            and old_message.channel == message.channel
        )

    text: str = message.clean_content.lower()
    channel: Union[
        discord.TextChannel, discord.DMChannel, discord.GroupChannel
    ] = message.channel
    guild = cast(Union[Guild, Guild, None], message.guild)

    quote = await get_quote_anyio(guild, text)
    if quote:
        await channel.send(quote)
        return

    if bot.user.mentioned_in(message):
        await channel.send("Can I help you with anything?")
        try:
            tripped = await wait_for_event_both(
                "message", timeout=15.0, check=booleanable
            )
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
        except TimeoutError:
            return

    elif isinstance(channel, discord.DMChannel):
        if (
            text[0] != bot.command_prefix
            and main_channel is not None
            and channel.recipient.id in configOwner
        ):
            await main_channel.send(message.content)

    # noinspection SpellCheckingInspection
    elif channel.id == 529311873330577408:
        # noinspection SpellCheckingInspection
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
            # noinspection SpellCheckingInspection
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
        # TODO: Bug. Process Commands already runs even without being called even though on_message is overridden.
        # await bot.process_commands(message)


all_events.append(on_message)


async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    """This gets called whenever the bot sees a new reaction to a message."""
    if payload.member is None:
        return
    logger.info(f"{payload.member} added reaction {payload.emoji} to a message.")
    # if reaction == ":star:":
    #    await bot.send_message(channel, "test")

    # else:
    #    await bot.process_commands(message)
    if debugging:
        await payload.member.send(
            f"I saw you react to a message, {payload.member.name}"
        )


all_events.append(on_raw_reaction_add)


async def on_disconnect() -> None:
    """This runs whenever the client disconnects from Discord."""
    global log_channel, started_up_event  # pylint: disable=global-statement
    log_channel = None
    started_up_event = anyio.Event()
    # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
    # noinspection PyAsyncCall
    shutting_down_event.set()
    logger.warning("Got disconnected from Discord.")


all_events.append(on_disconnect)


@commands.command(hidden=True, name="invitebot")
async def invite_bot(ctx: Context) -> None:
    """Gives a link to invite the bot."""
    assert bot is not None
    await send_message_both(
        ctx,
        "".join(
            [
                "https://discordapp.com/oauth2/authorize?client_id=",
                str(bot.user.id),
                "&permissions=8&scope=bot%20applications.commands",
            ]
        ),
    )
    logger.warning(f"{ctx.author.name} requested an invite for the bot!")


all_commands.append(invite_bot)
all_slash_commands.append(
    SlashCommandInfo(
        command=invite_bot,
        name="invitebot",
        description="Gives a link to invite the bot.",
        options=[],
    )
)


@commands.command(hidden=True)
async def github(ctx: Context) -> None:
    """Gives a link to the code of this bot."""
    await send_message_both(
        ctx,
        """Here is the github link to my code:
        https://github.com/gfrewqpoiu/GretaBot""",
    )
    logger.info(f"{ctx.author.name} ran the github command.")


all_commands.append(github)
all_slash_commands.append(
    SlashCommandInfo(
        command=github,
        name="github",
        description="Gives a link to the code of this bot.",
        options=[],
    )
)


@commands.command(hidden=True)
async def version(ctx: Context) -> None:
    """Gives back the bot version"""
    await send_message_both(ctx, bot_version)
    logger.info(f"{ctx.author.name} ran the version command.")


all_commands.append(version)
all_slash_commands.append(
    SlashCommandInfo(
        command=version,
        name="version",
        description="Gives back the bot version.",
        options=[],
    )
)


# Utility Commands
@is_in_owners()
@commands.command(hidden=True, aliases=["stop"])
async def shutdown(ctx: Context) -> None:
    """Shuts the bot down.

    Only works for the bot owners."""
    assert ctx.author.id in configOwner
    await send_message_both(ctx, "Shutting down!", delete_after=3)
    await sleep_both(5)
    # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
    # noinspection PyAsyncCall
    shutting_down_event.set()
    logger.warning(f"Shutting down on request of {ctx.author.name}!")
    await sleep_both(3)
    db.close()
    try:
        assert bot is not None
        raise SystemExit from None
    except discord.DiscordException:
        sys.exit(1)
    except AssertionError:
        raise SystemExit from None


all_commands.append(shutdown)  # type: ignore


@commands.command(hidden=True)
@is_in_owners()
async def update(ctx: Context) -> None:
    """Updates the bot with the newest Version from GitHub
    Only works for the bot owners."""
    assert ctx.author.id in configOwner
    await send_message_both(ctx, "Ok, I am updating from GitHub.")
    try:
        output = await anyio.run_process(
            ["git", "pull"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        embed = discord.Embed()
        embed.set_author(name="Output:")
        embed.set_footer(text=output.stdout.decode("utf-8"))
        await ctx.send(embed=embed)
    except subprocess.CalledProcessError as er:
        await send_message_both(ctx, "That didn't work for some reason...")
        logger.exception(er)
        raise er


all_commands.append(update)
all_slash_commands.append(
    SlashCommandInfo(
        command=update,
        name="update",
        description="Updates the bot from github. (Owners Only)",
        options=[],
    )
)


@commands.command(hidden=True, aliases=["reboot"])
@is_in_owners()
async def restart(ctx: Context) -> None:
    """Restarts the bot.

    Only works for bot owners."""
    assert ctx.author.id in configOwner
    await send_message_both(ctx, "Restarting", delete_after=3)
    await asyncio.sleep(5)
    logger.warning(f"Restarting on request of {ctx.author.name}!")
    db.close()
    try:
        await log_send_channel.aclose()
    except discord.NotFound:
        pass
    # noinspection PyBroadException
    try:
        _restart()
    except Exception as ex:  # pylint: disable=broad-except
        logger.exception(ex)


all_commands.append(restart)
all_slash_commands.append(
    SlashCommandInfo(
        command=restart,
        name="restart",
        description="Restarts the bot. (Owners Only)",
        options=[],
    )
)


# noinspection PyUnusedLocal
@commands.command(hidden=True, aliases=["setgame", "setplaying"], name="gametitle")
@is_in_owners()
async def game_title(ctx: Context, *, message: str) -> None:
    """Sets the currently playing status of the bot.

    Only works for bot owners."""
    assert bot is not None
    assert ctx.author.id in configOwner
    # noinspection PyArgumentList
    game = discord.Game(message)
    await bot.change_presence(activity=game)


all_commands.append(game_title)
all_slash_commands.append(
    SlashCommandInfo(
        command=game_title,
        name="gametitle",
        description="Sets the bots playing status.",
        options=[
            manage_commands.create_option(
                name="message",
                description="The new playing status.",
                option_type=3,
                required=True,
            )
        ],
    )
)


@commands.command()
async def ping(ctx: Context) -> None:
    """Checks the ping of the bot"""
    m = await ctx.send("Ping?")
    delay: timedelta = m.created_at - ctx.message.created_at
    try:
        await m.edit(
            content=f"Pong, Latency is {int(delay.total_seconds() * 1000)} ms."
        )
    except discord.Forbidden:
        await send_message_both(ctx, "I cannot edit messages in this channel!")
        await m.delete()
        await send_message_both(
            ctx, f"Pong, Latency is {int(delay.total_seconds() * 1000)} ms."
        )


all_commands.append(ping)
all_slash_commands.append(
    SlashCommandInfo(
        ping, name="ping", description="Check the name of the bot.", options=[]
    )
)


# noinspection DuplicatedCode
@commands.command(hidden=True)
async def say(ctx: Context, *, message: str) -> None:
    """Repeats what you said."""
    out = [f"{ctx.author.name} ran say Command with the message: {message}"]
    if ctx.guild is not None:
        out.append(f" in the guild {ctx.guild.name}")
    if ctx.channel is not None:
        out.append(f" in the channel {ctx.channel.name}.")
    logger.info("".join(out))
    await send_message_both(ctx, message)


all_commands.append(say)
all_slash_commands.append(
    SlashCommandInfo(
        command=say,
        name="say",
        description="Repeats what you said.",
        options=[
            manage_commands.create_option(
                name="message",
                description="What the bot should say.",
                option_type=3,
                required=True,
            )
        ],
    )
)


@commands.command(
    hidden=True,
    aliases=["msg_user", "msguser", "msgto", "pmuser", "pm_user", "say_to", "sayto"],
)
async def msg_to(ctx: Context, user: discord.User, *, message: str) -> None:
    """Messages the given user via PM"""
    out = [f"{ctx.author.name} ran msg_to Command with the message: {message}"]
    if ctx.guild is not None:
        out.append(f" in the guild {ctx.guild.name}")
    if ctx.channel is not None:
        out.append(f" in the channel {ctx.channel.name}.")
    logger.info("".join(out))
    await send_message_both(user, message)


# noinspection DuplicatedCode
@commands.command(hidden=True)
async def say3(ctx: SlashContext, *, message: str) -> None:
    """Repeats what you said, but only to you."""
    out = [f"{ctx.author.name} ran say3 Command with the message: {message}"]
    if ctx.guild is not None:
        out.append(f" in the guild {ctx.guild.name}")
    if ctx.channel is not None and isinstance(ctx.channel, discord.TextChannel):
        # noinspection PyUnresolvedReferences
        out.append(f" in the channel {ctx.channel.name}.")
    logger.info("".join(out))
    await ctx.send(message, hidden=True)


all_slash_commands.append(
    SlashCommandInfo(
        command=say3,
        name="say3",
        description="Repeats what you said, but only to you.",
        options=[
            manage_commands.create_option(
                name="message",
                description="What the bot should say.",
                option_type=3,
                required=True,
            )
        ],
    )
)


# noinspection DuplicatedCode
@commands.command(hidden=True)
@commands.has_permissions(manage_messages=True)
async def say2(ctx: Context, *, message: str) -> None:
    """Repeats what you said and removes the command message."""
    if ctx.guild is not None:
        assert ctx.author.permissions_in(ctx.channel).manage_messages
    logger.debug(f"Running Say2 command with the message: {message}")
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        await send_message_both(ctx, "I cannot delete messages in this channel!")
    except AttributeError:
        pass
    out = [f"{ctx.author.name} ran say2 Command with the message: {message}"]
    if ctx.guild is not None:
        out.append(f" in the guild {ctx.guild.name}")
    if ctx.channel is not None:
        out.append(f" in the channel {ctx.channel.name}.")
    logger.info("".join(out))
    await send_message_both(ctx, message)


all_commands.append(say2)
all_slash_commands.append(
    SlashCommandInfo(
        command=say2,
        name="say2",
        description="Repeats what you said and removes your message.",
        options=[
            manage_commands.create_option(
                name="message",
                description="What the bot should say.",
                option_type=3,
                required=True,
            )
        ],
    )
)


@commands.command(hidden=True, aliases=["setchannel"])
@is_in_owners()
@commands.guild_only()
async def set_channel(ctx: Context) -> None:
    """Sets the channel for PM messaging."""
    assert ctx.guild is not None
    assert ctx.author.id in configOwner
    global main_channel
    main_channel = ctx.channel
    assert main_channel is not None
    await ctx.message.delete()
    await send_message_both(
        ctx, "Set the default channel to this channel.", delete_after=10
    )
    logger.success(f"Set the DM Response Channel to {main_channel.name} in {ctx.guild}")


all_commands.append(set_channel)
all_slash_commands.append(
    SlashCommandInfo(
        command=set_channel,
        name="setchannel",
        description="Sets the channel for PM messaging (Owner Only).",
        options=[],
    )
)


@commands.command()
@commands.has_permissions(kick_members=True)
@commands.guild_only()
async def kick(ctx: Context, user: discord.Member) -> None:
    """Kicks the specified User"""
    assert ctx.guild is not None
    assert ctx.author.permissions_in(ctx.channel).kick_members
    if user is None:
        await send_message_both(ctx, "No user was specified.")
        return
    try:
        assert ctx.guild is not None
        # noinspection PyUnresolvedReferences
        await ctx.kick(user)
        await send_message_both(ctx, f"{user.name} has been kicked from the server.")
        logger.success(f"Kicked user {user.name} from Server {ctx.guild.name}")
    except discord.Forbidden:
        await send_message_both(
            ctx, "I can't kick this user because of missing permissions."
        )
    except DiscordException:
        await send_message_both(ctx, "I couldn't kick that user.")


all_commands.append(kick)
all_slash_commands.append(
    SlashCommandInfo(
        command=kick,
        name="kick",
        description="Kicks the specified user.",
        options=[
            manage_commands.create_option(
                name="user",
                description="The user that should be kicked",
                option_type=6,
                required=True,
            )
        ],
    )
)


@commands.command()
@commands.has_permissions(ban_members=True)
@commands.guild_only()
async def ban(ctx: commands.Context, user: discord.Member) -> None:
    """Bans the specified User"""
    assert ctx.guild is not None
    assert ctx.author.permissions_in(ctx.channel).ban_members
    if user is None:
        await send_message_both(ctx, "No user was specified.")
        return
    try:
        assert ctx.guild is not None
        # noinspection PyUnresolvedReferences
        await ctx.ban(user)
        await send_message_both(ctx, "The user has been banned from the server.")
        logger.success(f"User {user.name} was banned from Server {ctx.guild.name}")
    except DiscordException:
        await send_message_both(ctx, "I couldn't ban that user.")


all_commands.append(ban)


@commands.command()
async def info(ctx: Context) -> None:
    """Gives some info about the bot"""
    assert bot is not None
    message = f"""📢
    Hello, I'm {bot.user.name}, a Discord bot made for simple usage by Gr3ta a.k.a Gh0st4rt1st.
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

    Fun facts:
    1.)S.A.I.L name comes from Starbound game's AI character S.A.I.L;
    2.)S.A.I.L stands for Ship-based Artificial Intelligence Lattice.
    3.)I was renamed from S.A.I.L to {bot.user.name}"""

    await send_message_both(ctx, message)


all_commands.append(info)
all_slash_commands.append(
    SlashCommandInfo(
        command=info,
        name="info",
        description="Gives some info about the bot.",
        options=[],
    )
)


@commands.command(aliases=["prune", "delmsgs", "deletemessages", "delete_messages"])
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def purge(ctx: Context, amount: int) -> None:
    """Removes the given amount of messages from this channel."""
    assert ctx.guild is not None
    assert ctx.author.permissions_in(ctx.channel).manage_messages
    try:
        assert ctx.guild is not None
        await ctx.channel.purge(limit=(amount + 1))
        logger.success(
            f"Deleted {amount} messages from channel {ctx.channel.name} in Server {ctx.guild.name}"
        )
        await send_message_both(ctx, "Done!", delete_after=10)
    except discord.Forbidden:
        await send_message_both(
            ctx, "I couldn't do that because of missing permissions..."
        )
    except discord.HTTPException as ex:
        logger.exception(ex)
        raise ex


all_commands.append(purge)
all_slash_commands.append(
    SlashCommandInfo(
        command=purge,
        name="purge",
        description="Deletes multiple messages from this channel.",
        options=[
            manage_commands.create_option(
                name="amount",
                description="How many messages to delete.",
                option_type=4,
                required=True,
            )
        ],
    )
)


@commands.command(hidden=False)
async def tf2(ctx: Context) -> None:
    """Gives a link to a funny video from Team Fortress 2."""
    await send_message_both(ctx, "https://www.youtube.com/watch?v=r-u4rA_yZTA")


all_commands.append(tf2)
all_slash_commands.append(
    SlashCommandInfo(
        command=tf2,
        name="tf2",
        description="Gives a link to a funny video from Team Fortress 2.",
        options=[],
    )
)


@commands.command(hidden=False)
async def an(ctx: Context) -> None:
    """A command giving the link to A->N website"""
    # noinspection SpellCheckingInspection
    await send_message_both(
        ctx,
        """>R3DACT3D
        >L1NK_R3M0V3D? = yes""",
    )


all_commands.append(an)
all_slash_commands.append(
    SlashCommandInfo(
        command=an,
        name="an",
        description="A command giving the link to A->N website",
        options=[],
    )
)


@commands.command(hidden=False, name="walkersjoin")
async def walkers_join(ctx: Context) -> None:
    """Gives a link to the now defunct 24/7 Walker's Radio on YouTube."""
    await send_message_both(ctx, "https://www.youtube.com/watch?v=ruOlyWdUMSw")


all_commands.append(walkers_join)
all_slash_commands.append(
    SlashCommandInfo(
        command=walkers_join,
        name="walkersjoin",
        description="Gives a link to the now defunct 24/7 Walker's Radio on YouTube.",
        options=[],
    )
)


@commands.command()
async def changes(ctx: Context) -> None:
    """A command to show what has been added and/or removed from bot"""
    await send_message_both(
        ctx,
        """The changes:
    1.0.0 -> **ADDED**: Many commands can now be run by using /command.
    Though the old prefix based commands still work.
    And some commands, esp. hidden ones, don't work with /.
    0.11.0 -> **ADDED:** Lots of additional documentation.
    0.10.0 -> **ADDED:** New help2 command for owners. 
    Changes of 0.6.1 or earlier will be removed from this list in the next update.
    EDIT: They have been removed.
    0.9.1 -> **CHANGED**: Logging fixed, new playing statuses.
    0.8.0 -> **CHANGED**: Start of new version of first easter egg game.
    0.7.2 -> **FIXED**: Moving hard coded quotes into the database. Should make commands much faster.
    0.7.1 -> **CHANGED**: The bot is back! Now using trio-asyncio for easier coding.""",
    )


all_commands.append(changes)
all_slash_commands.append(
    SlashCommandInfo(
        command=changes,
        name="changes",
        description="Gives back the changelog of the bot.",
        options=[],
    )
)


@commands.command()
async def upcoming(ctx: Context) -> None:
    """Previews upcoming plans if there are any."""
    await send_message_both(
        ctx,
        """This is upcoming:```Markdown
        * Full version of hack_run game.
        ```""",
    )


all_commands.append(upcoming)
all_slash_commands.append(
    SlashCommandInfo(
        command=upcoming,
        name="upcoming",
        description="Previews upcoming plans if there are any.",
        options=[],
    )
)


@commands.command(hidden=True, aliases=["FreeNitro", "freenitro", "Free_Nitro"])
async def free_nitro(ctx: commands.Context) -> None:
    """Gives you a link to Free Discord Nitro."""
    await send_message_both(
        ctx,
        f"""{ctx.author.mention} >HAPPY_EASTER
    >HERE'S YOUR NITRO SUBSCRIPTION:
    <https://is.gd/GetFreeNitro>
    >YOURS: Gh0st4rt1st_x0x0""",
    )


all_commands.append(free_nitro)
# This command should not get a / command version.


@logger.catch(reraise=True)
async def hacknet_anyio(ctx: Context) -> None:
    """The implementation of the new hack_net and hack_run game.

    The game is based heavily on hack_run. It is supposed to simulate a UNIX Terminal, where the user
    can enter commands and progress to "connect" to a server and see a secret message."""
    # pylint: disable=unused-variable
    class Progress(IntEnum):
        """This represents the game progress."""

        START = 0
        FOUND = 1
        HACKED = 2
        CONNECTED = 3
        IN_HOME = 4
        COMPLETED = 5

    user: discord.User = ctx.author
    name: str = user.name
    wait_time = 30  # How long to wait for user input before ending the game.
    allowed_commands = [  # This is a list of all supported commands.
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
        "credits",
        "thanks",
    ]
    current_progress = Progress.START

    def get_help() -> str:
        """Returns the help for the game."""
        logger.info(f"The user {ctx.author} ran the help command of hack_net.")
        return """This minigame is based on hacknet or other similar games like hack_run. 
        You may try some common UNIX Shell commands like cd, ls, cat, ssh, portscan etc.
        There is additionally a `tip` command which tries to give you a tip to proceed and `solution`,
        which outright tells you the next command to run.

        You can also use the commands credits and thanks to get credits and thanks from the developer."""

    def get_tip(progress: Progress) -> str:
        """Returns a tip for the player to progress."""
        logger.warning(f"The user {ctx.author} ran the tip command of hack_net")
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

    def get_solution(progress: Progress) -> str:
        """Tells the player what to do to progress to the next step."""
        logger.warning(f"The user {ctx.author} ran the solution command of hack_net")
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

    def get_exit() -> str:
        """Returns the End Game String."""
        return "I closed the console and ended the game for you."

    def base_prompt(user_name: str, progress: Progress) -> List[str]:
        """Gives a base representation of the "console" for the current user without trailing `

        :param user_name: The username
        :param progress: The current game progress
        :return: A list of substrings that should be joined by "".join(list).
        """

        # We are using a list of strings here because it allows us to add to a string efficiently.
        # Strings are immutable in Python, so string = string + "Additional text" is really inefficient.
        return_list = [f"```{user_name}@"]
        if progress not in [Progress.START, Progress.COMPLETED, Progress.HACKED]:
            return_list.append("Server")
        else:
            return_list.append("localhost")
        return_list.append("> ")
        return return_list

    def is_command_check(message: discord.Message) -> bool:
        """Checks whether the given message is a command."""
        if message.author != user or message.channel != user.dm_channel:
            return False
        content = message.clean_content.lower()
        for command in allowed_commands:
            if content.startswith(command):
                return True

        return False

    async def command_or_cancel() -> str:
        """Tries to get a command from the user."""
        try:
            command = await wait_for_event_both("message", is_command_check, wait_time)
            logger.success(
                f"{user.name} ran hack_net command {command.clean_content.lower()}"
            )
            return str(command.clean_content).lower()
        except TimeoutError:
            logger.warning(f"{user.name} played hack_net but timed out.")
            await send_message_both(
                user, "You timed out while I waited for the next command."
            )
            raise TimeoutError

    async def call_command(command: str) -> None:
        """Actually "runs" the given command."""
        # allowed_commands = [
        #     "help",
        #     "tip",
        #     "solution",
        #     "exit",
        #     "end",
        #     "cd",
        #     "ls",
        #     "portscan",
        #     "ssh",
        #     "cat",
        #     "probe",
        #     "credits",
        #     "thanks",
        # ]
        if command.startswith("help"):
            await send_message_both(user, get_help())
            return
        elif command.startswith("tip"):
            await send_message_both(user, get_tip(current_progress))
            return
        elif command.startswith("solution"):
            await send_message_both(user, get_solution(current_progress))
            return
        elif command.startswith("end") or command.startswith("exit"):
            await send_message_both(user, get_exit())
            return
        else:
            raise NotImplementedError("Not yet implemented.")

    introduction = f"""Welcome to the third easter Egg mini game. 
    This minigame is based on games like hacknet and hack_run. It allows you to try and hack a Server to find
    a secret note. 
    If you want to start the game now, enter `yes` in the next {wait_time} seconds.
    The game will be played in Private Messages, so if you want to play, the bot needs to be able to PM you.

    Once the game has started, you can enter help into the console to get some additional info."""
    await send_message_both(ctx, introduction)
    try:
        assert bot is not None
        await wait_for_event_both(
            "message",
            check=lambda msg: msg.clean_content.lower() == "yes",
            timeout=wait_time,
        )
    except TimeoutError:
        logger.warning(f"{ctx.author} ran hack_net but timed out.")
        await send_message_both(ctx, "Okay, game has not started.")
        return

    await send_message_both(
        user,
        """Okay, this is your prompt. Just respond with a command and it gets run.
    *Hint: Any commands, that are not recognized, get ignored.*
    If you want to end the game at any time, enter `end` or `exit`""",
    )
    await sleep_both(0.5)
    prompt = base_prompt(name, current_progress)
    prompt.append("```")
    await send_message_both(user, "".join(prompt))
    await sleep_both(0.5)
    await send_message_both(
        user, "Thank you for your interest in playing, the rest is not implemented yet."
    )
    # TODO: Finish implementation of hack_net.
    raise NotImplementedError


@commands.command(hidden=True, aliases=["hacknet", "hack_run", "hackrun"])
async def hack_net(ctx: Context) -> None:
    """Use this command to start the new WIP mini-game (ps. this is first step command of Easter egg)."""
    await hacknet_anyio(ctx)


all_commands.append(hack_net)
# TODO: Add slash command once hack_net is finished.


@commands.command(hidden=False)
async def probe(ctx: Context) -> None:
    """Use this command to check for open ports (ps. this is first step command of Easter egg)."""
    assert bot is not None
    await send_message_both(
        ctx,
        f""">1_OPEN_PORT_HAD_BEEN_FOUND
    >USE_{bot.command_prefix}ssh_TO_CRACK_IT""",
    )


all_commands.append(probe)
all_slash_commands.append(
    SlashCommandInfo(
        command=probe,
        name="probe",
        description="Use this command to check for open ports (ps. this is first step command of Easter egg).",
        options=[],
    )
)


@commands.command(hidden=True)
async def ssh(ctx: commands.Context) -> None:
    """This command hacks the port."""
    await send_message_both(
        ctx,
        """>CRACKING_SUCCESSFUL
    >USE_porthack_TO_GAIN_ACCESS""",
    )


all_commands.append(ssh)
# This command should not get a / command version.


@commands.command(hidden=True)
async def porthack(ctx: commands.Context) -> None:
    """This command lets you inside"""
    await send_message_both(
        ctx,
        """>HACK_SUCCESSFUL
    >USE_ls_TO_ACCESS_FILES""",
    )


all_commands.append(porthack)
# This command should not get a / command version.


@commands.command(hidden=True)
async def ls(ctx: commands.Context) -> None:
    """This command scans bot and lets you into files of bot"""
    await send_message_both(
        ctx,
        """>1_DIRECTORY_FOUND
    >DIRECTORY:home
    >USE_cdhome_TO_ACCESS_FILES""",
    )


all_commands.append(ls)
# This command should not get a / command version.


@commands.command(hidden=True, name="cdhome", aliases=["cd_home"])
async def cd_home(ctx: commands.Context) -> None:
    """This command scans existing folders of bot and let's you access folder"""
    await send_message_both(
        ctx,
        """>ONE_DIRECTORY_FOUND
    >File: README.txt
    >USE_catREADME_TO_VIEW_FILE_CONTENTS""",
    )


all_commands.append(cd_home)
# This command should not get a / command version.


# noinspection SpellCheckingInspection
@commands.command(
    hidden=True,
    name="catREADME",
    aliases=["cat_readme", "cat_README.txt", "catREADME.txt"],
)
async def cat_readme(ctx: commands.Context) -> None:
    """This command shows what's inside of file"""
    await send_message_both(
        ctx,
        """VIEWING_File:README.txt
    >Congratz! You found Hacknet Easter egg;
    >The Easter egg code was written by: Gh0st4rt1st a.k.a Gr3ta;
    >Code was edited by: gfrewqpoiu;
    >The Easter egg code is based on the Hacknet game;
    >Have a nice day! *Gh0st4rt1st* *x0x0* """,
    )


all_commands.append(cat_readme)
# This command should not get a / command version.


async def repeat_message_anyio(
    ctx: Context,
    message: str,
    amount: int = 10,
    sleep_time: int = 30,
    use_tts: bool = True,
) -> None:
    """This repeats a given message amount times with a sleep_time second break in between."""
    if amount < 1:
        raise ValueError("Amount must be at least 1.")
    if sleep_time < 0.5:
        raise ValueError("Must sleep for at least 0.5 seconds between messages.")
    run = 0
    while True:
        await send_message_both(ctx, message, tts=use_tts)
        run += 1
        if run >= amount:
            break
        await sleep_both(sleep_time)


# noinspection SpellCheckingInspection
@commands.command(hidden=True, name="annoyeveryone")
async def annoy_everyone(ctx: Context, amount: int = 10, sleep_time: int = 30) -> None:
    """This is just made to annoy people."""
    if amount > 10:
        await send_message_both(ctx, "Too many repetitions. Maximum is 10.")
        return
    if sleep_time > 5 * 60:
        await send_message_both(
            ctx, "Too much sleep time. Maximum 5 minutes so 300 seconds."
        )
        return
    if amount * sleep_time > 15 * 60 - 10:
        await send_message_both(
            ctx, "This would run for too long. Maximum is ~15 Minutes."
        )
        return
    await repeat_message_anyio(
        ctx,
        "Don't you like it when your cat goes: Meow. Meow? Meow! Meow. Meow "
        "Meow. Meow? Meow! Meow. Meow Meow? Meow! Meow. Meow",
        amount=amount,
        sleep_time=sleep_time,
        use_tts=True,
    )


all_commands.append(annoy_everyone)
all_slash_commands.append(
    SlashCommandInfo(
        command=annoy_everyone,
        name="annoyeveryone",
        description="Regularly posts a long tts message into this chat.",
        options=[
            manage_commands.create_option(
                name="amount",
                description="How often the message should be repeated. Maximum 10 times.",
                option_type=4,
                required=False,
            ),
            manage_commands.create_option(
                name="sleep_time",
                description="How long should the bot wait between messages in seconds. Maximum 300.",
                option_type=4,
                required=False,
            ),
        ],
    )
)


@commands.command(hidden=False)
async def tts(ctx: Context) -> None:
    """Says a funny tts phrase once."""
    await repeat_message_anyio(
        ctx,
        "Don't you just hate it when your cat wakes you up like this? Meow. Meow. "
        "Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. "
        "Meow. Meow. Meow. Meow. Meow. Meow.",
        amount=1,
        sleep_time=20,
        use_tts=True,
    )


all_commands.append(tts)
# This command should not get a / command version.


async def _add_quote_anyio(ctx: Context, keyword: str, quote_text: str) -> None:
    """Actually adds a quote to the database using anyio."""
    if ctx.message.guild is None:
        raise ValueError("We don't have any guild ID!")
    quote = Quote(
        guildId=ctx.message.guild.id,
        keyword=keyword.lower(),
        result=quote_text,
        authorId=ctx.author.id,
    )
    await anyio.to_thread.run_sync(quote.save)
    logger.success(
        f"Added quote {keyword.lower()} with text: {quote_text} for guild: {ctx.message.guild} by {ctx.author.name}"
    )
    # The reasoning for moving it to a separate thread is to not block the main loop for database access.


@commands.command(aliases=["addq"])
@commands.has_permissions(manage_messages=True)
async def addquote(ctx: Context, keyword: str, *, quote_text: str) -> None:
    """Adds a quote to the database.

    Specify the keyword in "" if it has spaces in it.
    Like this: addquote "key message" Reacting Text"""
    assert ctx.author.permissions_in(ctx.channel).manage_messages
    if len(keyword) < 1 or len(quote_text) < 1:
        await send_message_both(ctx, "Keyword or quote text missing")
        return
    assert bot is not None
    if (
        keyword[0] in punctuation
        or quote_text[0] in punctuation
        or keyword.startswith(bot.command_prefix)
        or quote_text.startswith(bot.command_prefix)
    ):
        await send_message_both(
            ctx,
            "Neither the Keyword nor the quote text can start with punctuation to avoid running bot commands.",
        )
        return
    await _add_quote_anyio(ctx, keyword, quote_text)
    await send_message_both(ctx, "I saved the quote.")


all_commands.append(addquote)
all_slash_commands.append(
    SlashCommandInfo(
        command=addquote,
        name="addquote",
        description="Adds a quote to the bot.",
        options=[
            manage_commands.create_option(
                name="keyword",
                description="What should trigger the quote.",
                option_type=3,
                required=True,
            ),
            manage_commands.create_option(
                name="quote_text",
                description="The quote itself.",
                option_type=3,
                required=True,
            ),
        ],
    )
)


@commands.command(aliases=["addgq", "addgquote"], name="addglobalquote", hidden=True)
@is_in_owners()
async def add_global_quote(
    ctx: commands.Context, keyword: str, *, quote_text: str
) -> None:
    """Adds a global quote to the database.

    Specify the keyword in "" if it has spaces in it.
    Like this: addgq "key message" Reacting Text"""
    assert ctx.author.id in configOwner
    if len(keyword) < 1 or len(quote_text) < 1:
        await send_message_both(ctx, "Keyword or quote text missing")
        return
    if keyword[0] in punctuation or quote_text[0] in punctuation:
        await send_message_both(
            ctx,
            "Neither the Keyword nor the quote text can start with punctuation to avoid running bot commands.",
        )
        return
    await _add_global_quote_anyio(keyword, quote_text, ctx.author)
    await send_message_both(ctx, "I saved the quote.")


all_commands.append(add_global_quote)
# This command should not get a / command version.


@commands.command(hidden=False, aliases=["delq", "delquote"])
@commands.has_permissions(manage_messages=True)
async def deletequote(ctx: Context, keyword: str) -> None:
    """Deletes the quote with the given keyword.

    If the keyword has spaces in it, it must be quoted like this:
    deletequote "Keyword with spaces"
    Only works for people that can delete messages in this server."""
    assert ctx.guild is not None
    assert ctx.author.permissions_in(ctx.channel).manage_messages
    quote = Quote.get_or_none(
        Quote.guildId == ctx.guild.id, Quote.keyword == keyword.lower()
    )
    if quote:
        quote.delete_instance()
        await send_message_both(ctx, "The quote was deleted.")
    else:
        await send_message_both(ctx, "I could not find the quote.")


all_commands.append(deletequote)
# This command should not get a / command version.


@commands.command(hidden=False, aliases=["liqu"], name="listquotes")
async def list_quotes(ctx: Context) -> None:
    """Lists all quotes on the current server."""
    result = ""
    if ctx.guild is None:
        await send_message_both(ctx, "You cannot run this command in a PM Channel.")
        return
    query = Quote.select(Quote.keyword).where(ctx.guild.id == Quote.guildId)
    results = await anyio.to_thread.run_sync(query.execute)
    for quote in results:
        result = result + str(quote.keyword) + "; "
    if result != "":
        await send_message_both(ctx, result)
    else:
        await send_message_both(ctx, "I couldn't find any quotes on this server.")


all_commands.append(list_quotes)
all_slash_commands.append(
    SlashCommandInfo(
        command=list_quotes,
        name="listquotes",
        description="Lists all quotes of this server.",
        options=[],
    )
)


@commands.command(hidden=True, aliases=["eval"])
@is_in_owners()
async def evaluate(ctx: Context, *, message: str) -> None:
    """Evaluates an arbitrary python expression.

    Checking a variable can be done with return var."""
    assert ctx.author.id in configOwner
    # if ctx.message.author.id != 167311142744489984:
    #     await send_message_both(
    #         ctx,
    #         """"This command is only for gfrewqpoiu.
    #     It is meant for testing purposes only.""",
    #     )
    #     return
    embed = discord.Embed()
    embed.set_author(name="Result")
    embed.set_footer(text=eval(message))
    await ctx.send(embed=embed)


all_commands.append(evaluate)
# This command should not get a / command version.


@commands.command(hidden=True, aliases=["leave_server, leave", "leaveguild"])
@is_in_owners()
async def leave_guild(ctx: Context, guild_id: int) -> None:
    """Leaves the server with the given ID."""
    assert bot is not None
    assert ctx.author.id in configOwner
    try:
        guild = bot.get_guild(guild_id)
        if guild is None:
            raise ValueError("Couldn't find a guild with that ID that I am a part of.")
        await guild.leave()
        await send_message_both(ctx, "I left that Guild.")
    except DiscordException as ex:
        logger.exception(ex)
        raise ex


all_commands.append(leave_guild)
# This command should not get a / command version.


@commands.command(hidden=False)
async def glitch(ctx: Context) -> None:
    """The second Easter Egg"""
    assert bot is not None
    await send_message_both(
        ctx,
        """Who created Walkers Join book?
    a ME;
    b FART;
    c Caro and Helryon;

    You have 15 seconds to respond. Respond with a, b or c""",
    )
    author = ctx.author
    channel = ctx.message.channel

    def check(message: discord.Message) -> bool:
        text = message.clean_content.strip().lower()
        answers = ["a", "b", "c"]
        return (
            text in answers and author == message.author and channel == message.channel
        )

    try:
        tripped = await wait_for_event_both("message", timeout=15.0, check=check)
        answer = tripped.clean_content.lower()
        if answer != "c":
            await send_message_both(ctx, "Wrong answer!")
        else:
            await send_message_both(ctx, "That is the correct answer!")
    except asyncio.TimeoutError:
        await send_message_both(ctx, "Time is up!")
        return


all_commands.append(glitch)
# This command should not get a / command version.


@commands.command(hidden=True)
@is_in_owners()
async def help2(ctx: Context) -> None:
    """Modified Help Command that shows all commands."""
    assert bot is not None
    assert ctx.author.id in configOwner
    try:
        bot.help_command.show_hidden = True
        cmd = bot.help_command

        if cmd is None:
            return None

        cmd.context = ctx
        await cmd.prepare_help_command(ctx, None)
        mapping = cmd.get_bot_mapping()
        injected = cmd.send_bot_help
        try:
            await injected(mapping)
        except discord.DiscordException as ex:
            logger.exception(ex)
            await cmd.on_help_command_error(ctx, ex)
    finally:
        bot.help_command.show_hidden = False


all_commands.append(help2)
# This command should not get a / command version.


# noinspection SpellCheckingInspection
async def _say_everywhere_anyio(
    ctx: Context, message: str, use_tts: bool = False, delete_after: int = 20
) -> None:
    important_patterns_startswith = ["rule", "welc"]
    important_patterns_everywhere = ["announc", "offici", "partne", "verifi"]
    important_patterns = [f"^{re.escape(i)}" for i in important_patterns_startswith]
    important_patterns.extend(re.escape(i) for i in important_patterns_everywhere)
    important_regex = re.compile("|".join(important_patterns), re.I)

    # noinspection PyShadowingNames
    def is_important_channel(channel: discord.TextChannel) -> bool:
        return bool(important_regex.search(channel.name.lower()))

    async with anyio.create_task_group() as task_group:
        for channel in ctx.guild.channels:
            if isinstance(channel, discord.TextChannel) and not is_important_channel(
                channel
            ):
                task = partial(
                    send_message_both,
                    channel,
                    message,
                    tts=use_tts,
                    delete_after=delete_after,
                    # allowed_mentions=discord.AllowedMentions(
                    #     everyone=False, users=[ctx.author], roles=False, replied_user=True
                    # ),
                )
                task_group.start_soon(task)


# noinspection PyShadowingNames
@commands.command(hidden=True, name="sayeverywhere", aliases=["say_everywhere"])
async def say_everywhere(
    ctx: Context, *, message: str, tts: bool = False, delete_after: int = 20
) -> None:
    """Says the message everywhere on this server."""
    assert ctx.guild is not None
    assert ctx.author.id in configOwner
    await _say_everywhere_anyio(ctx, message, use_tts=tts, delete_after=delete_after)


all_commands.append(say_everywhere)
all_slash_commands.append(
    SlashCommandInfo(
        command=say_everywhere,
        name="sayeverywhere",
        description="Says the message everywhere in this server (Owner Only)",
        options=[
            manage_commands.create_option(
                name="message",
                description="The message to send",
                option_type=3,
                required=True,
            ),
            manage_commands.create_option(
                name="tts",
                description="Whether to use tts",
                option_type=5,
                required=False,
            ),
            manage_commands.create_option(
                name="delete_after",
                description="When the messages should be deleted",
                option_type=4,
                required=False,
            ),
        ],
    )
)


async def setup_bot() -> None:
    global bot
    assert sniffio.current_async_library() == "asyncio"
    # noinspection PyArgumentList
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

    if all_slash_commands:
        slash = SlashCommand(bot, sync_commands=True)
        for slash_command in all_slash_commands:
            slash.add_slash_command(
                cmd=slash_command.command,
                name=slash_command.name,
                description=slash_command.description,
                options=slash_command.options,
            )


async def cycle_playing_status_anyio(period: int = 5 * 60) -> None:
    """Cycles the playing status of the bot every period seconds."""
    # noinspection SpellCheckingInspection
    statuses = [
        "making fun of Butler bot >:D",
        "poking Sky :p",
        "calling gfrew as Mr.Doot :D",
        "cuddling with Gh0st :D",
        "curiously poking Bird bot :o",
        "racing with Star :)",
        "planning to take over the world >:)",
        "planning to annoy Butler bot ;p",
        "annoying Lavio >:(",
        "screeching at Mee6 bot >:o",
        "Butler bot is rude >:(",
    ]
    await sleep_both(15)
    assert bot is not None
    await started_up_event.wait()
    while True:
        await sleep_both(period)
        if shutting_down_event.is_set():
            continue
        # noinspection PyBroadException
        try:
            await set_status_text_anyio(random.choice(statuses))
        except DiscordException:
            break
        except RuntimeError:
            break
        except aiohttp.ClientConnectionError:
            break


async def logging_task_anyio() -> None:
    """Sends a log message to the log channel."""
    while True:
        message = await log_recv_channel.receive()
        if not shutting_down_event.is_set():
            if log_channel is not None:
                await send_message_both(log_channel, message, True)
            await sleep_both(3)
        else:
            break


async def main() -> None:
    """This is the start point, this starts the bot and everything else. (asyncio)

    This function is using asyncio"""
    global global_task_group, started_up_event, shutting_down_event
    try:
        async with anyio.create_task_group() as task_group:
            # This is a nursery, it allows us to start Tasks that should run at the same time.
            started_up_event = anyio.Event()
            shutting_down_event = anyio.Event()
            await setup_bot()
            assert bot is not None
            logger.debug("Initializing Database.")
            await anyio.to_thread.run_sync(db.connect)
            await anyio.to_thread.run_sync(db.create_tables, [Quote])
            logger.debug("Database is initialized.")
            start_cmd = partial(bot.start, loginID, reconnect=True)
            global_task_group = task_group
            # These are no longer coroutines in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
            # noinspection PyAsyncCall
            task_group.start_soon(start_cmd)
            # noinspection PyAsyncCall
            task_group.start_soon(cycle_playing_status_anyio)
    except KeyboardInterrupt:
        if bot is not None:
            # This is no longer a coroutine in anyio >3.0.0 or in git version so we can suppress PyCharms warning.
            # noinspection PyAsyncCall
            shutting_down_event.set()
            logger.warning("Logging out the bot.")
            await bot.logout()
            raise SystemExit
    finally:
        logger.debug("Closing the Database connection.")
        await anyio.to_thread.run_sync(db.close)
        await logger.complete()


if __name__ == "__main__":
    """The code here only runs when you run this file using `pipenv run python bot.py`

    Or the shortcut `pipenv run bot`"""
    if debugging:
        logger.add(  # Here we add a logger to a log file.
            "Gretabot_debug.log",  # filename
            rotation="00:00",  # when should a new file be opened
            retention="3 days",  # how long to keep old files before they are deleted.
            backtrace=True,  # That shows all the functions that called the function that errored.
            diagnose=True,  # This means, show all variables when a Error occurs
            enqueue=True,  # Send all messages into a queue first, that is faster.
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

    for (
        attempt
    ) in Retrying(  # We will retry this part of the code when we get an error.
        wait=wait_fixed(60),  # Wait for 60 seconds before retrying.
        retry=(
            retry_if_exception_type(aiohttp.ClientConnectionError)
            # | retry_if_exception_type(trio.TrioInternalError)
        ),
        reraise=True,
    ):
        with attempt:
            try:
                anyio.run(main, backend="asyncio")
            except DiscordException as e:
                logger.exception(e)
                raise ValueError(
                    "Couldn't log in with the given credentials, please check those in config.ini"
                    " and your connection and try again!"
                )
