import os
import platform
import ctypes
import time

from Xlib import display

is_windows = platform.system() == "Windows"
is_linux = platform.system() == "Linux"
is_x11 = os.environ.get("XDG_SESSION_TYPE") == "x11"

INTERVAL = 5
OFFSET = 1

if is_linux and is_x11:
    d = display.Display()
    root = d.screen().root

    def get_cursor_pos():
        pointer = root.query_pointer()
        return pointer.root_x, pointer.root_y

    def move_cursor(x, y):
        root.warp_pointer(x, y)
        d.sync()

    while True:
        x, y = get_cursor_pos()

        move_cursor(x + OFFSET, y)
        time.sleep(0.5)
        move_cursor(x, y)

        time.sleep(INTERVAL)

elif is_windows:
    class MouseKeeper():
        def __init__(self, interval=INTERVAL, offset=OFFSET):
            self.interval = interval
            self.offset = offset
            self.user = ctypes.windll.user32
        
        def getPos(self):
            class Point(ctypes.Structure):
                _fields_ = [
                    ("x", ctypes.c_long),
                    ("y", ctypes.c_long),
                ]
            pt = Point()
            self.user.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        
        def setPos(self, x, y):
            self.user.SetCursorPos(x, y)

        def tick(self):
            x, y = self.getPos()
            self.setPos(x+self.offset, y)
            time.sleep(0.5)
            self.setPos(x, y)

        def run(self):
            while True:
                self.tick()
                time.sleep(self.interval)
    
    mouse = MouseKeeper()
    mouse.run()

else:
    print("Only work on Linux X11 and Windows")