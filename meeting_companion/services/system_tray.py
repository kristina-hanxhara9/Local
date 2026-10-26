from __future__ import annotations

import platform
import threading


def icon_image(active=False):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 62, 62), radius=17, fill="#117D70")
    for x, h in ((17, 10), (25, 22), (33, 32), (41, 18), (49, 8)):
        draw.rounded_rectangle((x - 2, 32 - h // 2, x + 2, 32 + h // 2), radius=2, fill="white")
    if active:
        draw.ellipse((43, 43, 62, 62), fill="#E45F53", outline="white", width=2)
    return image


class SystemTray:
    def __init__(self, dispatch):
        self.dispatch = dispatch
        self.icon = None
        self.thread = None
        self.ready = threading.Event()

    def start(self) -> bool:
        if platform.system() != "Windows":
            return False
        import pystray
        menu = pystray.Menu(
            pystray.MenuItem("Show widget", lambda *_: self.dispatch("show"), default=True),
            pystray.MenuItem("View transcript", lambda *_: self.dispatch("transcript")),
            pystray.MenuItem("Start meeting…", lambda *_: self.dispatch("start")),
            pystray.MenuItem("Pause / Resume", lambda *_: self.dispatch("pause")),
            pystray.MenuItem("Stop", lambda *_: self.dispatch("stop")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit…", lambda *_: self.dispatch("quit")))
        self.icon = pystray.Icon("MeetingCompanion", icon_image(), "Meeting Companion", menu)

        def setup(icon):
            icon.visible = True
            self.ready.set()

        self.thread = threading.Thread(target=lambda: self.icon.run(setup=setup),
                                       name="windows-system-tray", daemon=True)
        self.thread.start()
        return True

    def active(self, active: bool):
        if self.icon and self.ready.is_set():
            self.icon.icon = icon_image(active)
            self.icon.title = "Meeting Companion — capture active" if active else "Meeting Companion"

    def notify(self, text):
        if self.icon and self.ready.is_set():
            self.icon.notify(text, "Meeting Companion")

    def stop(self):
        if self.icon:
            self.icon.stop()
