import ctypes
import os
import platform
import threading
import time
from pathlib import Path


INTERVAL = 5
OFFSET = 1
MOVE_BACK_DELAY = 0.5
CONFIG_FILE = Path(__file__).with_name("config.env")
DEFAULT_EXIT_KEY_COMBINATIONS = (
    "Escape",
    ("Control", "q"),
)


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


def normalize_key_name(key_name):
    key_name = str(key_name)

    if key_name == " ":
        return "space"

    key_name = key_name.strip()
    lowered = key_name.lower()

    if len(key_name) == 1:
        return lowered

    return KEY_ALIASES.get(lowered, key_name)


def normalize_key_combination(combination):
    if isinstance(combination, str):
        combination = (combination,)

    return frozenset(normalize_key_name(key) for key in combination)


def strip_inline_comment(value):
    comment_start = value.find(" #")

    if comment_start == -1:
        return value

    return value[:comment_start].strip()


def load_env_config(path=CONFIG_FILE):
    config = {}

    if not path.exists():
        return config

    with path.open(encoding="utf-8") as config_file:
        for line_number, line in enumerate(config_file, start=1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                raise ValueError(f"Invalid config line {line_number}: {line}")

            name, value = line.split("=", 1)
            config[name.strip()] = strip_inline_comment(value.strip())

    return config


def parse_exit_key_combinations(value):
    combinations = []

    for raw_combination in value.split(","):
        keys = tuple(
            key.strip()
            for key in raw_combination.split("+")
            if key.strip()
        )

        if not keys:
            continue

        if len(keys) == 1:
            combinations.append(keys[0])
        else:
            combinations.append(keys)

    if not combinations:
        raise ValueError("EXIT_KEY_COMBINATIONS must contain at least one key")

    return tuple(combinations)


def load_exit_key_combinations(path=CONFIG_FILE):
    config = load_env_config(path)
    raw_combinations = config.get("EXIT_KEY_COMBINATIONS")

    if raw_combinations is None:
        return DEFAULT_EXIT_KEY_COMBINATIONS

    return parse_exit_key_combinations(raw_combinations)


def build_x11_keysym_names(XK):
    keysym_names = {
        XK.XK_space: "space",
        XK.XK_Escape: "Escape",
        XK.XK_Return: "Enter",
        XK.XK_KP_Enter: "Enter",
        XK.XK_BackSpace: "BackSpace",
        XK.XK_Tab: "Tab",
        XK.XK_Shift_L: "Shift",
        XK.XK_Shift_R: "Shift",
        XK.XK_Control_L: "Control",
        XK.XK_Control_R: "Control",
        XK.XK_Alt_L: "Alt",
        XK.XK_Alt_R: "Alt",
        XK.XK_Meta_L: "Super",
        XK.XK_Meta_R: "Super",
        XK.XK_Super_L: "Super",
        XK.XK_Super_R: "Super",
        XK.XK_Delete: "Delete",
        XK.XK_Insert: "Insert",
        XK.XK_Home: "Home",
        XK.XK_End: "End",
        XK.XK_Page_Up: "Page_Up",
        XK.XK_Page_Down: "Page_Down",
        XK.XK_Left: "Left",
        XK.XK_Right: "Right",
        XK.XK_Up: "Up",
        XK.XK_Down: "Down",
    }

    for number in range(1, 13):
        keysym_names[getattr(XK, f"XK_F{number}")] = f"F{number}"

    return keysym_names


class ExitKeyMatcher:
    def __init__(self, combinations):
        self.combinations = tuple(
            combination
            for combination in (
                normalize_key_combination(combination)
                for combination in combinations
            )
            if combination
        )
        self.pressed_keys = set()

    def press(self, key_name):
        self.pressed_keys.add(normalize_key_name(key_name))
        return self.should_exit()

    def release(self, key_name):
        self.pressed_keys.discard(normalize_key_name(key_name))

    def should_exit(self):
        return any(
            combination.issubset(self.pressed_keys)
            for combination in self.combinations
        )


class LinuxX11MouseKeeper:
    def __init__(self, offset=OFFSET):
        from Xlib import display

        self.offset = offset
        self.display = display.Display()
        self.root = self.display.screen().root

    def get_pos(self):
        pointer = self.root.query_pointer()
        return pointer.root_x, pointer.root_y

    def set_pos(self, x, y):
        self.root.warp_pointer(x, y)
        self.display.sync()


class LinuxX11BlackoutOverlay:
    def __init__(self, stop_event, exit_key_combinations):
        from Xlib import X, XK, display

        self.X = X
        self.XK = XK
        self.keysym_names = build_x11_keysym_names(XK)
        self.modifier_masks = (
            (X.ShiftMask, "Shift"),
            (X.ControlMask, "Control"),
            (X.Mod1Mask, "Alt"),
            (X.Mod4Mask, "Super"),
        )
        self.stop_event = stop_event
        self.exit_keys = ExitKeyMatcher(exit_key_combinations)
        self.display = display.Display()
        self.screen = self.display.screen()
        self.window = self.screen.root.create_window(
            0,
            0,
            self.screen.width_in_pixels,
            self.screen.height_in_pixels,
            0,
            self.screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,
            background_pixel=self.screen.black_pixel,
            event_mask=X.KeyPressMask | X.KeyReleaseMask,
            override_redirect=True,
        )

    def run(self):
        self.window.map()
        self.display.sync()
        self.focus()

        try:
            next_focus = 0

            while not self.stop_event.is_set():
                while self.display.pending_events():
                    event = self.display.next_event()

                    if event.type == self.X.KeyPress and self.key_pressed(event):
                        self.stop_event.set()
                        return

                    if event.type == self.X.KeyRelease:
                        self.key_released(event)

                now = time.monotonic()

                if now >= next_focus:
                    self.focus()
                    next_focus = now + 1

                self.stop_event.wait(0.05)
        finally:
            self.close()

    def focus(self):
        self.window.configure(stack_mode=self.X.Above)
        self.window.set_input_focus(self.X.RevertToParent, self.X.CurrentTime)
        self.window.grab_keyboard(
            False,
            self.X.GrabModeAsync,
            self.X.GrabModeAsync,
            self.X.CurrentTime,
        )
        self.display.flush()

    def get_key_name(self, event):
        keysym = self.display.keycode_to_keysym(event.detail, 0)
        key_name = self.keysym_names.get(keysym)

        if key_name is not None:
            return key_name

        if 32 <= keysym <= 126:
            return chr(keysym)

        return self.XK.keysym_to_string(keysym)

    def get_modifier_names(self, event):
        return [
            key_name
            for mask, key_name in self.modifier_masks
            if event.state & mask
        ]

    def key_pressed(self, event):
        key_name = self.get_key_name(event)

        for modifier_name in self.get_modifier_names(event):
            self.exit_keys.press(modifier_name)

        if key_name is None:
            return False

        return self.exit_keys.press(key_name)

    def key_released(self, event):
        key_name = self.get_key_name(event)

        if key_name is not None:
            self.exit_keys.release(key_name)

    def close(self):
        try:
            self.display.ungrab_keyboard(self.X.CurrentTime)
            self.window.destroy()
            self.display.sync()
        finally:
            self.display.close()


class WindowsMouseKeeper:
    def __init__(self, offset=OFFSET):
        self.offset = offset
        self.user = ctypes.windll.user32

    def get_pos(self):
        class Point(ctypes.Structure):
            _fields_ = [
                ("x", ctypes.c_long),
                ("y", ctypes.c_long),
            ]

        point = Point()
        self.user.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def set_pos(self, x, y):
        self.user.SetCursorPos(x, y)


class TkBlackoutOverlay:
    def __init__(self, stop_event, exit_key_combinations):
        import tkinter as tk

        self.stop_event = stop_event
        self.exit_keys = ExitKeyMatcher(exit_key_combinations)
        self.closed = False
        self.root = tk.Tk()
        self.root.configure(background="black", cursor="none")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.bind("<KeyPress>", self.key_pressed)
        self.root.bind("<KeyRelease>", self.key_released)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.focus)

    def focus(self):
        if self.stop_event.is_set():
            return

        self.root.lift()
        self.root.focus_force()
        self.root.after(1000, self.focus)

    def close(self, _event=None):
        if self.closed:
            return

        self.closed = True
        self.stop_event.set()
        self.root.destroy()

    def key_pressed(self, event):
        if self.exit_keys.press(event.keysym):
            self.close()

    def key_released(self, event):
        self.exit_keys.release(event.keysym)

    def run(self):
        self.root.mainloop()


