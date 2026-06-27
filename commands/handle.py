import inspect
import sys

import discord
from discord import app_commands

from bot import ModerationBot
from commands.base import Command
from helpers.emoji_parser import parse_emotes
from helpers.uuid_handle import handle_utils


# commandle if youre nasty >:D
class HandleCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.cmd = None
        self.client = client_instance

    def get_slash_commands(self) -> list:
        @app_commands.command(name="handle", description="Generate a random handle")
        async def handle_command(interaction: discord.Interaction) -> None:
            response = f"Your handle is: ```{handle_utils().get()}```\nHope you can... *handle* it. :peeposmile:"
            response = parse_emotes(response, self.client)
            await interaction.response.send_message(
                response, ephemeral=True
            )

        return [handle_command]


classes = [("HandleCommand", HandleCommand)]