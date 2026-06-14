import inspect
import sys
import uuid

import discord
from discord import app_commands

from bot import ModerationBot
from commands.base import Command


class UuidCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.client = client_instance
        self.cmd = None

    def get_slash_commands(self) -> list:
        @app_commands.command(name="uuid", description="Generate a random UUID.")
        async def uuid_command(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(f"`{str(uuid.uuid4())}`", ephemeral=True)

        return [uuid_command]


classes = inspect.getmembers(sys.modules[__name__], lambda member: inspect.isclass(member) and member.__module__ == __name__)
