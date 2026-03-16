from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


def apply_dark_theme(app):

    app.setStyle("Fusion")  # Fusionのほうが崩れにくい

    palette = QPalette()

    # ベース
    palette.setColor(QPalette.Window, QColor(37, 37, 38))
    palette.setColor(QPalette.WindowText, Qt.white)

    # 入力欄
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))

    # 文字
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)

    # ボタン
    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, Qt.white)

    # メニュー
    palette.setColor(QPalette.BrightText, Qt.red)

    # 選択
    palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.HighlightedText, Qt.white)

    # ツールチップ
    palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))

    # 無効状態
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))

    app.setPalette(palette)