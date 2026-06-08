import asyncio
import inspect
import re
import sys

import discord

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
    normalize_priority,
    toggle_response,
    update_response,
    update_response_settings,
)
from helpers.roleid_parser import parse_roleid


class PickButton(discord.ui.Button):
    def __init__(self, label: str, value: str, style: discord.ButtonStyle) -> None:
        super().__init__(label=label, style=style)
        self.value = value

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None or interaction.user.id != view.author_id:
            await interaction.response.send_message(
                "This is not for you.", ephemeral=True
            )
            return

        view.value = self.value
        for child in view.children:
            child.disabled = True
        await interaction.response.edit_message(view=view)
        view.stop()


class PickView(discord.ui.View):
    def __init__(self, author_id: int, choices: list[tuple[str, str, discord.ButtonStyle]]) -> None:
        super().__init__(timeout=180)
        self.author_id = author_id
        self.value = None
        for label, value, style in choices:
            self.add_item(PickButton(label, value, style))


class ResponseSettingButton(discord.ui.Button):
    def __init__(
        self,
        label: str,
        action: str,
        style: discord.ButtonStyle,
        disabled: bool = False,
    ) -> None:
        super().__init__(label=label, style=style, disabled=disabled)
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None or interaction.user.id != view.author_id:
            await interaction.response.send_message(
                "This is not for you.", ephemeral=True
            )
            return

        view.action = self.action
        await interaction.response.defer()
        view.stop()


class ResponseSettingView(discord.ui.View):
    def __init__(self, author_id: int, page_index: int, page_count: int) -> None:
        super().__init__(timeout=180)
        self.author_id = author_id
        self.action = None
        self.add_item(
            ResponseSettingButton(
                "Previous",
                "previous",
                discord.ButtonStyle.secondary,
                disabled=page_index == 0,
            )
        )
        self.add_item(
            ResponseSettingButton(
                "Confirm All",
                "confirm",
                discord.ButtonStyle.success,
            )
        )
        self.add_item(
            ResponseSettingButton(
                "Cancel",
                "cancel",
                discord.ButtonStyle.danger,
            )
        )
        self.add_item(
            ResponseSettingButton(
                "Next",
                "next",
                discord.ButtonStyle.secondary,
                disabled=page_index == page_count - 1,
            )
        )


