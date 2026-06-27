SLUR_LIST = ["fag", "cunt"]


class slurs:
    def __init__(self, slur_list: list = SLUR_LIST) -> None:
        self.slur_list = slur_list

    def check(self, msg: str) -> bool:
        slur_found = False

        for slur in self.slur_list:
            slur_found = slur in msg.lower()
            if slur_found:
                break

        return slur_found
