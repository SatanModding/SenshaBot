import asyncio
import re
import time

import discord

PLAIN_EMOTE_PATTERN = re.compile(r"(?<!<a)(?<!<):([a-zA-Z0-9_]+):(?!\d+>)")
ESCAPED_EMOTE_PATTERN = re.compile(r"&lt;(a?):([a-zA-Z0-9_]+):(\d+)&gt;")
RAW_EMOTE_PATTERN = re.compile(r"<(a?):([a-zA-Z0-9_]+):(\d+)>")
APPLICATION_EMOJI_CACHE_SECONDS = 300


def _get_cached_application_emojis(client):
    return getattr(client, "_application_emojis_by_name", {}), getattr(
        client,
        "_application_emojis_by_id",
        {},
    )


def _emoji_matches(emoji, name, emoji_id=None) -> bool:
    if emoji_id is not None and str(emoji.id) == str(emoji_id):
        return True
    return emoji.name == name


def _pick_emoji(emojis, name, emoji_id=None):
    fallback_emoji = None

    for emoji in emojis:
        if not _emoji_matches(emoji, name, emoji_id):
            continue

        if fallback_emoji is None:
            fallback_emoji = emoji

        try:
            if emoji.is_usable():
                return emoji
        except Exception:
            return emoji

    return fallback_emoji


async def refresh_application_emojis(client, force: bool = False) -> None:
    if not hasattr(client, "fetch_application_emojis"):
        return

    now = time.time()
    cached_by_name, _ = _get_cached_application_emojis(client)
    last_update = getattr(client, "_application_emojis_updated", 0.0)

    if (
        not force
        and cached_by_name
        and (now - last_update) < APPLICATION_EMOJI_CACHE_SECONDS
    ):
        return

    if not hasattr(client, "_application_emojis_lock"):
        client._application_emojis_lock = asyncio.Lock()

    async with client._application_emojis_lock:
        cached_by_name, _ = _get_cached_application_emojis(client)
        last_update = getattr(client, "_application_emojis_updated", 0.0)
        now = time.time()

        if (
            not force
            and cached_by_name
            and (now - last_update) < APPLICATION_EMOJI_CACHE_SECONDS
        ):
            return

        try:
            application_emojis = await client.fetch_application_emojis()
        except (
            discord.HTTPException,
            discord.MissingApplicationID,
            AttributeError,
        ):
            return

        emojis_by_name = {}
        emojis_by_id = {}

        for emoji in application_emojis:
            emojis_by_name[emoji.name] = emoji
            emojis_by_id[str(emoji.id)] = emoji

        client._application_emojis_by_name = emojis_by_name
        client._application_emojis_by_id = emojis_by_id
        client._application_emojis_updated = now


def find_custom_emoji(
    name,
    client,
    guild: discord.Guild | None = None,
    emoji_id: str | None = None,
):
    """Find a custom emoji by name or ID, preferring the current guild."""
    if guild is not None:
        emoji = _pick_emoji(guild.emojis, name, emoji_id)
        if emoji is not None:
            return emoji

    emoji = _pick_emoji(client.emojis, name, emoji_id)
    if emoji is not None:
        return emoji

    cached_by_name, cached_by_id = _get_cached_application_emojis(client)
    if emoji_id is not None:
        emoji = cached_by_id.get(str(emoji_id))
        if emoji is not None:
            return emoji

    emoji = cached_by_name.get(name)
    if emoji is not None:
        return emoji

    return None


def get_custom_emoji(name, client, guild: discord.Guild | None = None):
    """Fetch a custom emoji by name and fall back to :name: if missing."""
    emoji = find_custom_emoji(name, client, guild)
    if emoji is not None:
        return str(emoji)
    return f":{name}:"


def parse_emotes_with_status(response, client, guild: discord.Guild | None = None):
    missing_emojis = []

    def replace_emote(match):
        emote_name = match.group(2)
        emote_id = match.group(3)

        emoji = find_custom_emoji(emote_name, client, guild, emote_id)
        if emoji is not None:
            return str(emoji)

        if emote_name not in missing_emojis:
            missing_emojis.append(emote_name)
        return f":{emote_name}:"

    def replace_plain_emote(match):
        emote_name = match.group(1)
        emoji = find_custom_emoji(emote_name, client, guild)
        if emoji is not None:
            return str(emoji)

        if emote_name not in missing_emojis:
            missing_emojis.append(emote_name)
        return f":{emote_name}:"

    parsed_response = re.sub(ESCAPED_EMOTE_PATTERN, replace_emote, response)
    parsed_response = re.sub(RAW_EMOTE_PATTERN, replace_emote, parsed_response)
    parsed_response = re.sub(PLAIN_EMOTE_PATTERN, replace_plain_emote, parsed_response)

    return parsed_response, missing_emojis


# Reuse the function to parse and replace custom and bot-specific emotes
def parse_emotes(response, client, guild: discord.Guild | None = None):
    parsed_response, _ = parse_emotes_with_status(response, client, guild)
    return parsed_response


async def parse_emotes_with_status_async(
    response,
    client,
    guild: discord.Guild | None = None,
):
    await refresh_application_emojis(client)
    return parse_emotes_with_status(response, client, guild)


async def parse_emotes_async(response, client, guild: discord.Guild | None = None):
    parsed_response, _ = await parse_emotes_with_status_async(response, client, guild)
    return parsed_response
