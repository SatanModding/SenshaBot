import inspect
import sys

import discord

from bot import ModerationBot
from commands.base import Command
from helpers.uuid_handle import handle_utils


# commandle if youre nasty >:D
class HandleCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.cmd = "handle"
        self.client = client_instance
        self.storage = client_instance.storage

    async def execute(self, message: discord.Message, **kwargs) -> None:
        print("generating handle")
        await message.reply(f"your handle is ```{handle_utils().get_handle()}```")


# Collects a list of classes in the file
classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
