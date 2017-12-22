#!/usr/bin/env python3
import sys
import os
try:  # These are mandatory.
    import discord
    from discord.ext import commands
    from discord import utils
    import asyncio
except:
    raise ModuleNotFoundError(
        "You don't have Discord.py installed, install it with "
        "'pip3 install --user --upgrade discord.py[voice]'")

import checks
import logging
import subprocess

logging.basicConfig(level=logging.INFO)

config = checks.getconf()
login = config['Login']
settings = config['Settings']
loginID = login.get('Login Token')
bot_version = "0.0.1"

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
    print(f"I am in {len(bot.get_all_channels())} channels")
    print('------')
    await bot.change_presence(game=discord.Game(name='my game'))

async def on_server_join(server):
    print(f"I just joined the server {server.name} with the ID {server.id}")

async def on_server_remove(server):
    print(f"I left the server {server.name} with the ID {server.id}")

@bot.command(hidden = True)
async def invite():
    await bot.say(f"https://discordapp.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions=8")

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

@checks.is_owner()
@bot.command(pass_context=True, hidden=True)
async def update(ctx):
    """Updates the bot with the newest Version from GitHub
        Only works for the bot owner account"""
    await bot.say("Ok, I am updating from GitHub")
    try:
        output = subprocess.run(["git", "pull"], stdout=subprocess.PIPE)
        embed = discord.Embed()
        embed.set_author(name="Output:")
        embed.set_footer(text=output.stdout.decode('utf-8'))
        await bot.send_message(ctx.message.channel, embed=embed)
    except:
        await bot.say("That didn't work for some reason")

@checks.is_owner()
@bot.command(pass_context=True, hidden=True, aliases=['reboot'])
async def restart(ctx):
    """Restart the bot
    Only works for the bot owner"""
    await bot.say("Restarting", delete_after=3)
    await asyncio.sleep(5)
    print(f"Restarting on request of {ctx.message.author.name}!")
    await bot.close()
    try:
        os.execl(sys.executable, sys.executable, *sys.argv)
    except:
        pass

try:
    bot.run(loginID)
except:
    raise ValueError(
        "Couldn't log in with the given credentials, please check those in config.ini"
        " and your connection and try again!")
