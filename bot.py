#!/usr/bin/env python3
import sys
import os
import pprint
def _restart():
    try:
        os.execl(sys.executable, sys.executable, *sys.argv)
    except:
        pass

try:  # These are mandatory.
    import discord
    from discord.ext import commands
    from discord import utils
    import asyncio
except ImportError:
    import pip
    pip.main(['install', '--user', '--upgrade', 'discord.py[voice]'])
    _restart()

import checks
import logging
import subprocess

logging.basicConfig(level=logging.INFO)

config = checks.getconf()
login = config['Login']
settings = config['Settings']
loginID = login.get('Login Token')
bot_version = "0.1.1"

bot = commands.Bot(command_prefix=settings.get('prefix', '.'),
                   description=settings.get('Bot Description', 'A WIP bot'), pm_help=True)

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print(f"Using Bot Version: {bot_version}")
    print('------')
    print("")
    print("I am part of the following servers:")
    for server in bot.servers:
        print(f"{server.name}")
    print("")
    amount = 0
    for channel in bot.get_all_channels():
        amount += 1
    print(f"I am in {amount} channels")
    print('------')
    await bot.change_presence(game=discord.Game(name='waiting'))

@bot.event
async def on_server_join(server):
    print(f"I just joined the server {server.name} with the ID {server.id}")

@bot.event
async def on_server_remove(server):
    print(f"I left the server {server.name} with the ID {server.id}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    text = message.clean_content
    channel = message.channel

    if text == "/o/":
        await bot.send_message(channel, "\o\\")
    elif text == "\o\\":
        await bot.send_message(channel, "/o/")
    elif text == ">_>":
        await bot.send_message(channel, "<_<")
    elif text == "<_<":
        await bot.send_message(channel, ">_>")
    elif text == "-_-":
        await bot.send_message(channel, "I am sorry that you are annoyed. I want you to be happy!")
    elif text == "-.-":
        await bot.send_message(channel, "Aww don't be so upsetti, have some spaghetti!")

    else:
        await bot.process_commands(message)

@bot.command(hidden=True)
async def invite():
    await bot.say(f"https://discordapp.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions=8")


@bot.command(hidden=True)
async def version():
    """Gives back the bot version"""
    await bot.say(bot_version)

#Utility Commands
@checks.is_owner()
@bot.command(pass_context=True, hidden=True, aliases=['stop'])
async def shutdown(ctx):
    """Shuts the bot down
    Only works for the bot owner"""
    await bot.say("Shutting down!", delete_after=3)
    await asyncio.sleep(5)
    print(f"Shutting down on request of {ctx.message.author.name}!")
    await bot.close()
    try:
        sys.exit()
    except:
        {}


@checks.is_admin()
@bot.command(pass_context=True, hidden=True)
async def update(ctx):
    """Updates the bot with the newest Version from GitHub
        Only works for the bot owner"""
    await bot.say("Ok, I am updating from GitHub")
    import pip
    pip.main(['install', '--user', '--upgrade', 'discord.py[voice]'])
    try:
        output = subprocess.run(["git", "pull"], stdout=subprocess.PIPE)
        embed = discord.Embed()
        embed.set_author(name="Output:")
        embed.set_footer(text=output.stdout.decode('utf-8'))
        await bot.send_message(ctx.message.channel, embed=embed)
    except:
        await bot.say("That didn't work for some reason")


@checks.is_admin()
@bot.command(pass_context=True, hidden=True, aliases=['reboot'])
async def restart(ctx):
    """Restart the bot
    Only works for the bot owner"""
    await bot.say("Restarting", delete_after=3)
    await asyncio.sleep(5)
    print(f"Restarting on request of {ctx.message.author.name}!")
    await bot.close()
    _restart()


@checks.is_admin()
@bot.command(pass_context=True, hidden=True, aliases=['setgame', 'setplaying'])
async def gametitle(ctx, *, message: str):
    """Sets the currently playing status of the bot"""
    if not ctx.message.author.permissions_in(ctx.message.channel).manage_nicknames:
        await bot.say("You don't have permission to do this")
        return
    await bot.change_presence(game=discord.Game(name=message))


@bot.command(pass_context=True)
async def ping(ctx):
    """Checks the ping of the bot"""
    m = await bot.say("Ping?")
    await bot.edit_message(m, f"Pong, Latency is {m.timestamp - ctx.message.timestamp}.")


@bot.command(hidden=True)
async def say(*, message:str):
    """Repeats what you said"""
    await bot.say(message)


@checks.is_mod()
@bot.command(pass_context=True)
async def kick(ctx):
    """Kicks the specified User"""
    if not ctx.message.author.permissions_in(ctx.message.channel).kick_members:
        await bot.say("You don't have permission to kick users")
        return
    user = ctx.message.mentions[0]
    if user==None:
        await bot.say("No user was specified")
        return
    try:
        await bot.kick(user)
        await bot.say("The user has been kicked from the server.")
    except:
        await bot.say("I couldn't kick that user.")


@checks.is_mod()
@bot.command(pass_context=True)
async def ban(ctx):
    """Bans the specified User"""
    user = ctx.message.mentions[0]
    if user == None:
        await bot.say("No user was specified")
        return
    try:
        await bot.ban(user)
        await bot.say("The user has been banned from the server.")
    except:
        await bot.say("I couldn't ban that user.")


@bot.command()
async def info():
    """Gives some info about the bot"""
    message = f"""📢
    Hello, I'm S.A.I.L, a Discord bot made for simple usage by Gr3ta a.k.a Gh0st4rt1st.
    *~Date when I was created: 2017-10-15.
    *~I was ported to Python by gfrewqpoiu on 2017-12-22.
    *~To see what commands I can perform, use `{bot.command_prefix}help`
    *~My version currently is: {bot_version}
    *~I was made in Lithuania, Biržai and Klaipėda, as well as Munich, Germany.
    
    Fun facts:
    1.)S.A.I.L name comes from Starbound game's AI character S.A.I.L
    2.)S.A.I.L stands for Ship-based Artificial Intelligence Lattice"""

    await bot.say(message)


@checks.is_mod()
@bot.command(pass_context=True, aliases=['prune', 'delmsgs'])
async def purge(ctx, amount: int):
    """Removes the given amount of messages from the given channel."""
    try:
        await bot.purge_from(ctx.message.channel, limit=amount+1)
    except discord.Forbidden:
        await bot.say("I couldn't do that because of missing permissions")


@bot.command(hidden=False)
async def tf2():
    """Funny Video"""
    await bot.say("https://www.youtube.com/watch?v=r-u4rA_yZTA")

@bot.command(hidden=False)
async def an():
    """A command giving link to A->N website"""
    await bot.say("http://approachingnirvana.com/")

@bot.command(hidden=False)
async def changes():
    """A command to show what has been added and/or removed from bot"""
    await bot.say(""""The changes:
    0.1.1 -> ADDED: tf2 & an - link commands; extra reactions.""")

try:
    bot.run(loginID)
except:
    raise ValueError(
        "Couldn't log in with the given credentials, please check those in config.ini"
        " and your connection and try again!")
