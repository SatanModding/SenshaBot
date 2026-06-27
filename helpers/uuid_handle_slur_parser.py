from helpers.slurs import slurs
from helpers.uuid_handle import DataType, handle_utils, uuid_utils


class UUIDHandleSlurParser:
    def __init__(self):
        self.type: DataType = DataType.NONE
        self.msg: str = ""
        self.uuid_utils = uuid_utils()
        self.handle_utils = handle_utils()

    def test_extractor(self):
        msg_list = [
            "yeah so i was using d8f67f5c-fag3-40c9-8537-90c571306ff7 as my uuid and then it got mad at me :(",
            "oh wow i guess it gets mad at the handle h80cd529dg1680g4eaegbfageb53332d81adb, so weird",
        ]

        for msg in msg_list:
            print(f"testing msg: {msg}")
            self.uuidhandle_extractor(msg)
            print()

    def uuidhandle_extractor(self, msg: str):
        uuid_result = self.uuid_utils.uuid_pattern.search(msg)
        handle_result = self.handle_utils.handle_pattern.search(msg)

        extracted = ""
        if uuid_result:
            self.type = DataType.UUID
            extracted = uuid_result.group(self.type.name.lower())
        elif handle_result:
            self.type = DataType.HANDLE
            extracted = handle_result.group(self.type.name.lower())

        if slurs().check(extracted):
            return extracted

        return None