def create_mouse_keeper():
    system = platform.system()
    is_x11 = os.environ.get("XDG_SESSION_TYPE") == "x11"

    if system == "Linux" and is_x11:
        return LinuxX11MouseKeeper()

    if system == "Windows":
        return WindowsMouseKeeper()

    return None


def create_blackout_overlay(stop_event, exit_key_combinations):
    system = platform.system()
    is_x11 = os.environ.get("XDG_SESSION_TYPE") == "x11"

    if system == "Linux" and is_x11:
        return LinuxX11BlackoutOverlay(
            stop_event,
            exit_key_combinations,
        )

    if system == "Windows":
        return TkBlackoutOverlay(
            stop_event,
            exit_key_combinations,
        )

    return None


def keep_mouse_alive(mouse, stop_event):
    while not stop_event.is_set():
        x, y = mouse.get_pos()
        mouse.set_pos(x + mouse.offset, y)
        stop_event.wait(MOVE_BACK_DELAY)
        mouse.set_pos(x, y)
        stop_event.wait(INTERVAL)


def main():
    mouse = create_mouse_keeper()

    if mouse is None:
        print("Only works on Linux X11 and Windows")
        return

    stop_event = threading.Event()
    exit_key_combinations = load_exit_key_combinations()
    overlay = create_blackout_overlay(
        stop_event,
        exit_key_combinations,
    )

    if overlay is None:
        print("Only works on Linux X11 and Windows")
        return

    worker = threading.Thread(
        target=keep_mouse_alive,
        args=(mouse, stop_event),
        daemon=True,
    )

    worker.start()

    try:
        overlay.run()
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        worker.join(timeout=MOVE_BACK_DELAY + 1)


if __name__ == "__main__":
    main()
