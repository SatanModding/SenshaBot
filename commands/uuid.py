import inspect
import sys

import discord
from discord import app_commands

from bot import ModerationBot
from commands.base import Command
from helpers.uuid_handle import uuid_utils


class UuidCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.client = client_instance

    def get_slash_commands(self) -> list:
        @app_commands.command(name="uuid", description="Generate a random UUID.")
        async def uuid_command(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(
                f"your handle is ```{uuid_utils().get_uuid()}```", ephemeral=True
            )

        return [uuid_command]


classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