class ResponseCommand(Command):
    def __init__(self, client_instance: ModerationBot) -> None:
        self.cmd = ["response", "responses"]
        self.client = client_instance
        self.storage = client_instance.storage
        self.timeout_seconds = 180
        self.usage = (
            f"Usage: {self.client.prefix}response "
            "<setup|add|list|view|edit|toggle|delete> [response_id]"
        )
        self.invalid_args = "Invalid parameters."
        self.invalid_response = "Sorry, that is not a valid response ID."
        self.no_permissions = "Only moderators and admins can set up responses."

    async def execute(self, message: discord.Message, **kwargs) -> None:
        args = kwargs.get("args", [])
        command = args[0].lower() if args else None
        possible_id = args[1] if len(args) > 1 else None

        if not (
            author_is_admin(message.author)
            or await author_is_mod(message.author, self.storage)
        ):
            await message.channel.send(self.no_permissions)
            return

        if command == "setup":
            await self.handle_setup(message)
            return

        if command == "add":
            await self.handle_add(message)
            return

        if command == "list":
            await self.handle_list(message)
            return

        if command in {"view", "edit", "toggle", "delete", "remove"}:
            if possible_id is None or not is_integer(possible_id):
                await message.channel.send(self.invalid_response)
                return

            response_id = int(possible_id)

            if command == "view":
                await self.handle_view(message, response_id)
            elif command == "edit":
                await self.handle_edit(message, response_id)
            elif command == "toggle":
                await self.handle_toggle(message, response_id)
            else:
                await self.handle_delete(message, response_id)
            return

        await message.channel.send(self.usage)

    async def handle_setup(self, message: discord.Message) -> None:
        current_settings = await get_response_settings(self.storage, message.guild.id)

        await message.channel.send(
            embed=self.make_setup_intro_embed(message.guild, current_settings)
        )

        ignore_mods = await self.ask_yes_no(
            message,
            "Ignore moderators",
            "Should auto responses ignore moderators and admins by default?",
        )
        if ignore_mods == "cancel":
            await self.send_cancel_message(message)
            return

        exempt_role_ids = await self.ask_role_list(
            message,
            "Exempt roles",
            "Send role mentions or IDs to ignore by default. Send `none` for no roles.",
            allow_skip=False,
        )
        if exempt_role_ids == "cancel":
            await self.send_cancel_message(message)
            return

        channel_whitelist = await self.ask_channel_list(
            message,
            "Allowed channels",
            "Send channel mentions or IDs to allow by default. Send `none` for all channels.",
            allow_skip=False,
        )
        if channel_whitelist == "cancel":
            await self.send_cancel_message(message)
            return

        channel_blacklist = await self.ask_channel_list(
            message,
            "Blocked channels",
            "Send channel mentions or IDs to block by default. Send `none` for no blocked channels.",
            allow_skip=False,
        )
        if channel_blacklist == "cancel":
            await self.send_cancel_message(message)
            return

        cooldown_seconds = await self.ask_number(
            message,
            "Cooldown",
            "Send the default cooldown in seconds. Use `0` for no cooldown.",
            allow_skip=False,
        )
        if cooldown_seconds == "cancel":
            await self.send_cancel_message(message)
            return

        new_settings = {
            "ignore_mods": ignore_mods,
            "exempt_role_ids": exempt_role_ids,
            "channel_whitelist": channel_whitelist,
            "channel_blacklist": channel_blacklist,
            "cooldown_seconds": cooldown_seconds,
        }

        save_choice = await self.ask_pick(
            message,
            self.make_setup_preview_embed(message.guild, new_settings),
            [
                ("Save", "save", discord.ButtonStyle.success),
                ("Cancel", "cancel", discord.ButtonStyle.danger),
            ],
        )

        if save_choice != "save":
            await self.send_cancel_message(message)
            return

        await update_response_settings(self.storage, message.guild.id, new_settings)
        await message.channel.send(
            embed=self.make_done_embed(
                "Response setup saved.",
                "The default response settings have been updated.",
            )
        )

    async def handle_add(self, message: discord.Message) -> None:
        response_store = await get_or_setup_responses(self.storage, message.guild.id)

        match_type = await self.ask_pick(
            message,
            self.make_type_pick_embed(),
            [
                ("Word", "word", discord.ButtonStyle.primary),
                ("Phrase", "phrase", discord.ButtonStyle.primary),
                ("Emoji", "emoji", discord.ButtonStyle.success),
                ("Regex", "regex", discord.ButtonStyle.secondary),
                ("Cancel", "cancel", discord.ButtonStyle.danger),
            ],
        )
        if match_type in {None, "cancel"}:
            await self.send_cancel_message(message)
            return

        name = await self.ask_text(
            message,
            "Response name",
            "Send a short name for this response.",
        )
        if name is None:
            await self.send_cancel_message(message)
            return

        trigger_text = await self.ask_text(
            message,
            "Trigger text",
            self.get_trigger_prompt(match_type),
        )
        if trigger_text is None:
            await self.send_cancel_message(message)
            return

        try:
            triggers = self.parse_triggers(match_type, trigger_text)
        except ValueError as error:
            await message.channel.send(str(error))
            return

        response_text = await self.ask_text(
            message,
            "Response text",
            "Send the message the bot should post when this matches.",
        )
        if response_text is None:
            await self.send_cancel_message(message)
            return

        setting_values = await self.run_response_setting_setup(
            message,
            response_store,
        )
        if setting_values is None:
            return

        ignore_mods = setting_values["ignore_mods"]
        exempt_role_ids = setting_values["exempt_role_ids"]
        channel_whitelist = setting_values["channel_whitelist"]
        channel_blacklist = setting_values["channel_blacklist"]
        cooldown_seconds = setting_values["cooldown_seconds"]
        priority = setting_values["priority"]
        if priority is None:
            priority = 100

        response_def = {
            "name": name,
            "match_type": match_type,
            "triggers": triggers,
            "response_type": "send_message",
            "response_text": response_text,
            "enabled": True,
            "priority": priority,
            "ignore_mods": ignore_mods,
            "exempt_role_ids": exempt_role_ids,
            "channel_whitelist": channel_whitelist,
            "channel_blacklist": channel_blacklist,
            "cooldown_seconds": cooldown_seconds,
            "created_by": message.author.name,
        }

        preview_embed = await self.make_response_preview_embed(
            message.guild,
            response_store,
            response_def,
        )
        save_choice = await self.ask_pick(
            message,
            preview_embed,
            [
                ("Save", "save", discord.ButtonStyle.success),
                ("Cancel", "cancel", discord.ButtonStyle.danger),
            ],
        )

        if save_choice != "save":
            await self.send_cancel_message(message)
            return

        saved_response = await add_response(self.storage, message.guild.id, response_def)
        await message.channel.send(
            embed=self.make_done_embed(
                f"Response #{saved_response['id']} saved.",
                f"`{saved_response['name']}` is ready.",
            )
        )

    async def handle_list(self, message: discord.Message) -> None:
        entries = await list_responses(self.storage, message.guild.id)
        response_items = sorted(
            entries.values(),
            key=lambda item: (item.get("priority", 100), item.get("id", 0)),
        )

        if not response_items:
            await message.channel.send(
                embed=self.make_done_embed(
                    "No responses saved.",
                    f"Use `{self.client.prefix}response add` to make one.",
                )
            )
            return

        page_size = 8
        pages = [
            response_items[index:index + page_size]
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
                    value=(
                        f"Type: `{response_def['match_type']}`\n"
                        f"Priority: `{response_def.get('priority', 100)}`\n"
                        f"Status: `{status}`\n"
                        f"Triggers: `{len(response_def.get('triggers', []))}`"
                    ),
                    inline=False,
                )
            embed.set_footer(
                text=f"Use {self.client.prefix}response view <id> to see one entry."
            )
            return embed

        current_page = 0
        embed = create_embed(current_page)

        class PageView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(
                label="Previous",
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                nonlocal current_page
                if interaction.user.id != message.author.id:
                    await interaction.response.send_message(
                        "This is not for you.", ephemeral=True
                    )
                    return
                if current_page > 0:
                    current_page -= 1
                    self.previous_button.disabled = current_page == 0
                    self.next_button.disabled = False
                    await interaction.response.edit_message(
                        embed=create_embed(current_page),
                        view=self,
                    )

            @discord.ui.button(
                label="Next",
                style=discord.ButtonStyle.secondary,
                disabled=len(pages) <= 1,
            )
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                nonlocal current_page
                if interaction.user.id != message.author.id:
                    await interaction.response.send_message(
                        "This is not for you.", ephemeral=True
                    )
                    return
                if current_page < len(pages) - 1:
                    current_page += 1
                    self.next_button.disabled = current_page == len(pages) - 1
                    self.previous_button.disabled = False
                    await interaction.response.edit_message(
                        embed=create_embed(current_page),
                        view=self,
                    )

        await message.channel.send(embed=embed, view=PageView())

    async def handle_view(self, message: discord.Message, response_id: int) -> None:
        response_store = await get_or_setup_responses(self.storage, message.guild.id)
        response_def = await get_response(self.storage, message.guild.id, response_id)
        if response_def is None:
            await message.channel.send(self.invalid_response)
            return

        view_embed = await self.make_response_view_embed(
            message.guild,
            response_store,
            response_def,
        )
        await message.channel.send(embed=view_embed)

    async def handle_toggle(self, message: discord.Message, response_id: int) -> None:
        response_def = await toggle_response(self.storage, message.guild.id, response_id)
        if response_def is None:
            await message.channel.send(self.invalid_response)
            return

        status = "on" if response_def.get("enabled", True) else "off"
        await message.channel.send(
            embed=self.make_done_embed(
                f"Response #{response_id} updated.",
                f"`{response_def['name']}` is now {status}.",
            )
        )

    async def handle_delete(self, message: discord.Message, response_id: int) -> None:
        response_def = await get_response(self.storage, message.guild.id, response_id)
        if response_def is None:
            await message.channel.send(self.invalid_response)
            return

        choice = await self.ask_pick(
            message,
            self.make_delete_confirm_embed(response_def),
            [
                ("Delete", "delete", discord.ButtonStyle.danger),
                ("Cancel", "cancel", discord.ButtonStyle.secondary),
            ],
        )

        if choice != "delete":
            await self.send_cancel_message(message)
            return

        deleted_response = await delete_response(
            self.storage, message.guild.id, response_id
        )
        if deleted_response is None:
            await message.channel.send(self.invalid_response)
            return

        await message.channel.send(
            embed=self.make_done_embed(
                f"Response #{response_id} deleted.",
                f"`{deleted_response['name']}` was removed.",
            )
        )

    async def handle_edit(self, message: discord.Message, response_id: int) -> None:
        response_store = await get_or_setup_responses(self.storage, message.guild.id)
        response_def = await get_response(self.storage, message.guild.id, response_id)
        if response_def is None:
            await message.channel.send(self.invalid_response)
            return

        field_name = await self.ask_text(
            message,
            "Edit field",
            (
                "Send one of these field names:\n"
                "`name`, `type`, `triggers`, `text`, `ignore_mods`, `exempt_roles`, "
                "`allowed_channels`, `blocked_channels`, `cooldown`, `priority`"
            ),
        )
        if field_name is None:
            await self.send_cancel_message(message)
            return

        field_name = field_name.lower().replace(" ", "_")
        updates = {}

        if field_name == "name":
            new_name = await self.ask_text(
                message,
                "New name",
                "Send the new response name.",
            )
            if new_name is None:
                await self.send_cancel_message(message)
                return
            updates["name"] = new_name

        elif field_name == "type":
            new_type = await self.ask_pick(
                message,
                self.make_type_pick_embed(),
                [
                    ("Word", "word", discord.ButtonStyle.primary),
                    ("Phrase", "phrase", discord.ButtonStyle.primary),
                    ("Emoji", "emoji", discord.ButtonStyle.success),
                    ("Regex", "regex", discord.ButtonStyle.secondary),
                    ("Cancel", "cancel", discord.ButtonStyle.danger),
                ],
            )
            if new_type in {None, "cancel"}:
                await self.send_cancel_message(message)
                return
            trigger_text = await self.ask_text(
                message,
                "New trigger text",
                self.get_trigger_prompt(new_type),
            )
            if trigger_text is None:
                await self.send_cancel_message(message)
                return
            try:
                updates["match_type"] = new_type
                updates["triggers"] = self.parse_triggers(new_type, trigger_text)
            except ValueError as error:
                await message.channel.send(str(error))
                return

        elif field_name == "triggers":
            trigger_text = await self.ask_text(
                message,
                "New trigger text",
                self.get_trigger_prompt(response_def["match_type"]),
            )
            if trigger_text is None:
                await self.send_cancel_message(message)
                return
            try:
                updates["triggers"] = self.parse_triggers(
                    response_def["match_type"],
                    trigger_text,
                )
            except ValueError as error:
                await message.channel.send(str(error))
                return

        elif field_name == "text":
            new_text = await self.ask_text(
                message,
                "New response text",
                "Send the new text the bot should post.",
            )
            if new_text is None:
                await self.send_cancel_message(message)
                return
            updates["response_text"] = new_text

        elif field_name == "ignore_mods":
            ignore_mods = await self.ask_yes_no(
                message,
                "Ignore moderators override",
                "Send `yes`, `no`, or `skip` to use setup settings.",
                allow_skip=True,
            )
            if ignore_mods == "cancel":
                await self.send_cancel_message(message)
                return
            updates["ignore_mods"] = ignore_mods

        elif field_name == "exempt_roles":
            exempt_role_ids = await self.ask_role_list(
                message,
                "Exempt roles override",
                "Send role mentions or IDs. Send `skip` to use setup settings or `none` for no roles.",
                allow_skip=True,
            )
            if exempt_role_ids == "cancel":
                await self.send_cancel_message(message)
                return
            updates["exempt_role_ids"] = exempt_role_ids

        elif field_name == "allowed_channels":
            channel_whitelist = await self.ask_channel_list(
                message,
                "Allowed channels override",
                "Send channel mentions or IDs. Send `skip` to use setup settings or `none` for all channels.",
                allow_skip=True,
            )
            if channel_whitelist == "cancel":
                await self.send_cancel_message(message)
                return
            updates["channel_whitelist"] = channel_whitelist

        elif field_name == "blocked_channels":
            channel_blacklist = await self.ask_channel_list(
                message,
                "Blocked channels override",
                "Send channel mentions or IDs. Send `skip` to use setup settings or `none` for no blocked channels.",
                allow_skip=True,
            )
            if channel_blacklist == "cancel":
                await self.send_cancel_message(message)
                return
            updates["channel_blacklist"] = channel_blacklist

        elif field_name == "cooldown":
            cooldown_seconds = await self.ask_number(
                message,
                "Cooldown override",
                "Send the cooldown in seconds. Send `skip` to use setup settings.",
                allow_skip=True,
            )
            if cooldown_seconds == "cancel":
                await self.send_cancel_message(message)
                return
            updates["cooldown_seconds"] = cooldown_seconds

        elif field_name == "priority":
            priority_text = await self.ask_text(
                message,
                "Priority",
                "Send `important`, `basic`, or a whole number from `0` to `100`.",
            )
            if priority_text is None:
                await self.send_cancel_message(message)
                return
            try:
                updates["priority"] = self.parse_priority_value(priority_text)
            except ValueError as error:
                await message.channel.send(str(error))
                return

        else:
            await message.channel.send(self.invalid_args)
            return

        edited_response = response_def.copy()
        edited_response.update(updates)

        preview_embed = await self.make_response_preview_embed(
            message.guild,
            response_store,
            edited_response,
        )
        choice = await self.ask_pick(
            message,
            preview_embed,
            [
                ("Save", "save", discord.ButtonStyle.success),
                ("Cancel", "cancel", discord.ButtonStyle.danger),
            ],
        )

        if choice != "save":
            await self.send_cancel_message(message)
            return

        await update_response(self.storage, message.guild.id, response_id, updates)
        await message.channel.send(
            embed=self.make_done_embed(
                f"Response #{response_id} updated.",
                f"`{edited_response['name']}` was saved.",
            )
        )

    async def ask_pick(
        self,
        message: discord.Message,
        embed: discord.Embed,
        choices: list[tuple[str, str, discord.ButtonStyle]],
    ):
        view = PickView(message.author.id, choices)
        await message.channel.send(embed=embed, view=view)
        await view.wait()
        return view.value

    async def run_response_setting_setup(
        self,
        message: discord.Message,
        response_store: dict,
    ) -> dict | None:
        pages = self.get_response_setting_pages()
        setting_values = {page["key"]: None for page in pages}
        current_page = 0
        error_text = None
        prompt_message = None

        while True:
            embed = self.make_response_setting_embed(
                message.guild,
                response_store,
                setting_values,
                pages,
                current_page,
                error_text,
            )
            view = ResponseSettingView(
                message.author.id,
                current_page,
                len(pages),
            )

            if prompt_message is None:
                prompt_message = await message.channel.send(embed=embed, view=view)
            else:
                await prompt_message.edit(embed=embed, view=view)

            error_text = None

            def check(reply: discord.Message) -> bool:
                return (
                    reply.author.id == message.author.id
                    and reply.channel.id == message.channel.id
                )

            button_task = asyncio.create_task(view.wait())
            text_task = asyncio.create_task(
                self.client.wait_for(
                    "message",
                    timeout=self.timeout_seconds,
                    check=check,
                )
            )

            done, pending = await asyncio.wait(
                {button_task, text_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            if text_task in done and not text_task.cancelled():
                try:
                    reply = text_task.result()
                except asyncio.TimeoutError:
                    await prompt_message.edit(view=None)
                    await self.send_timeout_message(message)
                    return None

                if reply.content.lower() == "cancel":
                    await self.try_delete_message(reply)
                    await prompt_message.edit(view=None)
                    await self.send_cancel_message(message)
                    return None

                page_key = pages[current_page]["key"]
                try:
                    setting_values[page_key] = self.parse_response_setting_value(
                        page_key,
                        reply.content,
                    )
                    await self.try_delete_message(reply)
                    if current_page < len(pages) - 1:
                        current_page += 1
                except ValueError as error:
                    await self.try_delete_message(reply)
                    error_text = str(error)

                continue

            action = view.action
            if action is None:
                await prompt_message.edit(view=None)
                await self.send_timeout_message(message)
                return None

            if action == "cancel":
                await prompt_message.edit(view=None)
                await self.send_cancel_message(message)
                return None

            if action == "confirm":
                await prompt_message.edit(view=None)
                return setting_values

            if action == "previous" and current_page > 0:
                current_page -= 1
            elif action == "next" and current_page < len(pages) - 1:
                current_page += 1

    async def ask_text(
        self,
        message: discord.Message,
        title: str,
        description: str,
    ):
        await message.channel.send(embed=self.make_question_embed(title, description))

        def check(reply: discord.Message) -> bool:
            return (
                reply.author.id == message.author.id
                and reply.channel.id == message.channel.id
            )

        try:
            reply = await self.client.wait_for(
                "message",
                timeout=self.timeout_seconds,
                check=check,
            )
        except asyncio.TimeoutError:
            await self.send_timeout_message(message)
            return None

        if reply.content.lower() == "cancel":
            return None

        return reply.content

    async def try_delete_message(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def ask_yes_no(
        self,
        message: discord.Message,
        title: str,
        description: str,
        allow_skip: bool = False,
        allow_rest: bool = False,
    ):
        choices = [
            ("Yes", "yes", discord.ButtonStyle.success),
            ("No", "no", discord.ButtonStyle.danger),
        ]
        if allow_skip:
            choices.append(("Use setup", "skip", discord.ButtonStyle.secondary))
            if allow_rest:
                choices.append(
                    ("Use setup for rest", "rest", discord.ButtonStyle.secondary)
                )
        choices.append(("Cancel", "cancel", discord.ButtonStyle.secondary))

        view = PickView(message.author.id, choices)
        prompt_message = await message.channel.send(
            embed=self.make_question_embed(title, description),
            view=view,
        )

        allowed_answers = {"yes", "no", "cancel"}
        if allow_skip:
            allowed_answers.update({"skip", "none"})
        if allow_rest:
            allowed_answers.add("rest")

        def check(reply: discord.Message) -> bool:
            return (
                reply.author.id == message.author.id
                and reply.channel.id == message.channel.id
                and reply.content.lower() in allowed_answers
            )

        button_task = asyncio.create_task(view.wait())
        text_task = asyncio.create_task(
            self.client.wait_for(
                "message",
                timeout=self.timeout_seconds,
                check=check,
            )
        )

        done, pending = await asyncio.wait(
            {button_task, text_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        if text_task in done and not text_task.cancelled():
            try:
                reply = text_task.result()
            except asyncio.TimeoutError:
                return "cancel"

            view.value = reply.content.lower()
            if view.value == "none":
                view.value = "skip"
            for child in view.children:
                child.disabled = True
            await prompt_message.edit(view=view)
            view.stop()
            choice = view.value
        else:
            choice = view.value or "cancel"

        if choice == "yes":
            return True
        if choice == "no":
            return False
        if choice == "skip":
            return None
        if choice == "rest":
            return "rest"
        return "cancel"

    async def ask_number(
        self,
        message: discord.Message,
        title: str,
        description: str,
        allow_skip: bool = False,
        allow_rest: bool = False,
    ):
        text = await self.ask_text(message, title, description)
        if text is None:
            return "cancel"

        lowered_text = text.lower()
        if allow_rest and lowered_text == "rest":
            return "rest"
        if allow_skip and lowered_text in {"skip", "none"}:
            return None

        if not is_integer(text):
            await message.channel.send("Please send a whole number.")
            return await self.ask_number(
                message,
                title,
                description,
                allow_skip,
                allow_rest,
            )

        return int(text)

    async def ask_role_list(
        self,
        message: discord.Message,
        title: str,
        description: str,
        allow_skip: bool = False,
        allow_rest: bool = False,
    ):
        text = await self.ask_text(message, title, description)
        if text is None:
            return "cancel"

        lowered_text = text.lower()
        if allow_rest and lowered_text == "rest":
            return "rest"
        if allow_skip and lowered_text == "skip":
            return None
        if lowered_text == "none":
            return []

        try:
            return self.parse_role_ids(text)
        except ValueError as error:
            await message.channel.send(str(error))
            return await self.ask_role_list(
                message,
                title,
                description,
                allow_skip,
                allow_rest,
            )

    async def ask_channel_list(
        self,
        message: discord.Message,
        title: str,
        description: str,
        allow_skip: bool = False,
        allow_rest: bool = False,
    ):
        text = await self.ask_text(message, title, description)
        if text is None:
            return "cancel"

        lowered_text = text.lower()
        if allow_rest and lowered_text == "rest":
            return "rest"
        if allow_skip and lowered_text == "skip":
            return None
        if lowered_text == "none":
            return []

        try:
            return self.parse_channel_ids(text)
        except ValueError as error:
            await message.channel.send(str(error))
            return await self.ask_channel_list(
                message,
                title,
                description,
                allow_skip,
                allow_rest,
            )

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
        if len(lines) > 1:
            triggers = lines
        else:
            triggers = [item.strip() for item in trigger_text.split(",") if item.strip()]

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

    def get_response_setting_pages(self) -> list[dict]:
        return [
            {
                "key": "priority",
                "name": "Priority",
                "options": "`important` | `basic` | `0-100`",
            },
            {
                "key": "ignore_mods",
                "name": "Ignore Moderators",
                "options": "`true` | `false` | `setup`",
            },
            {
                "key": "exempt_role_ids",
                "name": "Exempt Roles",
                "options": "Role mention / ID | `none` | `setup`",
            },
            {
                "key": "channel_whitelist",
                "name": "Allowed Channels",
                "options": "Channel mention / ID | `none` | `setup`",
            },
            {
                "key": "channel_blacklist",
                "name": "Blocked Channels",
                "options": "Channel mention / ID | `none` | `setup`",
            },
            {
                "key": "cooldown_seconds",
                "name": "Cooldown",
                "options": "Whole number | `0` | `setup`",
            },
        ]

    def parse_response_setting_value(self, setting_key: str, text: str):
        lowered_text = text.lower().strip()

        if lowered_text in {"setup", "skip", "default"}:
            return None

        if setting_key == "priority":
            return self.parse_priority_value(text)

        if setting_key == "ignore_mods":
            if lowered_text in {"true", "yes"}:
                return True
            if lowered_text in {"false", "no"}:
                return False
            raise ValueError("Send `true`, `false`, or `setup`.")

        if setting_key == "exempt_role_ids":
            if lowered_text == "none":
                return []
            return self.parse_role_ids(text)

        if setting_key in {"channel_whitelist", "channel_blacklist"}:
            if lowered_text == "none":
                return []
            return self.parse_channel_ids(text)

        if setting_key == "cooldown_seconds":
            if lowered_text == "none":
                return None
            if not is_integer(text):
                raise ValueError("Send a whole number or `setup`.")
            return int(text)

        raise ValueError("Invalid setting.")

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

    def format_json_bool(self, value: bool) -> str:
        return "true" if value else "false"

    def format_response_setting_current(
        self,
        guild: discord.Guild,
        response_store: dict,
        setting_values: dict,
        setting_key: str,
    ) -> tuple[str, str]:
        current_value = setting_values[setting_key]
        if current_value is None:
            if setting_key == "priority":
                current_value = 100
                source_text = "basic default"
            else:
                current_value = response_store["settings"].get(setting_key)
                source_text = "based on setup"
        else:
            source_text = "custom value"

        if setting_key == "priority":
            return f"`{current_value}`", source_text

        if setting_key == "ignore_mods":
            return f"`{self.format_json_bool(current_value)}`", source_text

        if setting_key == "exempt_role_ids":
            return self.format_roles(guild, current_value), source_text

        if setting_key in {"channel_whitelist", "channel_blacklist"}:
            return self.format_channels(guild, current_value), source_text

        if setting_key == "cooldown_seconds":
            return f"`{current_value}`", source_text

        return str(current_value), source_text

    def format_roles(self, guild: discord.Guild, role_ids) -> str:
        if role_ids is None:
            return "Use setup"
        if not role_ids:
            return "None"

        names = []
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role is None:
                names.append(f"`{role_id}`")
            else:
                names.append(role.mention)
        return ", ".join(names)

    def format_channels(self, guild: discord.Guild, channel_ids) -> str:
        if channel_ids is None:
            return "Use setup"
        if not channel_ids:
            return "None"

        names = []
        for channel_id in channel_ids:
            channel = guild.get_channel(channel_id)
            if channel is None:
                names.append(f"`{channel_id}`")
            else:
                names.append(channel.mention)
        return ", ".join(names)

    def format_bool(self, value) -> str:
        if value is None or value == "skip":
            return "Use setup"
        return "Yes" if value else "No"

    def format_number(self, value) -> str:
        if value is None:
            return "Use setup"
        return str(value)

    async def get_response_text_preview(
        self,
        guild: discord.Guild,
        response_text: str,
    ) -> tuple[str, list[str]]:
        parsed_text, missing_emojis = await parse_emotes_with_status_async(
            response_text,
            self.client,
            guild,
        )
        return parsed_text, missing_emojis

    def get_trigger_prompt(self, match_type: str) -> str:
        if match_type == "word":
            return "Send one or more words. Use one per line or commas."
        if match_type == "phrase":
            return "Send one or more phrases. Use one per line or commas."
        if match_type == "emoji":
            return (
                "Send one or more emoji names like `:kek:`. "
                "Use one per line or commas."
            )
        return "Send one regex pattern."

    async def send_timeout_message(self, message: discord.Message) -> None:
        await message.channel.send(
            embed=self.make_done_embed(
                "Response setup timed out.",
                "Run the command again when you want to continue.",
            )
        )

    async def send_cancel_message(self, message: discord.Message) -> None:
        await message.channel.send(
            embed=self.make_done_embed(
                "Response setup cancelled.",
                "Nothing was saved.",
            )
        )

    def make_question_embed(self, title: str, description: str) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Type cancel to stop.")
        return embed

    def make_response_setting_embed(
        self,
        guild: discord.Guild,
        response_store: dict,
        setting_values: dict,
        pages: list[dict],
        current_page: int,
        error_text: str | None = None,
    ) -> discord.Embed:
        page = pages[current_page]
        current_text, source_text = self.format_response_setting_current(
            guild,
            response_store,
            setting_values,
            page["key"],
        )

        description = (
            f"**Setting ({current_page + 1}/{len(pages)}):**\n"
            f"{page['name']}\n\n"
            f"**Current:**\n"
            f"{current_text}\n"
            f"-# {source_text}\n\n"
            f"**Options:**\n"
            f"{page['options']}\n\n"
            "Reply in chat to update this setting. Your reply will be deleted."
        )

        if error_text:
            description += f"\n\n**Last error:**\n{error_text}"

        embed = discord.Embed(
            title="Response setting",
            description=description,
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Use Confirm All to save the current settings.")
        return embed

    def make_type_pick_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Response match type",
            description=(
                "Pick how this response should match messages.\n"
                "`word`, `phrase`, and `regex` ignore emoji names like `:kek:`.\n"
                "Use `emoji` if you want to match the emoji itself."
            ),
            color=discord.Color.blue(),
        )

    def make_setup_intro_embed(
        self,
        guild: discord.Guild,
        current_settings: dict,
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
            value=self.format_channels(guild, current_settings.get("channel_whitelist", [])),
            inline=False,
        )
        embed.add_field(
            name="Blocked channels",
            value=self.format_channels(guild, current_settings.get("channel_blacklist", [])),
            inline=False,
        )
        embed.add_field(
            name="Cooldown",
            value=f"{current_settings.get('cooldown_seconds', 300)} seconds",
            inline=False,
        )
        return embed

    def make_setup_preview_embed(self, guild: discord.Guild, settings: dict) -> discord.Embed:
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

    async def make_response_preview_embed(
        self,
        guild: discord.Guild,
        response_store: dict,
        response_def: dict,
    ) -> discord.Embed:
        parsed_response_text, missing_emojis = await self.get_response_text_preview(
            guild,
            response_def["response_text"],
        )
        embed = discord.Embed(
            title="Save auto response?",
            description="Check this response before saving.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Name", value=response_def["name"], inline=False)
        embed.add_field(
            name="Match type",
            value=response_def["match_type"],
            inline=False,
        )
        embed.add_field(
            name="Priority",
            value=f"`{response_def.get('priority', 100)}`",
            inline=False,
        )
        embed.add_field(
            name="Triggers",
            value="\n".join(response_def["triggers"]),
            inline=False,
        )
        embed.add_field(
            name="Response text",
            value=parsed_response_text[:1024],
            inline=False,
        )
        if missing_emojis:
            embed.add_field(
                name="Missing emojis",
                value=", ".join(f"`:{emoji_name}:`" for emoji_name in missing_emojis)[:1024],
                inline=False,
            )
        embed.add_field(
            name="Ignore moderators",
            value=self.format_bool(response_def.get("ignore_mods")),
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
            value=self.format_number(response_def.get("cooldown_seconds")),
            inline=False,
        )
        embed.set_footer(
            text=(
                "Use setup"
                if any(
                    response_def.get(key) is None
                    or response_def.get(key) == "skip"
                    for key in (
                        "ignore_mods",
                        "exempt_role_ids",
                        "channel_whitelist",
                        "channel_blacklist",
                        "cooldown_seconds",
                    )
                )
                else "This response uses only its own settings."
            )
        )
        return embed

    async def make_response_view_embed(
        self,
        guild: discord.Guild,
        response_store: dict,
        response_def: dict,
    ) -> discord.Embed:
        parsed_response_text, missing_emojis = await self.get_response_text_preview(
            guild,
            response_def["response_text"],
        )
        embed = discord.Embed(
            title=f"Auto Response #{response_def['id']}",
            description=response_def["name"],
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Match type",
            value=response_def["match_type"],
            inline=False,
        )
        embed.add_field(
            name="Priority",
            value=f"`{response_def.get('priority', 100)}`",
            inline=False,
        )
        embed.add_field(
            name="Triggers",
            value="\n".join(response_def["triggers"]),
            inline=False,
        )
        embed.add_field(
            name="Response text",
            value=parsed_response_text[:1024],
            inline=False,
        )
        if missing_emojis:
            embed.add_field(
                name="Missing emojis",
                value=", ".join(f"`:{emoji_name}:`" for emoji_name in missing_emojis)[:1024],
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
            value=(
                self.format_number(response_def.get("cooldown_seconds"))
                + f" (effective: {get_effective_setting(response_store, response_def, 'cooldown_seconds')})"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Created by {response_def.get('created_by', 'unknown')}")
        return embed

    def make_delete_confirm_embed(self, response_def: dict) -> discord.Embed:
        return discord.Embed(
            title=f"Delete response #{response_def['id']}?",
            description=f"This will remove `{response_def['name']}`.",
            color=discord.Color.red(),
        )

    def make_done_embed(self, title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green(),
        )


classes = inspect.getmembers(
    sys.modules[__name__],
    lambda member: inspect.isclass(member) and member.__module__ == __name__,
)
