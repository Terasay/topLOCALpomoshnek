import mss
from PIL import Image


def take_screenshot(path: str = "screen.png") -> str:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        img.save(path)

    return path