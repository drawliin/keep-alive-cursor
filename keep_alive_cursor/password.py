from __future__ import annotations


SUBMIT_KEY_NAMES = {"Enter", "KP_Enter", "Return"}
BACKSPACE_KEY_NAMES = {"BackSpace", "Backspace"}
CLEAR_KEY_NAMES = {"Escape"}


class ExitPasswordMatcher:
    def __init__(self, password: str):
        self.password = password
        self.buffer = ""
        self.failed = False

    @property
    def masked_buffer(self) -> str:
        return "*" * len(self.buffer)

    def press(
        self,
        key_name: str | None = None,
        character: str | None = None,
    ) -> bool:
        if key_name in SUBMIT_KEY_NAMES:
            return self.submit()

        if key_name in BACKSPACE_KEY_NAMES:
            self.failed = False
            self.backspace()
            return False

        if key_name in CLEAR_KEY_NAMES:
            self.failed = False
            self.clear()
            return False

        if (
            character is None
            or len(character) != 1
            or not character.isprintable()
        ):
            return False

        self.failed = False
        self.buffer += character
        return False

    def submit(self) -> bool:
        matches = self.buffer == self.password
        self.clear()
        self.failed = not matches
        return matches

    def backspace(self) -> None:
        self.buffer = self.buffer[:-1]

    def clear(self) -> None:
        self.buffer = ""
