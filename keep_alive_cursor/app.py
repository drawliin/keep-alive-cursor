from __future__ import annotations

import threading

from .config import AppSettings, MovementSettings, load_settings
from .mouse import MouseController, create_mouse_controller
from .overlays import create_blackout_overlay


UNSUPPORTED_PLATFORM_MESSAGE = "Only works on Linux X11 and Windows"


def keep_mouse_alive(
    mouse: MouseController,
    movement: MovementSettings,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        x, y = mouse.get_pos()
        mouse.set_pos(x + movement.offset_pixels, y)

        if stop_event.wait(movement.move_back_delay_seconds):
            mouse.set_pos(x, y)
            break

        mouse.set_pos(x, y)
        stop_event.wait(movement.interval_seconds)


def start_timeout_timer(
    timeout_seconds: float,
    stop_event: threading.Event,
) -> threading.Timer | None:
    if timeout_seconds == 0:
        return None

    timer = threading.Timer(timeout_seconds, stop_event.set)
    timer.daemon = True
    timer.start()
    return timer


def run(settings: AppSettings) -> int:
    mouse = create_mouse_controller()

    if mouse is None:
        print(UNSUPPORTED_PLATFORM_MESSAGE)
        return 1

    stop_event = threading.Event()
    overlay = create_blackout_overlay(
        stop_event,
        settings.exit_key_combinations,
    )

    if overlay is None:
        print(UNSUPPORTED_PLATFORM_MESSAGE)
        return 1

    worker = threading.Thread(
        target=keep_mouse_alive,
        args=(mouse, settings.movement, stop_event),
        daemon=True,
    )

    worker.start()
    timeout_timer = start_timeout_timer(settings.timeout_seconds, stop_event)

    try:
        overlay.run()
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        if timeout_timer is not None:
            timeout_timer.cancel()

        stop_event.set()
        worker.join(timeout=settings.movement.move_back_delay_seconds + 1)

    return 0


def main() -> int:
    try:
        settings = load_settings()
    except (RuntimeError, ValueError) as error:
        print(f"Configuration error: {error}")
        return 2

    return run(settings)
