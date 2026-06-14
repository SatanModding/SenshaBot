import inspect
import sys

import discord
from discord import app_commands

from bot import ModerationBot
from commands.base import Command
from helpers.uuid_handle import handle_utils


# commandle if youre nasty >:D
class HandleCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.cmd = None
        self.client = client_instance

    def get_slash_commands(self) -> list:
        @app_commands.command(name="handle", description="Generate a random handle")
        async def handle_command(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(
                f"your handle is ```{handle_utils().get_handle()}```", ephemeral=True
            )

        return [handle_command]


classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
