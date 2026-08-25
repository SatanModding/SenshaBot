
import inspect
import sys
import re
import discord

from bot import ModerationBot


class TemperatureConverter():
    def __init__(self, client_instance: ModerationBot) -> None:
        self.client = client_instance
        self.storage = client_instance.storage




    def  c_to_f(self, c):
        return (c*1,8) + 32

    def f_to_c(self, f):
        return (f - 32) / 1,8




    async def on_message(self, message: discord.Message):
        allowed_channel = 1511607247954903120 #senshabot fork test

        if message.channel.id != allowed_channel:
            return

        # matches various ways to type temperature (21C, 21 C, 21°C. 21 ° C. -3.5C)
        TEMP_REGEX = re.compile(
            r'(?P<value>-?\d+(?:\.\d+)?)\s*(?:°\s*)?(?P<unit>[cCfF])\b'
        )

        # check if message contains a temperature.

        matches = TEMP_REGEX.findall(message.content)
        if len(matches) >= 1:
            await message.channel.send(f"{len(matches)} temperature found {matches}")
            await message.channel.send(f"number {matches[0][0]}")
            await message.channel.send(f"format {matches[0][1]}")


# Collects a list of classes in the file
classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
