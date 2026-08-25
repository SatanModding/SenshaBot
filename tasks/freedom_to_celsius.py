
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
        return (c * 1.8) + 32

    def f_to_c(self, f):
        return (f - 32) / 1.8




    async def on_message(self, message: discord.Message):
        # allowed_channel = 1541891962955894835 #senshabot fork test 2

        #if message.channel.id != allowed_channel:
        #    return

        # matches various ways to type temperature (21C, 21 C, 21°C. 21 ° C. -3.5C) and comma versions
        TEMP_REGEX = re.compile(
            r'(?P<value>-?\d+(?:[.,]\d+)?)\s*(?:°\s*)?(?P<unit>[cCfF])\b'
        )

        # check if message contains a temperature.

        matches = TEMP_REGEX.findall(message.content)

        starting = "-# beep boop! I detected a temperature:"
        closing= "-# For now I can only convert Celsius <-> Fahrenheit! Feel free to send a ModMail if you want me to learn more!"

        if len(matches) >= 1:
            # collect all and only send one message cause delay
            messages = []
            for value, unit in matches:
                # we accept , and . as decimals. Convert to . so we can convert to floats
                num = float(value.replace(",", "."))

                old = f"{value}°{unit.upper()}"

                if unit.upper() == "F":
                    c = self.f_to_c(num)
                    new = f"{c:.0f}°C"
                    msg = f"{old} is {new} !"
                if unit.upper() == "C":
                    f = self.c_to_f(num)
                    new = f"{f:.0f}°F"
                    msg = f"{old} is {new} !"

                messages.append(msg)

            await message.channel.send(
                f"{starting}\n" + "\n".join(messages) + f"\n{closing}")

# Collects a list of classes in the file
classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
