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
    #pip.main(['install', '--user', '--upgrade', 'discord.py[voice]'])
    _restart()

import checks
import logging
import subprocess

logging.basicConfig(level=logging.INFO)

config = checks.getconf()
login = config['Login']
settings = config['Settings']
loginID = login.get('Login Token')
bot_version = "0.4.0"
main_channel=None

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
    if message.author.bot:
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
    elif bot.user.mentioned_in(message):
        await bot.send_message(channel, f"Can I help you with anything?")
        yes = await bot.wait_for_message(timeout=10, author=message.author, content="yes")
        if yes:
            await bot.send_message(channel, f"Okay use the {bot.command_prefix}help command to get a list of my commands!")
            #await bot.command('help', )
        else:
            await bot.send_message(channel, f"""Oh my fucking GOD! Fuck you {message.author.mention}! >:c""")
    elif text == "<_>":
        await bot.send_message(channel, ">_<")
    elif text == ">_<":
        await bot.send_message(channel, "<_>")
    elif text == "oof":
        await bot.send_message(channel, "https://cdn.discordapp.com/attachments/412033002072178689/422739362929704970/New_Piskel_22.gif")
    elif text == "thot":
        await bot.send_message(channel, "https://cdn.discordapp.com/attachments/343693498752565248/465931036384165888/tenor_1.gif")
    elif channel.is_private:
        if text[0]!=bot.command_prefix and main_channel is not None and channel.user.id in ['240224846217216000', '167311142744489984']:
            await bot.send_message(main_channel,text)
    else:
        await bot.process_commands(message)

@bot.command(hidden=True)
async def invite():
    await bot.say(f"https://discordapp.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions=8")

@bot.event
async def on_reaction(reaction, user):
    pass
    # if reaction == ":star:":
    #    await bot.send_message(channel, "test")
    
    # else:
    #    await bot.process_commands(message)

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



@bot.command(pass_context=True, hidden=True)
@commands.has_permissions(administrator=True)
async def update(ctx):
    """Updates the bot with the newest Version from GitHub
        Only works for the bot owner"""
    await bot.say("Ok, I am updating from GitHub")
    import pip
    #pip.main(['install', '--user', '--upgrade', 'discord.py[voice]'])
    try:
        output = subprocess.run(["git", "pull"], stdout=subprocess.PIPE)
        embed = discord.Embed()
        embed.set_author(name="Output:")
        embed.set_footer(text=output.stdout.decode('utf-8'))
        await bot.send_message(ctx.message.channel, embed=embed)
    except:
        await bot.say("That didn't work for some reason")



@bot.command(pass_context=True, hidden=True, aliases=['reboot'])
@commands.has_permissions(administrator=True)
async def restart(ctx):
    """Restart the bot
    Only works for the bot owner"""
    await bot.say("Restarting", delete_after=3)
    await asyncio.sleep(5)
    print(f"Restarting on request of {ctx.message.author.name}!")
    await bot.close()
    _restart()


@bot.command(pass_context=True, hidden=True, aliases=['setgame', 'setplaying'])
@commands.has_permissions(administrator=True)
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

@bot.command(pass_context=True, hidden=True)
@commands.has_permissions(administrator=True)
async def say2(ctx, *, message:str):
    """Repeats what you said and removes it"""
    await bot.delete_message(ctx.message)
    await bot.say(message)

@bot.command(pass_context=True, hidden=True)
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    """Sets the channel for PM messaging"""
    global main_channel
    main_channel=ctx.message.channel
    await bot.delete_message(ctx.message)


@bot.command(pass_context=True)
@commands.has_permissions(kick_members=True)
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


@bot.command(pass_context=True)
@commands.has_permissions(ban_members=True)
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
    *~To see what commands I can perform, use `{bot.command_prefix}help`.
    *~My version currently is: {bot_version} .
    *~I was made in: 
    Country: Lithuania;
    City/Town: Biržai and Klaipėda;
    *~Porting from js to py was done in:
    Country: Germany;
    City/Town: Munich. 
    
    Fun facts:
    1.)S.A.I.L name comes from Starbound game's AI character S.A.I.L
    2.)S.A.I.L stands for Ship-based Artificial Intelligence Lattice"""

    await bot.say(message)


@bot.command(pass_context=True, aliases=['prune', 'delmsgs'])
@commands.has_permissions(manage_messages=True)
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
    await bot.say(""">R3DACT3D
    >L1NK_R3M0V3D? = yes""")

@bot.command(hidden=False)
async def walkersjoin():
    """A link to 24/7 Walker's Radio on youtube"""
    await bot.say("https://www.youtube.com/watch?v=ruOlyWdUMSw")

