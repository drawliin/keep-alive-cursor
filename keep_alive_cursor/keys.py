from __future__ import annotations


KeyCombination = str | tuple[str, ...]
ExitKeyCombinations = tuple[KeyCombination, ...]


KEY_ALIASES = {
    " ": "space",
    "alt_l": "Alt",
    "alt_r": "Alt",
    "control_l": "Control",
    "control_r": "Control",
    "ctrl": "Control",
    "cmd": "Super",
    "command": "Super",
    "esc": "Escape",
    "enter": "Enter",
    "meta_l": "Super",
    "meta_r": "Super",
    "option": "Alt",
    "return": "Enter",
    "shift_l": "Shift",
    "shift_r": "Shift",
    "spacebar": "space",
    "super_l": "Super",
    "super_r": "Super",
    "win": "Super",
    "windows": "Super",
}


def normalize_key_name(key_name: str) -> str:
    key_name = str(key_name)

    if key_name == " ":
        return "space"

    key_name = key_name.strip()
    lowered = key_name.lower()

    if len(key_name) == 1:
        return lowered

    return KEY_ALIASES.get(lowered, key_name)


def normalize_key_combination(combination: KeyCombination) -> frozenset[str]:
    if isinstance(combination, str):
        combination = (combination,)

    return frozenset(normalize_key_name(key) for key in combination)


class ExitKeyMatcher:
    def __init__(self, combinations: ExitKeyCombinations):
        self.combinations = tuple(
            combination
            for combination in (
                normalize_key_combination(combination)
                for combination in combinations
            )
            if combination
        )
        self.pressed_keys: set[str] = set()

    def press(self, key_name: str) -> bool:
        self.pressed_keys.add(normalize_key_name(key_name))
        return self.should_exit()

    def release(self, key_name: str) -> None:
        self.pressed_keys.discard(normalize_key_name(key_name))

    def should_exit(self) -> bool:
        return any(
            combination.issubset(self.pressed_keys)
            for combination in self.combinations
        )
