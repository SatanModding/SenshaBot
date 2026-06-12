import re
import secrets
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
    "0",
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

DASH_POS = [
    8,
    13,
    18,
    23,
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
        self.uuid = ""
        for _ in range(HANDLE_LENGTH):
            if len(self.uuid) in DASH_POS:
                self.uuid += "-"
            else:
                c = secrets.randbelow(len(HANDLE_CHARS))
                self.uuid += HANDLE_CHARS[c]

        while "fag" in self.uuid:
            self.uuid = self.get_uuid()

        return self.uuid