@bot.command()
async def changes():
    """A command to show what has been added and/or removed from bot"""
    await bot.say("""The changes:
    0.4.0 -> **ADDED:** More Utility Commands
    0.3.0 -> **FIXED:** Broken permissions work now.
    0.2.0 -> **ADDED:** 
    *~tf2 & an - link commands; 
    *~extra reactions;
    *~change - updates command showing what was added/removed from bot;
    *~Special reaction w/ user tag
    This is the BETA Version of the SAIL bot.""")

@bot.command(hidden=False)
async def quotes():
    """Random stupid quotes"""
    await bot.say("""'robots making love-->dubstep' Alexy 2018;
    'Skype is idiot, Discord is a bitch' Gr3ta;
    *MORE STUPID QUOTES WILL BE ADDED LATER ON! Cuz why not? ( ͡° ͜ʖ ͡°)*""")

@bot.command(hidden=False)
async def UTBlobs():
    """Provides invite link to Undertale Blobs Discord server"""
    await bot.say("https://discord.gg/XQfqsbq")

@bot.command(hidden=False)
async def N_S():
    """Just work in progress easter egg"""
    await bot.say(">N0T_Y3T_4ADD3D,_T0_B3_C0NTINU3D")

@bot.command(hidden=True)
async def FreeNitro():
    """Free Discord Nitro"""
    await bot.reply(""">H4PPY_E4STER
    >HERE'S YOUR N1TRO SUBSCRIPTION:
    <https://is.gd/GetFreeNitro>
    >YOURS: Gh0st4rt1st_x0x0""")

@bot.command(hidden=False)
async def probe():
    """Use this command to check for open ports (ps. this is first step command of Easter egg)"""
    await bot.say(""">1_OP3N_P0RT_H4D_B3EN_F0UND
    >US3_ssh_T0_CR4CK_1T""")

@bot.command(hidden=True)
async def ssh():
    """This command hacks the port"""
    await bot.say(""">CR4CKING_SUCC3SSFUL
    >US3_porthack_T0_G4IN_4CC3SS""")

@bot.command(hidden=True)
async def porthack():
    """This command lets you inside"""
    await bot.say(""">H4CK_SUCC3SSFUL
    >US3_ls_T0_4CCESS_FILES""")

@bot.command(hidden=True)
async def ls():
    """This command scans bot and lets you into files of bot"""
    await bot.say(""">1_D1R3CT0RY_F0UND
    >D1R3CT0RY:home
    >US3_cdhome_T0_4CCESS_FILES""")

@bot.command(hidden=True)
async def cdhome():
    """This command sancs existing folders of bot and let's you access folder"""
    await bot.say(""">0N3_D1R3CT0RY_F0UND
    >File: README.txt
    >US3_catREADME_T0_V1EW_F1L3_C0NT3NTS""")

@bot.command(hidden=True)
async def catREADME():
    """This command shows what's inside of file"""
    await bot.say("""VI3WING_F1E:README.txt
    >Congratz! You found Hacknet Easter egg;
    >The Easter egg code was written by: Gh0st4rt1st a.k.a Gr3ta;
    >Code was edited by: gfrewqpoiu;
    >The Easter egg code is based on Hacknet game;
    >Have a nice day! *Gh0st4rt1st* *x0x0* """)

@bot.command(hidden=True)
async def annoyeveryone():
    for i in range(10):
            await bot.say("Don't you like it when your cat goes: Meow. Meow? Meow! Meow. Meow Meow. Meow? Meow! Meow. Meow Meow? Meow! Meow. Meow",  tts=True)
            await asyncio.sleep(30)
            
@bot.command(hidden=True)
async def tts():
    for i in range(10):
        await bot.say("Don't you just hate it when your cat wakes you up like this? Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow. Meow.", tts=True)
        await asyncio.sleep(30)

try:
    bot.run(loginID)
except:
    raise ValueError(
        "Couldn't log in with the given credentials, please check those in config.ini"
        " and your connection and try again!")
