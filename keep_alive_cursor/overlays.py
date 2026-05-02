from __future__ import annotations

import os
import platform
import threading
import time
from typing import Protocol

from .password import ExitPasswordMatcher


PROMPT_TITLE = "Enter password"
PROMPT_HINT = "Press Enter to unlock"
PROMPT_ERROR = "Incorrect password"
X11_CHARACTER_WIDTH = 8


class BlackoutOverlay(Protocol):
    def run(self) -> None:
        ...


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


class LinuxX11BlackoutOverlay:
    def __init__(
        self,
        stop_event: threading.Event,
        exit_password: str,
    ):
        from Xlib import X, XK, display

        self.X = X
        self.XK = XK
        self.keysym_names = build_x11_keysym_names(XK)
        self.non_text_modifier_mask = X.ControlMask | X.Mod1Mask | X.Mod4Mask
        self.stop_event = stop_event
        self.exit_password = ExitPasswordMatcher(exit_password)
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
            event_mask=X.KeyPressMask | X.ExposureMask,
            override_redirect=True,
        )
        self.text_gc = self.window.create_gc(
            foreground=self.screen.white_pixel,
            background=self.screen.black_pixel,
            line_width=2,
        )

    def run(self) -> None:
        self.window.map()
        self.display.sync()
        self.focus()
        self.draw_prompt()

        try:
            next_focus = 0

            while not self.stop_event.is_set():
                while self.display.pending_events():
                    event = self.display.next_event()

                    if event.type == self.X.Expose:
                        self.draw_prompt()

                    if event.type == self.X.KeyPress:
                        if self.key_pressed(event):
                            self.stop_event.set()
                            return

                        self.draw_prompt()

                now = time.monotonic()

                if now >= next_focus:
                    self.focus()
                    next_focus = now + 1

                self.stop_event.wait(0.05)
        finally:
            self.close()

    def focus(self) -> None:
        self.window.configure(stack_mode=self.X.Above)
        self.window.set_input_focus(self.X.RevertToParent, self.X.CurrentTime)
        self.window.grab_keyboard(
            False,
            self.X.GrabModeAsync,
            self.X.GrabModeAsync,
            self.X.CurrentTime,
        )
        self.display.flush()

    def get_key_name(self, event) -> str | None:
        keysym = self.display.keycode_to_keysym(event.detail, 0)
        key_name = self.keysym_names.get(keysym)

        if key_name is not None:
            return key_name

        if 32 <= keysym <= 126:
            return chr(keysym)

        return self.XK.keysym_to_string(keysym)

    def get_key_character(self, event) -> str | None:
        if event.state & self.non_text_modifier_mask:
            return None

        index = 1 if event.state & self.X.ShiftMask else 0
        keysym = self.display.keycode_to_keysym(event.detail, index)
        character = self.display.lookup_string(keysym)

        if (
            character is None
            or len(character) != 1
            or not character.isprintable()
        ):
            return None

        if event.state & self.X.LockMask and character.isalpha():
            return character.swapcase()

        return character

    def key_pressed(self, event) -> bool:
        key_name = self.get_key_name(event)
        character = self.get_key_character(event)
        return self.exit_password.press(key_name, character)

    def draw_prompt(self) -> None:
        width = self.screen.width_in_pixels
        height = self.screen.height_in_pixels
        field_width = min(480, max(280, width // 3))
        field_height = 56
        field_x = (width - field_width) // 2
        field_y = max(96, height // 2 - 28)

        self.window.clear_area()
        self.draw_centered_text(PROMPT_TITLE, field_y - 36)
        self.window.rectangle(
            self.text_gc,
            field_x,
            field_y,
            field_width,
            field_height,
        )

        masked_password = self.visible_masked_password(field_width - 36)
        self.window.image_text(
            self.text_gc,
            field_x + 18,
            field_y + 36,
            masked_password,
        )
        self.draw_centered_text(PROMPT_HINT, field_y + field_height + 34)

        if self.exit_password.failed:
            self.draw_centered_text(PROMPT_ERROR, field_y + field_height + 62)

        self.display.flush()

    def draw_centered_text(self, text: str, y: int) -> None:
        text_width = len(text) * X11_CHARACTER_WIDTH
        x = max(0, (self.screen.width_in_pixels - text_width) // 2)
        self.window.image_text(self.text_gc, x, y, text)

    def visible_masked_password(self, max_width: int) -> str:
        max_characters = max(1, max_width // X11_CHARACTER_WIDTH)
        return self.exit_password.masked_buffer[-max_characters:]

    def close(self) -> None:
        try:
            self.display.ungrab_keyboard(self.X.CurrentTime)
            self.window.destroy()
            self.display.sync()
        finally:
            self.display.close()


class TkBlackoutOverlay:
    def __init__(
        self,
        stop_event: threading.Event,
        exit_password: str,
    ):
        import tkinter as tk

        self.stop_event = stop_event
        self.exit_password = ExitPasswordMatcher(exit_password)
        self.closed = False
        self.root = tk.Tk()
        self.root.configure(background="black", cursor="none")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.bind("<KeyPress>", self.key_pressed)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.focus)
        self.root.after(100, self.watch_stop_event)
        self.password_text = tk.StringVar()
        self.status_text = tk.StringVar()

        container = tk.Frame(self.root, background="black")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            container,
            text=PROMPT_TITLE,
            background="black",
            foreground="white",
            font=("Segoe UI", 28, "bold"),
        ).pack(pady=(0, 18))

        tk.Label(
            container,
            textvariable=self.password_text,
            anchor="w",
            background="black",
            foreground="white",
            font=("Segoe UI", 22),
            width=28,
            padx=18,
            pady=12,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
        ).pack()

        tk.Label(
            container,
            text=PROMPT_HINT,
            background="black",
            foreground="white",
            font=("Segoe UI", 12),
        ).pack(pady=(18, 0))

        tk.Label(
            container,
            textvariable=self.status_text,
            background="black",
            foreground="white",
            font=("Segoe UI", 12),
        ).pack(pady=(8, 0))
        self.update_prompt()

    def focus(self) -> None:
        if self.stop_event.is_set():
            return

        self.root.lift()
        self.root.focus_force()
        self.root.after(1000, self.focus)

    def watch_stop_event(self) -> None:
        if self.closed:
            return

        if self.stop_event.is_set():
            self.close()
            return

        self.root.after(100, self.watch_stop_event)

    def close(self, _event=None) -> None:
        if self.closed:
            return

        self.closed = True
        self.stop_event.set()
        self.root.destroy()

    def key_pressed(self, event) -> None:
        if self.exit_password.press(event.keysym, event.char):
            self.close()
            return

        self.update_prompt()

    def update_prompt(self) -> None:
        self.password_text.set(self.exit_password.masked_buffer)
        self.status_text.set(PROMPT_ERROR if self.exit_password.failed else "")

    def run(self) -> None:
        self.root.mainloop()


def create_blackout_overlay(
    stop_event: threading.Event,
    exit_password: str,
) -> BlackoutOverlay | None:
    system = platform.system()
    is_x11 = os.environ.get("XDG_SESSION_TYPE") == "x11"

    if system == "Linux" and is_x11:
        return LinuxX11BlackoutOverlay(
            stop_event,
            exit_password,
        )

    if system == "Windows":
        return TkBlackoutOverlay(
            stop_event,
            exit_password,
        )

    return None
