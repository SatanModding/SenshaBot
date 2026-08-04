import asyncio
import inspect
import re
import sys

import discord
from discord import app_commands

from bot import ModerationBot
from commands.base import Command
from helpers.emoji_parser import parse_emotes_with_status_async
from helpers.misc_functions import author_is_admin, author_is_mod, is_integer
from helpers.response_management import (
    add_response,
    delete_response,
    get_effective_setting,
    get_or_setup_responses,
    get_response,
    get_response_settings,
    list_responses,
    toggle_response,
    update_response,
    update_response_settings,
)
from helpers.roleid_parser import parse_roleid


class ResponseListPageView(discord.ui.View):
    def __init__(self, author_id: int, create_embed, page_count: int) -> None:
        super().__init__(timeout=180)
        self.author_id = author_id
        self.create_embed = create_embed
        self.page_count = page_count
        self.current_page = 0
        self.sync_buttons()

    def sync_buttons(self) -> None:
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.page_count - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This is not for you.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        if self.current_page > 0:
            self.current_page -= 1
        self.sync_buttons()
        await interaction.response.edit_message(
            embed=self.create_embed(self.current_page), view=self
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        if self.current_page < self.page_count - 1:
            self.current_page += 1
        self.sync_buttons()
        await interaction.response.edit_message(
            embed=self.create_embed(self.current_page), view=self
        )


class ResponseCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.client = client_instance
        self.storage = client_instance.storage
        self.cmd = None
        self.invalid_response = "Sorry, that is not a valid response ID."
        self.no_permissions = "Only moderators and admins can set up responses."

    async def ensure_slash_permissions(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            await self.send_interaction_message(
                interaction,
                embed=self.make_error_embed(
                    "Guild only.", "This command only works in a server."
                ),
                ephemeral=True,
            )
            return False

        if author_is_admin(interaction.user) or await author_is_mod(
            interaction.user, self.storage
        ):
            return True

        await self.send_interaction_message(
            interaction,
            embed=self.make_error_embed("No permissions.", self.no_permissions),
            ephemeral=True,
        )
        return False

    async def send_interaction_message(
        self, interaction: discord.Interaction, **kwargs
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
            return
        await interaction.response.send_message(**kwargs)

    async def send_interaction_message_defer(
        self,
        interaction: discord.Interaction,
        sleep: int = 0,
        thinking: bool = True,
        **kwargs,
    ) -> None:
        ephemeral: bool = False
        if "ephemeral" in kwargs:
            ephemeral = kwargs["ephemeral"]

        await asyncio.sleep(sleep)
        await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)
        await interaction.followup.send(**kwargs)

    async def autocomplete_response_id(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        if interaction.guild is None:
            return []

        entries = await list_responses(self.storage, interaction.guild.id)
        response_items = sorted(
            entries.values(),
            key=lambda item: (item.get("priority", 100), item.get("id", 0)),
        )
        current = str(current).lower().strip()
        choices = []

        for response_def in response_items:
            response_id = response_def.get("id", 0)
            haystack = f"{response_id} {response_def.get('name', '')} {response_def.get('match_type', '')}".lower()
            if current and current not in haystack:
                continue
            choices.append(
                app_commands.Choice(
                    name=f"#{response_id} {response_def.get('name', 'Unnamed')} [{response_def.get('match_type', 'unknown')}]"[
                        :100
                    ],
                    value=response_id,
                )
            )
            if len(choices) >= 25:
                break

        return choices

    def parse_slash_override_text(self, text: str, parser):
        lowered_text = text.lower().strip()
        if lowered_text in {"setup", "skip", "default"}:
            return None
        if lowered_text == "none":
            return []
        return parser(text)

    def parse_slash_setting_list_text(self, text: str, parser):
        lowered_text = text.lower().strip()
        if lowered_text in {"setup", "skip", "default"}:
            raise ValueError("Use `none` to clear this setting, or leave it empty.")
        if lowered_text == "none":
            return []
        return parser(text)

    async def send_slash_response_list(self, interaction: discord.Interaction) -> None:
        entries = await list_responses(self.storage, interaction.guild.id)
        response_items = sorted(
            entries.values(),
            key=lambda item: (item.get("priority", 100), item.get("id", 0)),
        )

        if not response_items:
            await self.send_interaction_message_defer(
                interaction,
                embed=self.make_done_embed(
                    "No responses saved.", "Use `/response add` to make one."
                ),
                ephemeral=True,
            )
            return

        page_size = 8
        pages = [
            response_items[index : index + page_size]
            for index in range(0, len(response_items), page_size)
        ]

        def create_embed(page_index: int) -> discord.Embed:
            embed = discord.Embed(
                title=f"Auto Responses (Page {page_index + 1}/{len(pages)})",
                color=discord.Color.blue(),
            )
            for response_def in pages[page_index]:
                status = "On" if response_def.get("enabled", True) else "Off"
                embed.add_field(
                    name=f"#{response_def['id']} {response_def['name']}",
                    value=f"Type: `{response_def['match_type']}`\nPriority: `{response_def.get('priority', 100)}`\nStatus: `{status}`\nTriggers: `{len(response_def.get('triggers', []))}`",
                    inline=False,
                )
            embed.set_footer(text="Use /response view to see one entry.")
            return embed

        view = ResponseListPageView(interaction.user.id, create_embed, len(pages))
        await self.send_interaction_message_defer(
            interaction, embed=create_embed(0), view=view, ephemeral=True
        )

    def make_error_embed(self, title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=title, description=description, color=discord.Color.red()
        )

    def get_slash_commands(self) -> list:
        response_group = app_commands.Group(
            name="response", description="Manage auto responses."
        )
        match_type_choices = [
            app_commands.Choice(name="Word", value="word"),
            app_commands.Choice(name="Phrase", value="phrase"),
            app_commands.Choice(name="Emoji", value="emoji"),
            app_commands.Choice(name="Regex", value="regex"),
        ]
        ignore_mods_choices = [
            app_commands.Choice(name="Use setup", value="setup"),
            app_commands.Choice(name="True", value="true"),
            app_commands.Choice(name="False", value="false"),
        ]

        @response_group.command(
            name="setup", description="Set default response settings."
        )
        @app_commands.describe(
            ignore_mods="Default ignore moderators setting.",
            exempt_roles="Role mentions or IDs, comma separated. Use `none` to clear.",
            allowed_channels="Channel mentions or IDs, comma separated. Use `none` to allow all.",
            blocked_channels="Channel mentions or IDs, comma separated. Use `none` to clear.",
            cooldown_seconds="Default cooldown in seconds.",
        )
        async def setup_command(
            interaction: discord.Interaction,
            ignore_mods: bool | None = None,
            exempt_roles: str | None = None,
            allowed_channels: str | None = None,
            blocked_channels: str | None = None,
            cooldown_seconds: int | None = None,
        ) -> None:
            if not await self.ensure_slash_permissions(interaction):
                return

            current_settings = await get_response_settings(
                self.storage, interaction.guild.id
            )
            if all(
                value is None
                for value in (
                    ignore_mods,
                    exempt_roles,
                    allowed_channels,
                    blocked_channels,
                    cooldown_seconds,
                )
            ):
                embed = self.make_setup_intro_embed(interaction.guild, current_settings)
                embed.set_footer(
                    text="Set any slash parameters to update these defaults."
                )
                await self.send_interaction_message(
                    interaction, embed=embed, ephemeral=True
                )
                return

            try:
                new_settings = current_settings.copy()
                if ignore_mods is not None:
                    new_settings["ignore_mods"] = ignore_mods
                if exempt_roles is not None:
                    new_settings["exempt_role_ids"] = (
                        self.parse_slash_setting_list_text(
                            exempt_roles, self.parse_role_ids
                        )
                    )
                if allowed_channels is not None:
                    new_settings["channel_whitelist"] = (
                        self.parse_slash_setting_list_text(
                            allowed_channels, self.parse_channel_ids
                        )
                    )
                if blocked_channels is not None:
                    new_settings["channel_blacklist"] = (
                        self.parse_slash_setting_list_text(
                            blocked_channels, self.parse_channel_ids
                        )
                    )
                if cooldown_seconds is not None:
                    if cooldown_seconds < 0:
                        raise ValueError("Cooldown must be `0` or higher.")
                    new_settings["cooldown_seconds"] = cooldown_seconds
            except ValueError as error:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed("Invalid parameters.", str(error)),
                    ephemeral=True,
                )
                return

            await update_response_settings(
                self.storage, interaction.guild.id, new_settings
            )
            embed = self.make_setup_preview_embed(interaction.guild, new_settings)
            embed.title = "Response setup saved."
            embed.description = "The default response settings have been updated."
            await self.send_interaction_message(
                interaction, embed=embed, ephemeral=True
            )

        @response_group.command(name="add", description="Add a new auto response.")
        @app_commands.describe(
            match_type="How this response should match messages.",
            name="Short name for this response.",
            triggers="Comma separated triggers, or one regex pattern.",
            response_text="What the bot should post when this matches.",
            priority="Use `important`, `basic`, or `0-100`.",
            ignore_mods="Use setup, true, or false for this response.",
            exempt_roles="Role mentions or IDs, comma separated. Use `setup` or `none`.",
            allowed_channels="Channel mentions or IDs, comma separated. Use `setup` or `none`.",
            blocked_channels="Channel mentions or IDs, comma separated. Use `setup` or `none`.",
            cooldown_seconds="Cooldown override in seconds.",
        )
        @app_commands.choices(
            match_type=match_type_choices, ignore_mods=ignore_mods_choices
        )
        async def add_command(
            interaction: discord.Interaction,
            match_type: app_commands.Choice[str],
            name: str,
            triggers: str,
            response_text: str,
            priority: str | None = None,
            ignore_mods: app_commands.Choice[str] | None = None,
            exempt_roles: str | None = None,
            allowed_channels: str | None = None,
            blocked_channels: str | None = None,
            cooldown_seconds: int | None = None,
        ) -> None:
            if not await self.ensure_slash_permissions(interaction):
                return

            try:
                parsed_triggers = self.parse_triggers(match_type.value, triggers)
                priority_value = (
                    100 if priority is None else self.parse_priority_value(priority)
                )
                if cooldown_seconds is not None and cooldown_seconds < 0:
                    raise ValueError("Cooldown must be `0` or higher.")
                ignore_mods_value = (
                    None
                    if ignore_mods is None
                    else {"setup": None, "true": True, "false": False}[
                        ignore_mods.value
                    ]
                )
                exempt_role_ids = (
                    None
                    if exempt_roles is None
                    else self.parse_slash_override_text(
                        exempt_roles, self.parse_role_ids
                    )
                )
                channel_whitelist = (
                    None
                    if allowed_channels is None
                    else self.parse_slash_override_text(
                        allowed_channels, self.parse_channel_ids
                    )
                )
                channel_blacklist = (
                    None
                    if blocked_channels is None
                    else self.parse_slash_override_text(
                        blocked_channels, self.parse_channel_ids
                    )
                )
            except ValueError as error:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed("Invalid parameters.", str(error)),
                    ephemeral=True,
                )
                return

            response_def = {
                "name": name,
                "match_type": match_type.value,
                "triggers": parsed_triggers,
                "response_type": "send_message",
                "response_text": response_text,
                "enabled": True,
                "priority": priority_value,
                "ignore_mods": ignore_mods_value,
                "exempt_role_ids": exempt_role_ids,
                "channel_whitelist": channel_whitelist,
                "channel_blacklist": channel_blacklist,
                "cooldown_seconds": cooldown_seconds,
                "created_by": interaction.user.name,
            }

            saved_response = await add_response(
                self.storage, interaction.guild.id, response_def
            )
            response_store = await get_or_setup_responses(
                self.storage, interaction.guild.id
            )
            embed = await self.make_response_view_embed(
                interaction.guild, response_store, saved_response
            )
            embed.title = f"Response #{saved_response['id']} saved."
            await self.send_interaction_message(
                interaction, embed=embed, ephemeral=True
            )

        @response_group.command(name="list", description="List saved auto responses.")
        async def list_command(interaction: discord.Interaction) -> None:
            if not await self.ensure_slash_permissions(interaction):
                return
            await self.send_slash_response_list(interaction)

        @response_group.command(
            name="view", description="View one saved auto response."
        )
        @app_commands.describe(response_id="Saved response ID.")
        @app_commands.autocomplete(response_id=self.autocomplete_response_id)
        async def view_command(
            interaction: discord.Interaction, response_id: int
        ) -> None:
            if not await self.ensure_slash_permissions(interaction):
                return

            response_store = await get_or_setup_responses(
                self.storage, interaction.guild.id
            )
            response_def = await get_response(
                self.storage, interaction.guild.id, response_id
            )
            if response_def is None:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed(
                        "Invalid response.", self.invalid_response
                    ),
                    ephemeral=True,
                )
                return

            embed = await self.make_response_view_embed(
                interaction.guild, response_store, response_def
            )
            await self.send_interaction_message_defer(
                interaction, embed=embed, ephemeral=True
            )

        @response_group.command(
            name="toggle", description="Turn a saved auto response on or off."
        )
        @app_commands.describe(response_id="Saved response ID.")
        @app_commands.autocomplete(response_id=self.autocomplete_response_id)
        async def toggle_command(
            interaction: discord.Interaction, response_id: int
        ) -> None:
            if not await self.ensure_slash_permissions(interaction):
                return

            response_def = await toggle_response(
                self.storage, interaction.guild.id, response_id
            )
            if response_def is None:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed(
                        "Invalid response.", self.invalid_response
                    ),
                    ephemeral=True,
                )
                return

            status = "on" if response_def.get("enabled", True) else "off"
            await self.send_interaction_message(
                interaction,
                embed=self.make_done_embed(
                    f"Response #{response_id} updated.",
                    f"`{response_def['name']}` is now {status}.",
                ),
                ephemeral=True,
            )

        @response_group.command(
            name="delete", description="Delete a saved auto response."
        )
        @app_commands.describe(
            response_id="Saved response ID.",
            confirm="Set this to true to delete the response.",
        )
        @app_commands.autocomplete(response_id=self.autocomplete_response_id)
        async def delete_command(
            interaction: discord.Interaction, response_id: int, confirm: bool = False
        ) -> None:
            if not await self.ensure_slash_permissions(interaction):
                return

            if not confirm:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed(
                        "Delete not confirmed.",
                        "Run the command again and set `confirm` to `true`.",
                    ),
                    ephemeral=True,
                )
                return

            deleted_response = await delete_response(
                self.storage, interaction.guild.id, response_id
            )
            if deleted_response is None:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed(
                        "Invalid response.", self.invalid_response
                    ),
                    ephemeral=True,
                )
                return

            await self.send_interaction_message(
                interaction,
                embed=self.make_done_embed(
                    f"Response #{response_id} deleted.",
                    f"`{deleted_response['name']}` was removed.",
                ),
                ephemeral=True,
            )

        @response_group.command(name="edit", description="Edit a saved auto response.")
        @app_commands.describe(
            response_id="Saved response ID.",
            name="New response name.",
            match_type="New match type. If this changes, also send new triggers.",
            triggers="Comma separated triggers, or one regex pattern.",
            response_text="New response text.",
            priority="Use `important`, `basic`, or `0-100`.",
            ignore_mods="Use setup, true, or false for this response.",
            exempt_roles="Role mentions or IDs, comma separated. Use `setup` or `none`.",
            allowed_channels="Channel mentions or IDs, comma separated. Use `setup` or `none`.",
            blocked_channels="Channel mentions or IDs, comma separated. Use `setup` or `none`.",
            cooldown_seconds="Cooldown override in seconds.",
        )
        @app_commands.choices(
            match_type=match_type_choices, ignore_mods=ignore_mods_choices
        )
        @app_commands.autocomplete(response_id=self.autocomplete_response_id)
        async def edit_command(
            interaction: discord.Interaction,
            response_id: int,
            name: str | None = None,
            match_type: app_commands.Choice[str] | None = None,
            triggers: str | None = None,
            response_text: str | None = None,
            priority: str | None = None,
            ignore_mods: app_commands.Choice[str] | None = None,
            exempt_roles: str | None = None,
            allowed_channels: str | None = None,
            blocked_channels: str | None = None,
            cooldown_seconds: int | None = None,
        ) -> None:
            if not await self.ensure_slash_permissions(interaction):
                return

            response_store = await get_or_setup_responses(
                self.storage, interaction.guild.id
            )
            response_def = await get_response(
                self.storage, interaction.guild.id, response_id
            )
            if response_def is None:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed(
                        "Invalid response.", self.invalid_response
                    ),
                    ephemeral=True,
                )
                return

            if all(
                value is None
                for value in (
                    name,
                    match_type,
                    triggers,
                    response_text,
                    priority,
                    ignore_mods,
                    exempt_roles,
                    allowed_channels,
                    blocked_channels,
                    cooldown_seconds,
                )
            ):
                embed = await self.make_response_view_embed(
                    interaction.guild, response_store, response_def
                )
                embed.set_footer(text="Set any slash parameters you want to change.")
                await self.send_interaction_message(
                    interaction, embed=embed, ephemeral=True
                )
                return

            updates = {}

            try:
                if name is not None:
                    updates["name"] = name

                new_match_type = response_def["match_type"]
                if match_type is not None:
                    new_match_type = match_type.value
                    if (
                        new_match_type != response_def["match_type"]
                        and triggers is None
                    ):
                        raise ValueError(
                            "When you change the match type, also send new triggers."
                        )
                    if new_match_type != response_def["match_type"]:
                        updates["match_type"] = new_match_type

                if triggers is not None:
                    updates["triggers"] = self.parse_triggers(new_match_type, triggers)
                if response_text is not None:
                    updates["response_text"] = response_text
                if priority is not None:
                    updates["priority"] = self.parse_priority_value(priority)
                if ignore_mods is not None:
                    updates["ignore_mods"] = {
                        "setup": None,
                        "true": True,
                        "false": False,
                    }[ignore_mods.value]
                if exempt_roles is not None:
                    updates["exempt_role_ids"] = self.parse_slash_override_text(
                        exempt_roles, self.parse_role_ids
                    )
                if allowed_channels is not None:
                    updates["channel_whitelist"] = self.parse_slash_override_text(
                        allowed_channels, self.parse_channel_ids
                    )
                if blocked_channels is not None:
                    updates["channel_blacklist"] = self.parse_slash_override_text(
                        blocked_channels, self.parse_channel_ids
                    )
                if cooldown_seconds is not None:
                    if cooldown_seconds < 0:
                        raise ValueError("Cooldown must be `0` or higher.")
                    updates["cooldown_seconds"] = cooldown_seconds
            except ValueError as error:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed("Invalid parameters.", str(error)),
                    ephemeral=True,
                )
                return

            if not updates:
                await self.send_interaction_message(
                    interaction,
                    embed=self.make_error_embed(
                        "No changes given.", "Set at least one field to update."
                    ),
                    ephemeral=True,
                )
                return

            edited_response = await update_response(
                self.storage, interaction.guild.id, response_id, updates
            )
            response_store = await get_or_setup_responses(
                self.storage, interaction.guild.id
            )
            embed = await self.make_response_view_embed(
                interaction.guild, response_store, edited_response
            )
            embed.title = f"Response #{response_id} updated."
            await self.send_interaction_message(
                interaction, embed=embed, ephemeral=True
            )

        return [response_group]

    def parse_triggers(self, match_type: str, trigger_text: str) -> list[str]:
        if match_type == "regex":
            trigger = trigger_text.strip()
            if not trigger:
                raise ValueError("You must send a regex pattern.")
            try:
                re.compile(trigger)
            except re.error as error:
                raise ValueError(f"Invalid regex: {error}") from error
            return [trigger]

        lines = [line.strip() for line in trigger_text.splitlines() if line.strip()]
        triggers = (
            lines
            if len(lines) > 1
            else [item.strip() for item in trigger_text.split(",") if item.strip()]
        )
        if not triggers:
            raise ValueError("You must send at least one trigger.")

        if match_type == "emoji":
            invalid_triggers = [
                trigger
                for trigger in triggers
                if not re.fullmatch(r":[a-zA-Z0-9_]+:", trigger)
                and not re.fullmatch(r"<a?:[a-zA-Z0-9_]+:\d+>", trigger)
            ]
            if invalid_triggers:
                raise ValueError(
                    "Emoji triggers must look like `:kek:` or `<:kek:123456789012345678>`."
                )

        return triggers

    def parse_role_ids(self, text: str) -> list[int]:
        role_ids = []
        seen = set()
        parts = [part.strip() for part in re.split(r"[\n,]+", text) if part.strip()]

        for part in parts:
            role_id = parse_roleid(part)
            if role_id not in seen:
                role_ids.append(role_id)
                seen.add(role_id)

        return role_ids

    def parse_channel_ids(self, text: str) -> list[int]:
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        channel_ids = []
        seen = set()
        parts = [part.strip() for part in re.split(r"[\n,]+", text) if part.strip()]

        for part in parts:
            if re.fullmatch(r"\d{17,19}", part):
                channel_id = int(part)
            else:
                match = re.search(r"<#(\d{17,19})>", part)
                if match is None:
                    raise ValueError(f"{part} is not a valid channel ID or mention.")
                channel_id = int(match.group(1))

            if channel_id not in seen:
                channel_ids.append(channel_id)
                seen.add(channel_id)

        return channel_ids

    def parse_priority_value(self, text: str) -> int:
        lowered_text = text.lower().strip()
        if lowered_text == "important":
            return 0
        if lowered_text == "basic":
            return 100
        if is_integer(text):
            parsed_priority = int(text)
            if 0 <= parsed_priority <= 100:
                return parsed_priority
        raise ValueError(
            "Send `important`, `basic`, or a whole number from `0` to `100`."
        )

    def format_roles(self, guild: discord.Guild, role_ids) -> str:
        if role_ids is None:
            return "Use setup"
        if not role_ids:
            return "None"

        names = []
        for role_id in role_ids:
            role = guild.get_role(role_id)
            names.append(f"`{role_id}`" if role is None else role.mention)
        return ", ".join(names)

    def format_channels(self, guild: discord.Guild, channel_ids) -> str:
        if channel_ids is None:
            return "Use setup"
        if not channel_ids:
            return "None"

        names = []
        for channel_id in channel_ids:
            channel = guild.get_channel(channel_id)
            names.append(f"`{channel_id}`" if channel is None else channel.mention)
        return ", ".join(names)

    def format_bool(self, value) -> str:
        if value is None:
            return "Use setup"
        return "Yes" if value else "No"

    def format_number(self, value) -> str:
        if value is None:
            return "Use setup"
        return str(value)

    async def get_response_text_preview(
        self, guild: discord.Guild, response_text: str
    ) -> tuple[str, list[str]]:
        return await parse_emotes_with_status_async(response_text, self.client, guild)

    def make_setup_intro_embed(
        self, guild: discord.Guild, current_settings: dict
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Auto response setup",
            description="These are the default settings all responses use unless a response sets its own value.",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Ignore moderators",
            value="Yes" if current_settings.get("ignore_mods", True) else "No",
            inline=False,
        )
        embed.add_field(
            name="Exempt roles",
            value=self.format_roles(guild, current_settings.get("exempt_role_ids", [])),
            inline=False,
        )
        embed.add_field(
            name="Allowed channels",
            value=self.format_channels(
                guild, current_settings.get("channel_whitelist", [])
            ),
            inline=False,
        )
        embed.add_field(
            name="Blocked channels",
            value=self.format_channels(
                guild, current_settings.get("channel_blacklist", [])
            ),
            inline=False,
        )
        embed.add_field(
            name="Cooldown",
            value=f"{current_settings.get('cooldown_seconds', 300)} seconds",
            inline=False,
        )
        return embed

    def make_setup_preview_embed(
        self, guild: discord.Guild, settings: dict
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Save auto response setup?",
            description="Check the default settings before saving.",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Ignore moderators",
            value="Yes" if settings["ignore_mods"] else "No",
            inline=False,
        )
        embed.add_field(
            name="Exempt roles",
            value=self.format_roles(guild, settings["exempt_role_ids"]),
            inline=False,
        )
        embed.add_field(
            name="Allowed channels",
            value=self.format_channels(guild, settings["channel_whitelist"]),
            inline=False,
        )
        embed.add_field(
            name="Blocked channels",
            value=self.format_channels(guild, settings["channel_blacklist"]),
            inline=False,
        )
        embed.add_field(
            name="Cooldown",
            value=f"{settings['cooldown_seconds']} seconds",
            inline=False,
        )
        return embed

    async def make_response_view_embed(
        self, guild: discord.Guild, response_store: dict, response_def: dict
    ) -> discord.Embed:
        parsed_response_text, missing_emojis = await self.get_response_text_preview(
            guild, response_def["response_text"]
        )
        embed = discord.Embed(
            title=f"Auto Response #{response_def['id']}",
            description=response_def["name"],
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Match type", value=response_def["match_type"], inline=False
        )
        embed.add_field(
            name="Priority",
            value=f"`{response_def.get('priority', 100)}`",
            inline=False,
        )
        embed.add_field(
            name="Triggers", value="\n".join(response_def["triggers"]), inline=False
        )
        embed.add_field(
            name="Response text", value=parsed_response_text[:1024], inline=False
        )
        if missing_emojis:
            embed.add_field(
                name="Missing emojis",
                value=", ".join(f"`:{emoji_name}:`" for emoji_name in missing_emojis)[
                    :1024
                ],
                inline=False,
            )
        embed.add_field(
            name="Status",
            value="On" if response_def.get("enabled", True) else "Off",
            inline=False,
        )
        embed.add_field(
            name="Ignore moderators",
            value=self.format_bool(response_def.get("ignore_mods"))
            + f" (effective: {'Yes' if get_effective_setting(response_store, response_def, 'ignore_mods') else 'No'})",
            inline=False,
        )
        embed.add_field(
            name="Exempt roles",
            value=self.format_roles(guild, response_def.get("exempt_role_ids")),
            inline=False,
        )
        embed.add_field(
            name="Allowed channels",
            value=self.format_channels(guild, response_def.get("channel_whitelist")),
            inline=False,
        )
        embed.add_field(
            name="Blocked channels",
            value=self.format_channels(guild, response_def.get("channel_blacklist")),
            inline=False,
        )
        embed.add_field(
            name="Cooldown",
            value=self.format_number(response_def.get("cooldown_seconds"))
            + f" (effective: {get_effective_setting(response_store, response_def, 'cooldown_seconds')})",
            inline=False,
        )
        embed.set_footer(text=f"Created by {response_def.get('created_by', 'unknown')}")
        return embed

    def make_done_embed(self, title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=title, description=description, color=discord.Color.green()
        )


classes = [("ResponseCommand", ResponseCommand)]
