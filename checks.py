import configparser
from discord import Message
from discord.ext import commands
from typing import Any

config = configparser.ConfigParser()
config.read("config.ini")

settings = config["Settings"]


configOwnerstr = settings.get("Owner ID").split(" ")
configOwner = []
for s in configOwnerstr:
    configOwner.append(int(s))


def getconf() -> configparser.ConfigParser:
    """Returns the config"""
    return config


def is_in_owners() -> Any:
    """Checks, whether the author of the command is in the Owner List."""

    def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id in configOwner

    return commands.check(predicate)


def is_main_owner() -> Any:
    """Checks whether the command is run by the main owner (the first one from the config)"""

    def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == configOwner[0]

    return commands.check(predicate)


def is_admin_check(message: Message) -> Any:
    """Checks, whether the command is run by an admin."""
    if is_in_owners():
        return True
    return message.author.permissions_in(message.channel).administrator


def is_admin() -> Any:
    """Checks, whether the command is run by an admin."""
    return commands.check(lambda ctx: is_admin_check(ctx.message))


def is_mod_check(message: Message) -> bool:
    """Checks whether the command is run by a mod"""
    if is_admin():
        return True
    return message.author.permissions_in(message.channel).ban_members


def is_mod() -> Any:
    """Checks whether the command is run by a mod"""
    return commands.check(lambda ctx: is_mod_check(ctx.message))
