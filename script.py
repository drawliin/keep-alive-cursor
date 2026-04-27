import ctypes
import os
import platform
import threading
import time


INTERVAL = 5
OFFSET = 1
MOVE_BACK_DELAY = 0.5


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
    def __init__(self, stop_event):
        from Xlib import X, display

        self.X = X
        self.stop_event = stop_event
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
            event_mask=X.KeyPressMask,
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

                    if event.type == self.X.KeyPress:
                        self.stop_event.set()
                        return

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
    def __init__(self, stop_event):
        import tkinter as tk

        self.stop_event = stop_event
        self.root = tk.Tk()
        self.root.configure(background="black", cursor="none")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.bind("<Key>", self.close)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.focus)

    def focus(self):
        if self.stop_event.is_set():
            return

        self.root.lift()
        self.root.focus_force()
        self.root.after(1000, self.focus)

    def close(self, _event=None):
        self.stop_event.set()
        self.root.destroy()

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


def create_blackout_overlay(stop_event):
    system = platform.system()
    is_x11 = os.environ.get("XDG_SESSION_TYPE") == "x11"

    if system == "Linux" and is_x11:
        return LinuxX11BlackoutOverlay(stop_event)

    if system == "Windows":
        return TkBlackoutOverlay(stop_event)

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
    overlay = create_blackout_overlay(stop_event)

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
