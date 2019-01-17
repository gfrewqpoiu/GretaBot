import configparser
from discord.ext import commands

config = configparser.ConfigParser()
config.read('config.ini')

settings = config['Settings']


configOwnerstr = settings.get('Owner ID').split(" ")
configOwner = []
for s in configOwnerstr:
    configOwner.append(int(s))

def getconf():
    return config

def is_owner_check(message):
    return message.author.id in configOwner

def is_in_owners():
    return commands.check(lambda ctx: is_owner_check(ctx.message))

def is_admin_check(message):
    if is_in_owners():
        return True
    return message.author.permissions_in(message.channel).administrator

def is_admin():
    return commands.check(lambda ctx: is_admin_check(ctx.message))

def is_mod_check(message):
    if is_admin():
        return True
    return message.author.permissions_in(message.channel).ban_members

def is_mod():
    return commands.check(lambda ctx: is_mod_check(ctx.message))