from PySide6.QtCore import QTimer


def flash_text(label, color="#2ecc71", duration=150):

    original = label.styleSheet()

    label.setStyleSheet(f"color:{color};")

    QTimer.singleShot(
        duration,
        lambda: label.setStyleSheet(original)
    )