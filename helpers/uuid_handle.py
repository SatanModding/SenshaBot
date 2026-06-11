import re
import secrets
import uuid
from enum import Enum

HANDLE_LENGTH = 36
HANDLE_CHARS = [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    '0',
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
]


class DataType(Enum):
    UUID = 0
    HANDLE = 1
    BOTH = 2
    NONE = 3


class handle_utils:
    def __init__(self) -> None:
        self.handle = self.get_handle()
        self.handle_pattern = re.compile(r"(?P<handle>[hH][A-Ga-g\d]{36})")

    def get_handle(self) -> str:
        self.handle = "h"
        for _ in range(HANDLE_LENGTH):
            c = secrets.randbelow(len(HANDLE_CHARS))
            self.handle += HANDLE_CHARS[c]

        while "fag" in self.handle:
            self.handle = self.get_handle()

        return self.handle


class uuid_utils:
    def __init__(self) -> None:
        self.uuid = self.get_uuid()
        self.uuid_pattern = re.compile(
            r"(?P<uuid>[A-Ga-g\d]{8}-[A-Ga-g\d]{4}-[A-Ga-g\d]{4}-[A-Ga-g\d]{4}-[A-Ga-g\d]{12})"
        )

    def get_uuid(self) -> str:
        # not technically necessary but i like the idea of adding more
        # randomness into the uuid gen process
        return str(uuid.uuid5(uuid.uuid4(), secrets.token_hex(64)))
