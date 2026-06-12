import inspect
import sys

import discord

from bot import ModerationBot
from commands.base import Command
from helpers.uuid_handle import uuid_utils


class UUIDCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.cmd = "uuid"
        self.client = client_instance
        self.storage = client_instance.storage

    async def execute(self, message: discord.Message, **kwargs) -> None:
        await message.reply(f"your uuid is ```{uuid_utils().get_uuid()}```")


# Collects a list of classes in the file
classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
