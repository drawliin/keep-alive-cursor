# Keep Alive Cursor

A small Python app that keeps your system from appearing idle by moving the mouse cursor by 1 pixel and then moving it back while a black fullscreen overlay is shown.

It currently supports:
- Linux sessions running on X11
- Windows

## How It Works

When started, the script opens a black fullscreen window. While that window is active, every 5 seconds the script:
1. Reads the current mouse position
2. Moves the cursor by 1 pixel
3. Waits 0.5 seconds
4. Moves the cursor back to its original position

Press one of the configured keyboard buttons to close the fullscreen overlay and stop the script.

## Requirements

- Python 3
- Dependencies from `requirements.txt`

Windows support uses Tkinter for the fullscreen overlay. Most Python for Windows installers include it.
TOML configuration uses Python's built-in parser on Python 3.11+ and `tomli` on older versions.

## Usage

Run the script with:

```bash
./run.sh
```

The runner creates a local virtual environment, installs dependencies, and starts the script.

## Platform Notes

### Linux

Linux support only works when your desktop session is using X11.

You can check that with:

```bash
echo $XDG_SESSION_TYPE
```

If the result is `x11`, the script should work.

### Windows

The script uses the Windows `user32` API through `ctypes`, so no extra Windows-specific setup is needed beyond Python.

## Configuration

The fullscreen exit buttons, automatic timeout, and movement behavior are controlled in [`config.toml`](/home/hhamouich/Desktop/keep-alive-cursor/config.toml):

```toml
exit_key_combinations = ["spacebar+d"]
timeout_seconds = 0

[movement]
interval_seconds = 5
offset_pixels = 1
move_back_delay_seconds = 0.5
```

Use one key by writing the key name, like `Escape` or `F12`.
Use a key combo with `+`, like `Control+q` or `Control+Shift+q`.
Use `spacebar` for the space key.
Allow multiple exit options by adding more strings to the array.
Set `timeout_seconds` to the number of seconds the script should run before stopping itself.
Set `timeout_seconds = 0` to run until you stop it manually.
Set `movement.interval_seconds` to the wait time between cursor nudges; it must be greater than `0`.
Set `movement.offset_pixels` to how far the cursor moves.
Set `movement.move_back_delay_seconds` to how long the cursor stays offset before moving back.

In the current config, hold `Spacebar` and press `d` to exit.

## Code Layout

- [`script.py`](/home/hhamouich/Desktop/keep-alive-cursor/script.py) is a compatibility entrypoint.
- [`keep_alive_cursor/app.py`](/home/hhamouich/Desktop/keep-alive-cursor/keep_alive_cursor/app.py) coordinates settings, timers, overlay, and mouse movement.
- [`keep_alive_cursor/config.py`](/home/hhamouich/Desktop/keep-alive-cursor/keep_alive_cursor/config.py) loads and validates TOML settings.
- [`keep_alive_cursor/keys.py`](/home/hhamouich/Desktop/keep-alive-cursor/keep_alive_cursor/keys.py) normalizes exit keys and key combinations.
- [`keep_alive_cursor/mouse.py`](/home/hhamouich/Desktop/keep-alive-cursor/keep_alive_cursor/mouse.py) contains platform mouse controllers.
- [`keep_alive_cursor/overlays.py`](/home/hhamouich/Desktop/keep-alive-cursor/keep_alive_cursor/overlays.py) contains fullscreen overlay implementations.

## Limitations

- It does not support Wayland sessions on Linux
- It runs continuously until you stop it manually when `timeout_seconds` is `0`
- It physically moves the mouse cursor, which may interfere if you are actively using it at the same time

## Stopping the Script

Press one of the configured exit buttons while the black fullscreen overlay is focused. You can also press `Ctrl+C` in the terminal to stop it, or set `timeout_seconds` to stop it automatically.
