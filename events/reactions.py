import inspect
import sys

from bot import ModerationBot
from tasks.starboard import Starboard

import discord
from events.base import EventHandler


class ReactionEvent(EventHandler):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.client = client_instance
        self.starboard = Starboard(client_instance)
        self.storage = client_instance.storage
        self.event = "on_raw_reaction_add"

    def get_custom_emoji(self, name):
        """Fetch the bot's custom emoji by name."""
        for emoji in self.client.emojis:
            if emoji.name == name:
                return str(emoji)
        return f":{name}:"

    async def handle(self, payload: discord.RawReactionActionEvent, *args, **kwargs) -> None:
        '''
        message_id = payload.message_id # the message id that got or lost a reaction
        user_id = payload.user_id  # The user ID who added the reaction or whose reaction was removed.
        channel_id = payload.channel_id # The channel ID where the reaction got added or removed.
        guild_id = payload.guild_id # Optional[int] – The guild ID where the reaction got added or removed, if applicable. Guild = server [CMTY]
        emoji = payload.emoji # The custom or unicode emoji being use
        '''

        channel = self.client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = self.client.get_user(payload.user_id)

        await self.starboard.on_reaction(payload)


# Collects a list of classes in the file
classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
