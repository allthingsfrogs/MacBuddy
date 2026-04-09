from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap
import sys

app = QApplication([])

class BuddyWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setStyleSheet("background: transparent;")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        #pass in self as parent to place label inside of widget
        self.label = QLabel(self)
        self.label.setStyleSheet("background: transparent;")

        pixmap = QPixmap("assets/froakie/idle.png")





window = BuddyWidget()
window.show()


app.exec()