import inspect
import sys

import discord

from tasks.check_punishments import check_punishments

from events.base import EventHandler
from bot import ModerationBot
from helpers.emoji_parser import refresh_application_emojis


class ReadyEvent(EventHandler):
    def __init__(self, client_instance: ModerationBot):
        self.client = client_instance
        self.event = "on_ready"

    async def handle(self, *args, **kwargs) -> None:
        print(f"Logged in as {self.client.user}")

        # Start the storage management and setup the guilds we are connected to.
        await self.client.storage.init()

        # If you added the custom storage class from the developing guide, it would get initialized by this
        if hasattr(self.client, "config"):
            await self.client.config.init()

        for guild in self.client.guilds:
            await self.client.setup_guild(guild)

        if not self.client.slash_guild_sync_done:
            for guild in self.client.guilds:
                guild_object = discord.Object(id=guild.id)
                self.client.tree.clear_commands(guild=guild_object)
                for slash_command in self.client.slash_commands:
                    self.client.tree.add_command(
                        slash_command,
                        guild=guild_object,
                        override=True,
                    )
                await self.client.tree.sync(guild=guild_object)
                print(f"Synced slash commands to guild {guild.name} ({guild.id})")
            self.client.slash_guild_sync_done = True

        await refresh_application_emojis(self.client)

        # Register some tasks
        self.client.loop.create_task(check_punishments(self.client))




# Collects a list of classes in the file
classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
