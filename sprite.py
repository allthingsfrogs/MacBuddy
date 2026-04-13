import os
import re
from PIL import Image
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer


def load_frames_from_folder(folder_path):
    """
    Loads all PNG files from a folder as animation frames, sorted by filename.

    Since your sprites are individual PNGs named with numbers (e.g. froakie_left1.png,
    froakie_left2.png), sorting alphabetically gives us the correct frame order.

    Args:
        folder_path: path to a folder containing numbered PNG frames
                     e.g. "assets/froakie/walkLeft"

    Returns:
        A list of QPixmap objects in filename-sorted order, ready for the Animator.
    """
    # Get all PNG files and sort numerically by all numbers in the filename
    # e.g. "idle_two-4-10.png" sorts by (4, 10), so it comes after "idle_two-4-9.png" (4, 9)
    def numeric_key(filename):
        numbers = re.findall(r'\d+', filename)
        return tuple(int(n) for n in numbers) if numbers else (0,)

    filenames = sorted(
        (f for f in os.listdir(folder_path) if f.endswith(".png")),
        key=numeric_key
    )

    frames = []
    for filename in filenames:
        full_path = os.path.join(folder_path, filename)
        image = Image.open(full_path)

        # Convert each Pillow image to a QPixmap so Qt can display it
        pixmap = pillow_to_pixmap(image)
        frames.append(pixmap)

    return frames

# Later when you implement the state machine, switching animations is just:
# self.animator.set_frames(load_frames_from_folder("assets/froakie/walkLeft"))

def pillow_to_pixmap(pil_image):
    """
    Converts a Pillow Image to a QPixmap.

    Qt cannot render Pillow images directly. The conversion path is:
        Pillow Image
            -> convert to RGBA (ensures 4 channels: red, green, blue, alpha)
            -> get raw bytes with .tobytes()
            -> build a QImage from those bytes
            -> convert QImage to QPixmap

    The QImage constructor needs to know:
        - the raw byte data
        - image width and height
        - bytes per line (width * 4 because RGBA = 4 bytes per pixel)
        - the pixel format (Format_RGBA8888 matches RGBA byte order from Pillow)
    """
    pil_image = pil_image.convert("RGBA")

    width, height = pil_image.size
    raw_bytes = pil_image.tobytes()

    bytes_per_line = width * 4  # 4 bytes per pixel (R, G, B, A)

    qimage = QImage(raw_bytes, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)

    # .copy() forces Qt to make its own copy of the pixel data.
    # Without this, QImage just holds a pointer to raw_bytes, which Python
    # can garbage collect — causing corrupted or wrong frames to appear.
    return QPixmap.fromImage(qimage.copy())


class Animator:
    """
    Manages frame cycling for a single animation.

    Holds a list of QPixmap frames and a QTimer that advances through them
    at a set interval. On each timer tick it calls a callback with the next frame,
    so the widget can update its QLabel.

    Supports two modes:
        loop=True  (default) — cycles forever, wrapping back to frame 0 after the last
        loop=False           — plays through once, then stops and calls on_finish if provided

    Usage:
        # Looping animation (e.g. walk cycle)
        animator = Animator(frames, interval_ms=150, on_frame=self.label.setPixmap)
        animator.start()

        # One-shot animation (e.g. blink), calls on_finish when done
        animator = Animator(frames, interval_ms=80, on_frame=self.label.setPixmap,
                            loop=False, on_finish=self.on_blink_done)
        animator.start()
    """

    def __init__(self, frames, interval_ms, on_frame, loop=True, on_finish=None):
        """
        Args:
            frames:      list of QPixmap objects to cycle through
            interval_ms: milliseconds between each frame (150ms = ~6fps, good for walk cycles)
            on_frame:    callable that receives the current QPixmap each tick
                         typically self.label.setPixmap
            loop:        if True, animation repeats forever
                         if False, plays once and stops
            on_finish:   optional callable invoked when a non-looping animation completes
        """
        self.frames = frames
        self.on_frame = on_frame
        self.loop = loop
        self.on_finish = on_finish
        self.current_frame = 0  # index into self.frames

        # QTimer fires repeatedly at the given interval.
        # Each tick calls self._tick to advance the animation.
        self.timer = QTimer()
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._tick)

    def start(self):
        """Begin cycling through frames."""
        self.current_frame = 0  # always start from the beginning
        self._tick()            # show the first frame immediately, don't wait for first tick
        self.timer.start()

    def stop(self):
        """Pause the animation on the current frame."""
        self.timer.stop()

    def resume(self):
        """Resume the animation from where it was paused, without resetting the frame counter."""
        self.timer.start()

    def set_frames(self, frames, interval_ms=None):
        """
        Swap to a new set of frames (e.g. switching from idle to walk).
        Resets the frame counter so the new animation starts from the beginning.
        Optionally update the interval (walk vs yawn may have different speeds).
        """
        self.frames = frames
        self.current_frame = 0
        if interval_ms is not None:
            self.timer.setInterval(interval_ms)

    def _tick(self):
        """
        Called by the QTimer on each interval.
        Sends the current frame to the widget, then advances the counter.

        In loop mode: wraps back to 0 after the last frame.
        In one-shot mode: stops the timer after the last frame and calls on_finish.
        """
        self.on_frame(self.frames[self.current_frame])
        self.current_frame += 1

        if self.current_frame >= len(self.frames):
            if self.loop:
                # Wrap back to the start for continuous animations
                self.current_frame = 0
            else:
                # One-shot complete — stop and notify the caller
                self.timer.stop()
                if self.on_finish:
                    self.on_finish()