import re


TEXT_EMOJI_PATTERN = re.compile(r":[a-zA-Z0-9_]+:")
CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:[a-zA-Z0-9_]+:\d+>")


def default_response_settings() -> dict:
    return {
        "ignore_mods": True,
        "exempt_role_ids": [],
        "channel_whitelist": [],
        "channel_blacklist": [],
        "cooldown_seconds": 300,
    }


def default_response_store() -> dict:
    return {
        "settings": default_response_settings(),
        "entries": {},
        "next_response_id": 1,
    }


def normalize_priority(value):
    if isinstance(value, int):
        if 0 <= value <= 100:
            return value
        return None

    return None


def normalize_bool_override(value):
    if value == "skip":
        return None
    if isinstance(value, str):
        lowered_value = value.lower()
        if lowered_value == "true":
            return True
        if lowered_value == "false":
            return False
        if lowered_value == "skip":
            return None
    return value


async def get_or_setup_responses(storage, guild_id: str) -> dict:
    guild_id = str(guild_id)
    guild = storage.settings["guilds"][guild_id]
    responses = guild.get("responses")
    override_keys = (
        "ignore_mods",
        "exempt_role_ids",
        "channel_whitelist",
        "channel_blacklist",
        "cooldown_seconds",
    )

    if not isinstance(responses, dict):
        guild["responses"] = default_response_store()
        await storage.write_file_to_disk()
        return guild["responses"]

    changed = False
    if "settings" not in responses or not isinstance(responses["settings"], dict):
        responses["settings"] = default_response_settings()
        changed = True
    else:
        defaults = default_response_settings()
        for key, value in defaults.items():
            if key not in responses["settings"]:
                responses["settings"][key] = value
                changed = True
        normalized_ignore_mods = normalize_bool_override(
            responses["settings"].get("ignore_mods")
        )
        if responses["settings"].get("ignore_mods") != normalized_ignore_mods:
            responses["settings"]["ignore_mods"] = normalized_ignore_mods
            changed = True

    if "entries" not in responses or not isinstance(responses["entries"], dict):
        responses["entries"] = {}
        changed = True
    else:
        for response_def in responses["entries"].values():
            if not isinstance(response_def, dict):
                continue
            normalized_ignore_mods = normalize_bool_override(
                response_def.get("ignore_mods")
            )
            if response_def.get("ignore_mods") != normalized_ignore_mods:
                response_def["ignore_mods"] = normalized_ignore_mods
                changed = True

            normalized_priority = normalize_priority(response_def.get("priority"))
            if normalized_priority is None:
                normalized_priority = 100
            if response_def.get("priority") != normalized_priority:
                response_def["priority"] = normalized_priority
                changed = True
            for key in override_keys:
                if response_def.get(key) == "skip":
                    response_def[key] = None
                    changed = True

    if "next_response_id" not in responses or not isinstance(
        responses["next_response_id"], int
    ):
        responses["next_response_id"] = 1
        changed = True

    if changed:
        await storage.write_file_to_disk()

    return responses


async def get_response_settings(storage, guild_id: str) -> dict:
    response_store = await get_or_setup_responses(storage, guild_id)
    return response_store["settings"]


async def update_response_settings(storage, guild_id: str, new_settings: dict) -> dict:
    response_store = await get_or_setup_responses(storage, guild_id)
    response_store["settings"].update(new_settings)
    await storage.write_file_to_disk()
    return response_store["settings"]


async def list_responses(storage, guild_id: str) -> dict:
    response_store = await get_or_setup_responses(storage, guild_id)
    return response_store["entries"]


async def get_response(storage, guild_id: str, response_id: int) -> dict | None:
    response_store = await get_or_setup_responses(storage, guild_id)
    return response_store["entries"].get(str(response_id))


async def add_response(storage, guild_id: str, response_def: dict) -> dict:
    response_store = await get_or_setup_responses(storage, guild_id)
    response_id = response_store["next_response_id"]
    response_store["next_response_id"] += 1
    response_def["id"] = response_id
    response_store["entries"][str(response_id)] = response_def
    await storage.write_file_to_disk()
    return response_def


async def update_response(storage, guild_id: str, response_id: int, updates: dict) -> dict | None:
    response_store = await get_or_setup_responses(storage, guild_id)
    response_def = response_store["entries"].get(str(response_id))
    if response_def is None:
        return None

    response_def.update(updates)
    await storage.write_file_to_disk()
    return response_def


async def toggle_response(storage, guild_id: str, response_id: int) -> dict | None:
    response_store = await get_or_setup_responses(storage, guild_id)
    response_def = response_store["entries"].get(str(response_id))
    if response_def is None:
        return None

    response_def["enabled"] = not response_def.get("enabled", True)
    await storage.write_file_to_disk()
    return response_def


async def delete_response(storage, guild_id: str, response_id: int) -> dict | None:
    response_store = await get_or_setup_responses(storage, guild_id)
    response_def = response_store["entries"].pop(str(response_id), None)
    if response_def is None:
        return None

    await storage.write_file_to_disk()
    return response_def


def get_effective_setting(response_store: dict, response_def: dict, key: str):
    value = response_def.get(key)
    if value is None or value == "skip":
        return response_store["settings"].get(key)
    return value


def strip_emoji_tokens(content: str) -> str:
    content = CUSTOM_EMOJI_PATTERN.sub(" ", content)
    content = TEXT_EMOJI_PATTERN.sub(" ", content)
    return content


def get_emoji_tokens(content: str) -> list[str]:
    return CUSTOM_EMOJI_PATTERN.findall(content) + TEXT_EMOJI_PATTERN.findall(content)


def message_matches_response(content: str, response_def: dict) -> bool:
    match_type = response_def.get("match_type")
    triggers = response_def.get("triggers", [])

    if not content or not triggers:
        return False

    lowered_content = strip_emoji_tokens(content).lower()

    if match_type == "word":
        pattern = r"\b(?:{})\b".format("|".join(re.escape(word) for word in triggers))
        return re.search(pattern, lowered_content, re.IGNORECASE) is not None

    if match_type == "phrase":
        return any(trigger.lower() in lowered_content for trigger in triggers)

    if match_type == "regex":
        try:
            return re.search(triggers[0], lowered_content, re.IGNORECASE) is not None
        except re.error:
            return False

    if match_type == "emoji":
        lowered_tokens = [token.lower() for token in get_emoji_tokens(content)]
        return any(trigger.lower() in lowered_tokens for trigger in triggers)

    return False
