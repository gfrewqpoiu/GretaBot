import configparser
from discord.ext import commands

config = configparser.ConfigParser()
config.read("config.ini")

settings = config["Settings"]


configOwnerstr = settings.get("Owner ID").split(" ")
configOwner = []
for s in configOwnerstr:
    configOwner.append(int(s))


def getconf():
    return config


def is_in_owners():
    def predicate(ctx):
        return ctx.author.id in configOwner

    return commands.check(predicate)


def is_main_owner():
    def predicate(ctx):
        return ctx.author.id == configOwner[0]

    return commands.check(predicate)


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
