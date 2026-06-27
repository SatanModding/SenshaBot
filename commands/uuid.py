import secrets

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
            # always have fake_uuid_limit be at least 2 but as high as 20
            # that way its always plural and grammar wont need to change
            fake_uuid_limit = secrets.randbelow(19) + 2
            await interaction.response.send_message(
                f"your uuid is ```{uuid_utils().get()}```\nyou have {fake_uuid_limit} uuids left. use them wisely...",
                ephemeral=True,
            )

        return [uuid_command]


classes = [("UUIDCommand", UUIDCommand)]
