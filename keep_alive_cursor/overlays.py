from __future__ import annotations

import os
import platform
import threading
import time
from typing import Protocol

from .keys import ExitKeyCombinations, ExitKeyMatcher


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
        exit_key_combinations: ExitKeyCombinations,
    ):
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

    def run(self) -> None:
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

    def get_modifier_names(self, event) -> list[str]:
        return [
            key_name
            for mask, key_name in self.modifier_masks
            if event.state & mask
        ]

    def key_pressed(self, event) -> bool:
        key_name = self.get_key_name(event)

        for modifier_name in self.get_modifier_names(event):
            self.exit_keys.press(modifier_name)

        if key_name is None:
            return False

        return self.exit_keys.press(key_name)

    def key_released(self, event) -> None:
        key_name = self.get_key_name(event)

        if key_name is not None:
            self.exit_keys.release(key_name)

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
        exit_key_combinations: ExitKeyCombinations,
    ):
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
        self.root.after(100, self.watch_stop_event)

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
        if self.exit_keys.press(event.keysym):
            self.close()

    def key_released(self, event) -> None:
        self.exit_keys.release(event.keysym)

    def run(self) -> None:
        self.root.mainloop()


def create_blackout_overlay(
    stop_event: threading.Event,
    exit_key_combinations: ExitKeyCombinations,
) -> BlackoutOverlay | None:
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
