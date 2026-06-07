import inspect
import sys
import time

import discord

from bot import ModerationBot
from events.base import EventHandler
from helpers.emoji_parser import parse_emotes
from helpers.misc_functions import author_is_admin, author_is_mod
from helpers.response_management import (
    get_effective_setting,
    get_or_setup_responses,
    message_matches_response,
)


class AutoResponseEvent(EventHandler):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.client = client_instance
        self.storage = client_instance.storage
        self.event = "on_message"
        self.cooldowns = {}

    async def handle(self, message: discord.Message, *args, **kwargs) -> None:
        if message.author.bot or message.guild is None or not message.content:
            return

        if message.content.startswith(self.client.prefix):
            return

        guild_id = str(message.guild.id)
        response_store = await get_or_setup_responses(self.storage, guild_id)
        response_entries = response_store["entries"]

        if not response_entries:
            return

        sorted_responses = sorted(
            response_entries.values(),
            key=lambda response_def: (
                response_def.get("priority", 100),
                response_def.get("id", 0),
            ),
        )

        for response_def in sorted_responses:
            if not response_def.get("enabled", True):
                continue

            if await self.should_skip_message(message, response_store, response_def):
                continue

            if self.response_on_cooldown(
                message.guild.id,
                message.channel.id,
                response_store,
                response_def,
            ):
                continue

            if not message_matches_response(message.content, response_def):
                continue

            response_text = parse_emotes(
                response_def["response_text"],
                self.client,
                message.guild,
            )
            await message.channel.send(
                response_text,
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    users=True,
                    roles=True,
                    replied_user=False,
                ),
            )
            self.mark_cooldown(message.guild.id, message.channel.id, response_def)
            return

    async def should_skip_message(
        self,
        message: discord.Message,
        response_store: dict,
        response_def: dict,
    ) -> bool:
        ignore_mods = get_effective_setting(response_store, response_def, "ignore_mods")
        if ignore_mods and (
            author_is_admin(message.author)
            or await author_is_mod(message.author, self.storage)
        ):
            return True

        exempt_role_ids = get_effective_setting(
            response_store,
            response_def,
            "exempt_role_ids",
        )
        if exempt_role_ids:
            author_role_ids = [role.id for role in message.author.roles]
            if any(role_id in author_role_ids for role_id in exempt_role_ids):
                return True

        channel_whitelist = get_effective_setting(
            response_store,
            response_def,
            "channel_whitelist",
        )
        if channel_whitelist and message.channel.id not in channel_whitelist:
            return True

        channel_blacklist = get_effective_setting(
            response_store,
            response_def,
            "channel_blacklist",
        )
        if channel_blacklist and message.channel.id in channel_blacklist:
            return True

        return False

    def response_on_cooldown(
        self,
        guild_id: int,
        channel_id: int,
        response_store: dict,
        response_def: dict,
    ) -> bool:
        response_id = response_def["id"]
        guild_key = str(guild_id)
        channel_key = str(channel_id)
        cooldown_seconds = get_effective_setting(
            response_store,
            response_def,
            "cooldown_seconds",
        )
        if not cooldown_seconds:
            return False

        response_cooldowns = self.cooldowns.get(guild_key, {}).get(str(response_id), {})
        last_run = response_cooldowns.get(channel_key)
        if last_run is None:
            return False

        return last_run + cooldown_seconds > time.time()

    def mark_cooldown(self, guild_id: int, channel_id: int, response_def: dict) -> None:
        response_id = str(response_def["id"])
        guild_key = str(guild_id)
        channel_key = str(channel_id)

        if guild_key not in self.cooldowns:
            self.cooldowns[guild_key] = {}
        if response_id not in self.cooldowns[guild_key]:
            self.cooldowns[guild_key][response_id] = {}

        self.cooldowns[guild_key][response_id][channel_key] = time.time()


classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
