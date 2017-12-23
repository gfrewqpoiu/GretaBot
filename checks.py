import configparser
from discord.ext import commands

config = configparser.ConfigParser()
config.read('config.ini')

settings = config['Settings']

configOwner = settings.get('Owner ID')

def getconf():
    return config

def is_owner_check(message):
    return message.author.id == configOwner

def is_owner():
    return commands.check(lambda ctx: is_owner_check(ctx.message))

def is_admin_check(message):
    if is_owner():
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