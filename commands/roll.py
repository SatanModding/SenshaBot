import random
import inspect
import sys
import time
import json 
import re 

import discord

from bot import ModerationBot
from commands.base import Command
from datetime import datetime
from datetime import timedelta
from commands.mute import timeoutCommand
from commands.ban import TempBanCommand
from commands.dm import DMCommand
from helpers.embed_builder import EmbedBuilder
from helpers.misc_functions import (author_is_mod, is_integer,
                                    is_valid_duration, parse_duration)


from helpers.userid_parser import parse_userid

from helpers.emoji_parser import parse_emotes


class RollCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.cmd = "roll"
        self.client = client_instance
        self.storage = client_instance.storage
        self.usage = f"Usage: {self.client.prefix}roll"
        self.roll_counter = 0  # Counter to track the number of rolls

    def get_custom_emoji(self, name):
        """Fetch the bot's custom emoji by name."""
        for emoji in self.client.emojis:
            if emoji.name == name:
                return str(emoji) 
        return f":{name}:"  # Fallback in case the emoji is not found

    def get_forced_roll(self):
        """Force a roll of 1 or 20 based on a condition."""
        # Alternate between forcing 1 or 20
        return 1 if self.roll_counter % 2 == 0 else 20
    
    def d20_roll(self):
        # Every 10th roll, force a 1 or 20
        if self.roll_counter % 10 == 0:
            return self.get_forced_roll()
        return random.randint(1,20)
    
    def custom_roll(self, num_dice, dice_size):
        rolls = [random.randint(1, dice_size) for _ in range(num_dice)]
        return sum(rolls)

    async def execute(self, message: discord.Message, **kwargs) -> None:
        response = ""
        roll = None

        args = kwargs.get("args", [])
        rollParams = args[0].lower() if args and args[0] else None

        if rollParams:
            if rollParams == "coin":
                roll = random.randint(1,2)
                if roll == 1:
                    roll = "Head"
                else:
                    roll = "Tail"
            else:   
                match = re.fullmatch(r"(\d+)d(\d+)", rollParams)

                if not match:
                    await message.channel.send("Use XdY Format! (2d6, 1d20)")
                    return

                num_dice = int(match.group(1))
                dice_size = int(match.group(2))

                if num_dice == 0 and dice_size == 0:
                    await message.channel.send("Why are you making me do this?")
                    return
                if num_dice == 0:
                    await message.channel.send("Just.. why?")
                    return
                if num_dice < 0:
                    await message.channel.send("Are you trying make reality collapse into itself, rolling negative amount of dice?!")
                    return
                elif num_dice > 100:
                    await message.channel.send("These are far too many dice you are trying to roll here, 100 at maximum should suffice!")
                    return
                elif dice_size <= 0:
                    await message.channel.send("I don't know what you are rolling but its not dice.")
                    return
                elif dice_size == 1:
                    await message.channel.send("Might as well just count how many dice you have.")
                    return
                elif dice_size > 1000:
                    await message.channel.send("Anything above 1000 sides are far too much. Those are real chonkers, some real badonkas!")
                    return
                
                roll = self.custom_roll(num_dice, dice_size)
        else:
            self.roll_counter += 1  # Increment the roll counter
            roll = self.d20_roll()

        # reset counter on natural crits to avoid back-to-back extremes by forced rolls
        if roll == 1 or roll == 20:
            self.roll_counter = 1

        user_id = message.author.id

        # Predefined rolls for specific users
        if user_id == 504374276334288896:
            roll = 1
            response = f"{self.get_custom_emoji('HaPoint')} you rolled a 1, critical simosas fail!"
        elif user_id == 219060288106921985:
            roll = 20
            response = f"{self.get_custom_emoji('pogcat')} Critical success! You dropped this Snesh: {self.get_custom_emoji('crown')}"
        elif user_id == 722476157714563073:
            roll = 1
            response = f"{self.get_custom_emoji('satanstarege')} you rolled a 1, loser!"

        if not response and not rollParams == "coin":
            # Get the emotes
            PointNLaugh = self.get_custom_emoji("PointNLaugh")
            pogowo = self.get_custom_emoji("pogowo")
            happynathyjump = self.get_custom_emoji("happynathyjump")
            hap = self.get_custom_emoji("hap")
            HaPoint = self.get_custom_emoji("HaPoint")
            fishap = self.get_custom_emoji("fishap")
            hapwiggle = self.get_custom_emoji("hapwiggle")
            pogcat = self.get_custom_emoji("pogcat")
            crown = self.get_custom_emoji("crown")
            pausecham = self.get_custom_emoji("pausecham")

            # Different outcomes based on the roll
            max_roll = num_dice * dice_size if rollParams else 20

            if roll == 69:
                response = "Nice"
            elif roll == 420:
                response = "Blaze it!"
            elif roll > 9000:
                response = f"Its over 9000!"
            elif roll == 1:
                response = f"{PointNLaugh} you rolled a 1, critical fail!"
            elif roll == 20 and not rollParams:
                response = f"{pogowo} Critical success! You dropped this: {crown}"
            elif roll == max_roll:
                response = f"{pogowo} Perfect roll! You hit the absolute limit: {crown}"
            else:
                percent = roll / max_roll

                if percent <= 0.10:
                    response = f"{PointNLaugh} Oof."
                elif percent <= 0.30:
                    response = f"{hap} rough, not your best moment."
                elif percent < 0.50:
                    response = f"{pausecham} could've gone worse, but probably better."
                elif percent == 0.50:
                    response = f"Straight center. I have no strong feelings one way or the other."
                elif percent <= 0.70:
                    response = f"{happynathyjump} not too bad! Probably passed that ability check!"
                elif percent <= 0.90:
                    response = f"{pogowo} strong roll!"
                else:
                    response = f"{crown} nice roll, almost had it!"

        # Send the final response
        if rollParams == "coin":
            await message.channel.send(f"{roll}!")
        else:
            await message.channel.send(f"You rolled a {roll}!")
        if response:
            await message.channel.send(response)


# Collects a list of classes in the file
classes = inspect.getmembers(sys.modules[__name__], lambda member: inspect.isclass(member) and member.__module__ == __name__)

