import re
import discord

PLAIN_EMOTE_PATTERN = re.compile(r"(?<!<a)(?<!<):([a-zA-Z0-9_]+):(?!\d+>)")
ESCAPED_EMOTE_PATTERN = re.compile(r"&lt;(a?):([a-zA-Z0-9_]+):(\d+)&gt;")


def find_custom_emoji(name, client, guild: discord.Guild | None = None):
    """Find a custom emoji by name, preferring the current guild when available."""
    if guild is not None:
        for emoji in guild.emojis:
            if emoji.name == name:
                return emoji

    for emoji in client.emojis:
        if emoji.name == name:
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
        is_animated = match.group(1) == "a"  # Check if it's animated
        emote_name = match.group(2)
        emote_id = match.group(3)

        emoji = find_custom_emoji(emote_name, client, guild)
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
    parsed_response = re.sub(PLAIN_EMOTE_PATTERN, replace_plain_emote, parsed_response)

    return parsed_response, missing_emojis


# Reuse the function to parse and replace custom and bot-specific emotes
def parse_emotes(response, client, guild: discord.Guild | None = None):
    parsed_response, _ = parse_emotes_with_status(response, client, guild)
    return parsed_response
