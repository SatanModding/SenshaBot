import asyncio
import inspect
import sys
import json

import discord

from bot import ModerationBot


class Starboard():
    def __init__(self, client_instance: ModerationBot) -> None:
        self.client = client_instance
        self.storage = client_instance.storage
        # change this to 1394634902598713354 (#pin-overflow)  1511613516438704169 testing
        self.starboard_channel_id = 1394634902598713354

    # duplicate function from roll.py for testing -> fix
    def get_custom_emoji(self, name):
        """Fetch the bot's custom emoji by name."""
        for emoji in self.client.emojis:
            if emoji.name == name:
                return str(emoji)
        return f":{name}:"  # Fallback in case the emoji is not found

    # forwarding is currently not available in this API.
    # instead use embedding like dyno
    async def forward(self, message, channel):
        dyno_grey= 0x2f3136
        satan_green =0x368036

        link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"

        embed = discord.Embed(
            description=message.content or None,
            color= satan_green
        )

        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )

        embed.add_field(
            name="Original",
            value=f"[Jump to message]({link})",
            inline=False
        )


        # 1. Videos
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("video"):

                # Can error if video too large
                MAX_SIZE = 8 * 1024 * 1024  # 8MB conservative safe default - we can try increasing if necessary

                # if too large -> fallback to link
                if attachment.size > MAX_SIZE:
                    fallback_embed = embed.copy()

                    fallback_embed.add_field(
                        name="Video",
                        value=f"Too large to re-upload.\n[Open video]({attachment.url})",
                        inline=False
                    )

                    await channel.send(embed=fallback_embed)
                    return

                try:
                    file = await attachment.to_file()

                    await channel.send(
                        embed=embed,
                        file=file
                    )
                    return

                except discord.HTTPException as e:
                    # handles 413 + other upload failures
                    await channel.send(
                        content=f"Video upload failed, falling back to link: {attachment.url}",
                        embed=embed
                    )
                    return

        # 2. Image
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image"):
                embed.set_image(url=attachment.url)
                break

        # 3. Embed media
        if message.embeds:
            for e in message.embeds:

                # image embed
                if getattr(e, "image", None) and e.image:
                    embed.set_image(url=e.image.url)
                    break

                # thumbnail embed fallback
                if getattr(e, "thumbnail", None) and e.thumbnail:
                    embed.set_image(url=e.thumbnail.url)
                    break

                # external URL embeds (ü-tübe)
                if getattr(e, "url", None):
                    embed.add_field(
                        name="External link",
                        value=e.url,
                        inline=False
                    )

        # 4. final message
        await channel.send(embed=embed)

# TODO - blacklist locked channels (moderation,admin etc)
# TODO - fix rate limitation error

    # is fired when event reactions detects a reaction
    async def on_reaction(self, payload):
        coin_name = "CMTYcoin"
        threshold = 3
        coin = self.get_custom_emoji("CMTYcoin")
        og_channel = self.client.get_channel(payload.channel_id)
        message_id = payload.message_id
        message = await og_channel.fetch_message(message_id)
        user = self.client.get_user(payload.user_id)
        star_channel =  channel = self.client.get_channel(self.starboard_channel_id)

        guild_id = str(payload.guild_id)
        guild = self.storage.settings["guilds"][guild_id]
        already_posted = guild.setdefault("starboarded_messages", {})

        # If message has already been posted - ignore
        if message_id in already_posted:
            return


        # get number of reactions
        for reaction in message.reactions:
            # we only accept CMTYcoin reactions
            if type(reaction.emoji) == str:
                return
            elif reaction.emoji.name == coin_name:
                count = reaction.count
                # We use threshold of 3 reactions for starboard
                if count >= threshold:
                    # instead of sending forward
                    await self.forward(message, channel)

                    already_posted[message_id] = True
                    await self.storage.write_file_to_disk()
                    return

# Collects a list of classes in the file
classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
