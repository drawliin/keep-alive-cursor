from __future__ import annotations

import ctypes
import os
import platform
from typing import Protocol


class MouseController(Protocol):
    def get_pos(self) -> tuple[int, int]:
        ...

    def set_pos(self, x: int, y: int) -> None:
        ...


class LinuxX11MouseController:
    def __init__(self):
        from Xlib import display

        self.display = display.Display()
        self.root = self.display.screen().root

    def get_pos(self) -> tuple[int, int]:
        pointer = self.root.query_pointer()
        return pointer.root_x, pointer.root_y

    def set_pos(self, x: int, y: int) -> None:
        self.root.warp_pointer(x, y)
        self.display.sync()


class WindowsMouseController:
    def __init__(self):
        self.user = ctypes.windll.user32

    def get_pos(self) -> tuple[int, int]:
        class Point(ctypes.Structure):
            _fields_ = [
                ("x", ctypes.c_long),
                ("y", ctypes.c_long),
            ]

        point = Point()
        self.user.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def set_pos(self, x: int, y: int) -> None:
        self.user.SetCursorPos(x, y)


def create_mouse_controller() -> MouseController | None:
    system = platform.system()
    is_x11 = os.environ.get("XDG_SESSION_TYPE") == "x11"

    if system == "Linux" and is_x11:
        return LinuxX11MouseController()

    if system == "Windows":
        return WindowsMouseController()

    return None
