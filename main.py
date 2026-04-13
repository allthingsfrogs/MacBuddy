from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QCheckBox, QPushButton
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QPixmap, QCursor, QFontDatabase
import sys
import os
import signal
import random
from AppKit import NSApplication, NSApp, NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary, NSApplicationActivationPolicyAccessory
from sprite import load_frames_from_folder, Animator


class BuddyWidget(QWidget):
    # Shared list of all buddy instances — used for overlap avoidance
    all_buddies = []

    def __init__(self, sprite_folder):
        super().__init__()
        BuddyWidget.all_buddies.append(self)

        self.setStyleSheet("background: transparent;")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            #Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        # pass in self as parent to place label inside of widget
        self.label = QLabel(self)
        self.label.setStyleSheet("background: transparent;")

        # load all animation states from the given sprite folder
        self.animations = {
            "idleOneLeft": load_frames_from_folder(f"{sprite_folder}/idleOneLeft"),
            "idleOneRight": load_frames_from_folder(f"{sprite_folder}/idleOneRight"),
            "idleTwoLeft": load_frames_from_folder(f"{sprite_folder}/idleTwoLeft"),
            "idleTwoRight": load_frames_from_folder(f"{sprite_folder}/idleTwoRight"),
            "idleBlinkLeft": load_frames_from_folder(f"{sprite_folder}/idleBlinkLeft") * 2,
            "idleBlinkRight": load_frames_from_folder(f"{sprite_folder}/idleBlinkRight") * 2,
            "walkLeft": load_frames_from_folder(f"{sprite_folder}/walkLeft") * 2,
            "walkRight": load_frames_from_folder(f"{sprite_folder}/walkRight") * 2,
        }

        # track which direction the sprite is facing
        self.facing = "Right"

        # store first frame for mousePressEvent alpha checks
        self.pixmap = self.animations["idleOneRight"][0]

        # size the label and window to the first frame
        self.label.resize(self.pixmap.size())
        self.resize(self.pixmap.size())

        # position sprite at bottom of screen, spaced apart from other buddies
        screen = QApplication.primaryScreen().geometry()
        sprite_w = self.pixmap.width()
        num_buddies = len(BuddyWidget.all_buddies)
        # Divide screen into equal sections, place this buddy in its section
        section_width = screen.width() // max(num_buddies, 1)
        x = (num_buddies - 1) * section_width + (section_width - sprite_w) // 2
        y = screen.height() - self.pixmap.height() - 50
        self.move(x, y)

        # create a single animator — we swap its frames when changing state
        self.animator = Animator(
            self.animations["idleOneRight"],
            interval_ms=200,
            on_frame=self.label.setPixmap,
            loop=True,
            on_finish=self._on_animation_done
        )
        self.animator.start()
        self.current_state = "idleOneRight"

        # Store the screen bounds and Y position for movement
        self.screen = QApplication.primaryScreen().geometry()
        self.target_x = None         # where the sprite is walking toward
        self.sprite_y = self.y()     # fixed Y position (stays the same)

        # Movement timer — fires every 30ms to step the sprite toward target_x
        self.move_timer = QTimer()
        self.move_timer.setInterval(30)
        self.move_timer.timeout.connect(self._move_step)

        # Store reference to NSWindow for toggling click-through
        self.ns_window = None

        # Poll mouse position every 50ms to toggle click-through
        self.mouse_timer = QTimer()
        self.mouse_timer.setInterval(50)
        self.mouse_timer.timeout.connect(self._check_mouse)
        self.mouse_timer.start()

        # schedule the first random state switch
        self._schedule_idle_switch()

    def _schedule_idle_switch(self):
        # After a random delay, switch from idleOne to idleTwo or vice versa
        delay_ms = random.randint(2000, 7000)
        QTimer.singleShot(delay_ms, self._switch_idle)

    def _switch_idle(self):
        # Randomly pick an action: idle variant, blink, or walk
        self.animator.stop()
        next_base = random.choice(["idleTwo", "idleBlink", "idleBlink", "idleOne", "walk", "walk"])
        print(next_base)

        # If walk was chosen, pick a bounded target that won't overlap other buddies
        if next_base == "walk":
            min_x = 0
            max_x = self.screen.width() - self.pixmap.width()
            # Try up to 10 times to find a non-overlapping target
            for _ in range(10):
                candidate = random.randint(min_x, max_x)
                if not self._would_overlap(candidate):
                    break
            self.target_x = candidate
            print("max x: ", max_x)
            self._start_walking()
            return

        # Append the current facing direction to get the correct animation key
        next_anim = next_base + self.facing
        self.current_state = next_anim
        self.animator = Animator(
            self.animations[next_anim],
            interval_ms=90 if next_base == "idleBlink" else 135,
            on_frame=self.label.setPixmap,
            loop=False,
            on_finish=self._on_animation_done
        )
        self.animator.start()

    def _on_animation_done(self):
        # When a one-shot animation finishes, return to idleOne facing the current direction
        idle_anim = "idleOne" + self.facing
        self.animator = Animator(
            self.animations[idle_anim],
            interval_ms=180,
            on_frame=self.label.setPixmap,
            loop=True,
            on_finish=self._on_animation_done
        )
        self.animator.start()
        self.current_state = idle_anim
        self._schedule_idle_switch()

    def _start_walking(self):
        # Choose walk direction based on which way we need to go
        if self.target_x < self.x():
            walk_anim = "walkLeft"
            self.facing = "Left"
        else:
            walk_anim = "walkRight"
            self.facing = "Right"

        # Randomly pick how many walk cycles to play (1 to 4)
        self.walk_cycles_remaining = random.randint(1, 3)

        # Calculate how far to walk per cycle: total distance / number of cycles
        total_distance = abs(self.target_x - self.x())
        self.pixels_per_cycle = max(1, total_distance // self.walk_cycles_remaining)

        # Track how many pixels moved in the current cycle
        self.pixels_moved_this_cycle = 0
        self.walk_direction = -4 if walk_anim == "walkLeft" else 4

        # Swap to the walk animation — one-shot so we can count cycles
        self.current_state = walk_anim
        self.animator = Animator(
            self.animations[walk_anim],
            interval_ms=100,
            on_frame=self.label.setPixmap,
            loop=False,
            on_finish=self._on_walk_cycle_done
        )
        self.animator.start()

        # Start the movement timer
        self.move_timer.start()

    def _on_walk_cycle_done(self):
        # One animation cycle finished — check if we should keep walking
        self.walk_cycles_remaining -= 1
        if self.walk_cycles_remaining > 0 and abs(self.x() - self.target_x) > 5:
            # More cycles to go — restart the walk animation for another cycle
            self.pixels_moved_this_cycle = 0
            self.animator.start()
        else:
            # Done walking — stop movement and return to idle
            self.move_timer.stop()
            self._on_animation_done()

    def _move_step(self):
        current_x = self.x()

        # Bounds check — keep sprite within screen
        min_x = 0
        max_x = self.screen.width() - self.pixmap.width()

        # Check if we've arrived at the target or hit a screen edge
        if abs(current_x - self.target_x) <= 5 or current_x <= min_x or current_x >= max_x:
            self.move_timer.stop()
            self.animator.stop()
            self._on_animation_done()
            return

        # Stop if the next step would directly overlap another buddy (tight check)
        next_x = current_x + self.walk_direction
        if self._would_overlap(next_x, buffer=2):
            self.move_timer.stop()
            self.animator.stop()
            self._on_animation_done()
            return

        # Move toward target
        new_x = current_x + self.walk_direction
        # Clamp to screen bounds
        new_x = max(min_x, min(new_x, max_x))
        self.move(new_x, self.sprite_y)

    def _would_overlap(self, x, buffer=10):
        # Check if placing this sprite at x would overlap with any other buddy
        # Buffer adds padding so sprites don't stop right on top of each other
        my_width = self.pixmap.width()
        for buddy in BuddyWidget.all_buddies:
            if buddy is self:
                continue
            other_x = buddy.x()
            other_width = buddy.pixmap.width()
            if x < other_x + other_width + buffer and x + my_width + buffer > other_x:
                return True
        return False

    def set_ns_window(self, ns_window):
        # Called after .show() to give us access to the native window
        self.ns_window = ns_window

    def _check_mouse(self):
        if not self.ns_window:
            return

        # Get global cursor position and convert to widget-local coordinates
        cursor_global = QCursor.pos()
        cursor_local = self.mapFromGlobal(cursor_global)
        x, y = cursor_local.x(), cursor_local.y()

        # Check if cursor is within the widget bounds
        if 0 <= x < self.width() and 0 <= y < self.height():
            # Check if the pixel under the cursor is non-transparent
            image = self.pixmap.toImage()
            color = image.pixelColor(x, y)
            if color.alpha() > 0:
                # Cursor is on the sprite — allow clicks
                self.ns_window.setIgnoresMouseEvents_(False)
                return

        # Cursor is outside the sprite or on a transparent pixel — click-through
        self.ns_window.setIgnoresMouseEvents_(True)

    # Qt calls this automatically on every click on your widget.
    # Steps to implement click-through:
    #   1. Get click position: pos = a0.position()  gives you x, y
    #   2. Convert the pixmap to an image: image = self.pixmap.toImage()
    #   3. Get the pixel color at the click: color = image.pixelColor(int(pos.x()), int(pos.y()))
    #   4. Check alpha: if color.alpha() == 0 -> transparent, call a0.ignore() to pass click through
    #                   if color.alpha() > 0  -> on the sprite, handle the click here
    def mousePressEvent(self, a0):

        pos = a0.position()
        image = self.pixmap.toImage()
        color = image.pixelColor(int(pos.x()), int(pos.y()))
        if color.alpha() == 0:
            a0.ignore()
        if color.alpha() > 0:
            print("Clicked on sprite")
            return super().mousePressEvent(a0)
       
        return super().mousePressEvent(a0)
    
class BuddyPicker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MacBuddy - Choose Your Buddies")
        self.resize(300, 350)

        # Load pixel font using absolute path
        font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "PressStart2P.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        print("Font loaded:", QFontDatabase.applicationFontFamilies(font_id))

        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a3e;
                color: #ffffff;
                font-family: 'Press Start 2P';
                font-size: 10px;
            }
            QCheckBox {
                spacing: 10px;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QPushButton {
                background-color: #4a3f8a;
                color: #ffffff;
                border: 2px solid #7a6fca;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Press Start 2P';
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #5a4f9a;
            }
        """)

        layout = QVBoxLayout(self)

        # Scan the assets folder for available pokemon
        self.checkboxes = []
        assets_path = "assets"
        available = sorted(
            d for d in os.listdir(assets_path)
            if os.path.isdir(os.path.join(assets_path, d))
        )

        label = QLabel(f"Choose up to 3 buddies ({len(available)} available):")
        layout.addWidget(label)

        for name in available:
            cb = QCheckBox(name.capitalize())
            cb.setProperty("folder", f"{assets_path}/{name}")
            cb.stateChanged.connect(self._enforce_limit)
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        self.spawn_button = QPushButton("Spawn!")
        self.spawn_button.clicked.connect(self._spawn)
        layout.addWidget(self.spawn_button)

        self.buddies = []

    def _enforce_limit(self):
        # Count how many are checked, disable unchecked ones if at 3
        checked = [cb for cb in self.checkboxes if cb.isChecked()]
        at_limit = len(checked) >= 3
        for cb in self.checkboxes:
            if not cb.isChecked():
                cb.setEnabled(not at_limit)

    def _spawn(self):
        # Clean up any existing buddies
        for buddy in self.buddies:
            buddy.close()
        self.buddies.clear()
        BuddyWidget.all_buddies.clear()

        # Create buddies from checked boxes
        selected = [cb.property("folder") for cb in self.checkboxes if cb.isChecked()]
        if not selected:
            return

        for folder in selected:
            buddy = BuddyWidget(folder)
            self.buddies.append(buddy)

        for buddy in self.buddies:
            buddy.show()

        # Apply NSWindow settings to the buddy windows (skip the picker window)
        ns_app = NSApplication.sharedApplication()
        # The picker window is the first one, buddy windows come after
        buddy_windows = ns_app.windows()[-len(self.buddies):]
        for ns_window in buddy_windows:
            ns_window.setLevel_(1000)
            ns_window.setHidesOnDeactivate_(False)
            ns_window.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
            )
            ns_window.setIgnoresMouseEvents_(True)

        for i, buddy in enumerate(self.buddies):
            buddy.set_ns_window(buddy_windows[i])

        # Hide the picker and remove app from Dock after spawning
        self.hide()
        ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)


app = QApplication([])

# Allow Ctrl+C to quit the app
signal.signal(signal.SIGINT, signal.SIG_DFL)

picker = BuddyPicker()
picker.show()

app.exec()