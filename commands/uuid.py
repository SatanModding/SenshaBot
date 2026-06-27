import inspect
import sys

import discord
from discord import app_commands

from bot import ModerationBot
from commands.base import Command
from helpers.uuid_handle import uuid_utils


class UUIDCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.cmd = None
        self.client = client_instance

    def get_slash_commands(self) -> list:
        @app_commands.command(name="uuid", description="Generate a random UUID.")
        async def uuid_command(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(
                f"your uuid is ```{uuid_utils().get()}```\nyou have `NaN` uuids left. use them wisely...", ephemeral=True
            )

        return [uuid_command]


classes = [("UUIDCommand", UUIDCommand)]
