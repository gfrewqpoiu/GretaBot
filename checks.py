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