from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .keys import ExitKeyCombinations


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.toml"

DEFAULT_EXIT_KEY_COMBINATIONS: ExitKeyCombinations = (
    "Escape",
    ("Control", "q"),
)
DEFAULT_TIMEOUT_SECONDS = 0.0
DEFAULT_INTERVAL_SECONDS = 5.0
DEFAULT_OFFSET_PIXELS = 1
DEFAULT_MOVE_BACK_DELAY_SECONDS = 0.5


@dataclass(frozen=True)
class MovementSettings:
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    offset_pixels: int = DEFAULT_OFFSET_PIXELS
    move_back_delay_seconds: float = DEFAULT_MOVE_BACK_DELAY_SECONDS


@dataclass(frozen=True)
class AppSettings:
    exit_key_combinations: ExitKeyCombinations = DEFAULT_EXIT_KEY_COMBINATIONS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    movement: MovementSettings = field(default_factory=MovementSettings)


def load_toml_module():
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "TOML config requires Python 3.11+ or the tomli package. "
                "Run ./run.sh to install project dependencies."
            ) from error

    return tomllib


def load_toml_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}

    tomllib = load_toml_module()

    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def parse_key_combination(raw_combination: Any) -> tuple[str, ...]:
    if isinstance(raw_combination, str):
        raw_keys = raw_combination.split("+")
    elif isinstance(raw_combination, (list, tuple)):
        raw_keys = raw_combination
    else:
        raise ValueError("exit_key_combinations entries must be strings")

    keys = []

    for raw_key in raw_keys:
        if not isinstance(raw_key, str):
            raise ValueError("exit key names must be strings")

        key = raw_key.strip()

        if key:
            keys.append(key)

    return tuple(keys)


def parse_exit_key_combinations(value: Any) -> ExitKeyCombinations:
    combinations = []

    if isinstance(value, str):
        raw_combinations = value.split(",")
    elif isinstance(value, (list, tuple)):
        raw_combinations = value
    else:
        raise ValueError(
            "exit_key_combinations must be a string or an array of strings"
        )

    for raw_combination in raw_combinations:
        keys = parse_key_combination(raw_combination)

        if not keys:
            continue

        if len(keys) == 1:
            combinations.append(keys[0])
        else:
            combinations.append(keys)

    if not combinations:
        raise ValueError("exit_key_combinations must contain at least one key")

    return tuple(combinations)


def parse_finite_seconds(value: Any, name: str, default: float) -> float:
    if value is None:
        return default

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")

    seconds = float(value)

    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"{name} must be a finite number 0 or greater")

    return seconds


def parse_positive_seconds(value: Any, name: str, default: float) -> float:
    seconds = parse_finite_seconds(value, name, default)

    if seconds == 0:
        raise ValueError(f"{name} must be greater than 0")

    return seconds


def parse_timeout_seconds(value: Any) -> float:
    return parse_finite_seconds(
        value,
        "timeout_seconds",
        DEFAULT_TIMEOUT_SECONDS,
    )


def parse_offset_pixels(value: Any) -> int:
    if value is None:
        return DEFAULT_OFFSET_PIXELS

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("movement.offset_pixels must be a non-negative integer")

    if value < 0:
        raise ValueError("movement.offset_pixels must be 0 or greater")

    return value


def parse_movement_settings(config: dict[str, Any]) -> MovementSettings:
    raw_movement = config.get("movement", {})

    if not isinstance(raw_movement, dict):
        raise ValueError("movement must be a TOML table")

    return MovementSettings(
        interval_seconds=parse_positive_seconds(
            raw_movement.get("interval_seconds"),
            "movement.interval_seconds",
            DEFAULT_INTERVAL_SECONDS,
        ),
        offset_pixels=parse_offset_pixels(raw_movement.get("offset_pixels")),
        move_back_delay_seconds=parse_finite_seconds(
            raw_movement.get("move_back_delay_seconds"),
            "movement.move_back_delay_seconds",
            DEFAULT_MOVE_BACK_DELAY_SECONDS,
        ),
    )


def load_settings(path: Path = CONFIG_FILE) -> AppSettings:
    config = load_toml_config(path)
    raw_combinations = config.get("exit_key_combinations")

    if raw_combinations is None:
        exit_key_combinations = DEFAULT_EXIT_KEY_COMBINATIONS
    else:
        exit_key_combinations = parse_exit_key_combinations(raw_combinations)

    return AppSettings(
        exit_key_combinations=exit_key_combinations,
        timeout_seconds=parse_timeout_seconds(config.get("timeout_seconds")),
        movement=parse_movement_settings(config),
    )
