# Keep Alive Cursor

A small Python script that keeps your system from appearing idle by moving the mouse cursor by 1 pixel and then moving it back.

It currently supports:
- Linux sessions running on X11
- Windows

## How It Works

Every 5 seconds, the script:
1. Reads the current mouse position
2. Moves the cursor by 1 pixel
3. Waits 0.5 seconds
4. Moves the cursor back to its original position

## Requirements

- Python 3
- Dependencies from `requirements.txt`

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

Run the script with:

```bash
python script.py
```

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

The behavior is controlled by these constants in [`script.py`](/home/hhamouich/Desktop/keep-alive-cursor/script.py):

- `INTERVAL = 5` sets the wait time between cursor nudges
- `OFFSET = 1` sets how far the cursor moves

You can edit those values to make the movement more or less frequent.

## Limitations

- It does not support Wayland sessions on Linux
- It runs continuously until you stop it manually
- It physically moves the mouse cursor, which may interfere if you are actively using it at the same time

## Stopping the Script

Press `Ctrl+C` in the terminal to stop it.
