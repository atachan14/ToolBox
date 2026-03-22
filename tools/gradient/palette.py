from __future__ import annotations

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QBoxLayout, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget

from core.flow_layout import FlowLayout
from .color_utils import color_text_from_qcolor, display_color_text, parse_color_text, qcolor_from_text
from .widgets import PaletteButton, SwatchDialog


class FlowLayoutWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._flow_layout: FlowLayout | None = None

    def set_flow_layout(self, flow_layout: FlowLayout):
        self._flow_layout = flow_layout

    def hasHeightForWidth(self) -> bool:
        return self._flow_layout.hasHeightForWidth() if self._flow_layout is not None else False

    def heightForWidth(self, width: int) -> int:
        if self._flow_layout is None:
            return super().heightForWidth(width)
        margins = self.contentsMargins()
        inner_width = max(0, width - margins.left() - margins.right())
        return self._flow_layout.heightForWidth(inner_width) + margins.top() + margins.bottom()

    def sizeHint(self):
        if self._flow_layout is None:
            return super().sizeHint()
        return self._flow_layout.sizeHint()

    def minimumSizeHint(self):
        if self._flow_layout is None:
            return super().minimumSizeHint()
        return self._flow_layout.minimumSize()


class GradientPalette(QFrame):
    colorSelected = Signal(str)
    colorsChanged = Signal(list)
    saveRequested = Signal()
    loadRequested = Signal()
    resetRequested = Signal()

    def __init__(self, colors: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.palette_colors = list(colors)
        self.buttons: list[PaletteButton] = []
        self.selected_index = 0 if self.palette_colors else -1
        self._syncing_inputs = False
        self._build_ui()
        self._rebuild_swatch_buttons()
        if self.palette_colors:
            self.select_index(0)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.header_host = QWidget()
        self.header_host.setMinimumWidth(0)
        self.header_box = QBoxLayout(QBoxLayout.LeftToRight, self.header_host)
        self.header_box.setContentsMargins(0, 0, 0, 0)
        self.header_box.setSpacing(4)
        self.color_row = QWidget()
        color_row_layout = QHBoxLayout(self.color_row)
        color_row_layout.setContentsMargins(0, 0, 0, 0)
        color_row_layout.setSpacing(4)
        color_row_layout.addWidget(QLabel("Color"))
        self.color_edit = QLineEdit()
        self.color_edit.setMinimumWidth(54)
        self.color_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        color_row_layout.addWidget(self.color_edit, 1)
        self.alpha_row = QWidget()
        alpha_row_layout = QHBoxLayout(self.alpha_row)
        alpha_row_layout.setContentsMargins(0, 0, 0, 0)
        alpha_row_layout.setSpacing(4)
        alpha_row_layout.addWidget(QLabel("Alpha"))
        self.alpha_edit = QLineEdit()
        self.alpha_edit.setMinimumWidth(44)
        self.alpha_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        alpha_row_layout.addWidget(self.alpha_edit)
        self.header_box.addWidget(self.color_row, 1)
        self.header_box.addWidget(self.alpha_row, 1)
        layout.addWidget(self.header_host)

        self.swatch_wrap = FlowLayoutWidget()
        self.swatch_wrap.setMinimumWidth(0)
        self.swatch_wrap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.swatch_wrap.setAcceptDrops(True)
        self.swatch_wrap.dragEnterEvent = self._swatch_drag_enter_event
        self.swatch_wrap.dragMoveEvent = self._swatch_drag_move_event
        self.swatch_wrap.dropEvent = self._swatch_drop_event
        self.swatch_layout = FlowLayout(self.swatch_wrap, margin=0, spacing=4)
        self.swatch_wrap.set_flow_layout(self.swatch_layout)
        layout.addWidget(self.swatch_wrap)

        self.footer_host = QWidget()
        self.footer_host.setMinimumWidth(0)
        self.footer_grid = QGridLayout(self.footer_host)
        self.footer_grid.setContentsMargins(0, 0, 0, 0)
        self.footer_grid.setHorizontalSpacing(4)
        self.footer_grid.setVerticalSpacing(4)
        self.reset_palette_button = QPushButton("Reset")
        self.save_palette_button = QPushButton("Save")
        self.load_palette_button = QPushButton("Load")
        for button in (self.reset_palette_button, self.save_palette_button, self.load_palette_button):
            button.setMinimumWidth(52)
        layout.addWidget(self.footer_host)

        self.color_edit.editingFinished.connect(self._on_inputs_edited)
        self.alpha_edit.editingFinished.connect(self._on_inputs_edited)
        self.reset_palette_button.clicked.connect(self.resetRequested.emit)
        self.save_palette_button.clicked.connect(self.saveRequested.emit)
        self.load_palette_button.clicked.connect(self.loadRequested.emit)
        self._update_footer_layout()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        layout = self.layout()
        if layout is None:
            return super().heightForWidth(width)
        margins = layout.contentsMargins()
        spacing = layout.spacing()
        inner_width = max(0, width - margins.left() - margins.right())
        header_height = self.header_host.sizeHint().height()
        swatch_height = self.swatch_wrap.heightForWidth(inner_width)
        button_height = max(
            self.reset_palette_button.sizeHint().height(),
            self.save_palette_button.sizeHint().height(),
            self.load_palette_button.sizeHint().height(),
        )
        footer_spacing = self.footer_grid.verticalSpacing()
        footer_mode = self._footer_mode_for_width(inner_width)
        if footer_mode in (1, 2):
            footer_height = button_height
        elif footer_mode == 3:
            footer_height = button_height * 2 + footer_spacing
        else:
            footer_height = button_height * 3 + footer_spacing * 2
        total = margins.top() + margins.bottom() + header_height + swatch_height + footer_height
        if layout.count() > 1:
            total += spacing
        if layout.count() > 2:
            total += spacing
        return total

    def sizeHint(self):
        hint = super().sizeHint()
        compact_width = 180
        return QSize(min(compact_width, max(120, hint.width())), hint.height())

    def minimumSizeHint(self):
        layout = self.layout()
        if layout is None:
            return super().minimumSizeHint()
        base = super().minimumSizeHint()
        return base.expandedTo(QSize(120, base.height()))

    def _sync_swatch_wrap_height(self):
        width = max(0, self.swatch_wrap.width())
        if width <= 0:
            width = max(0, self.width() - self.layout().contentsMargins().left() - self.layout().contentsMargins().right())
        target_height = max(24, self.swatch_wrap.heightForWidth(width))
        self.swatch_wrap.setFixedHeight(target_height)
        self.swatch_wrap.updateGeometry()
        self.updateGeometry()

    def _update_header_layout(self):
        inner_width = max(0, self.width() - self.layout().contentsMargins().left() - self.layout().contentsMargins().right())
        threshold = self.color_row.minimumSizeHint().width() + self.alpha_row.minimumSizeHint().width() + self.header_box.spacing()
        self.header_box.setDirection(QBoxLayout.LeftToRight if inner_width >= threshold else QBoxLayout.TopToBottom)
        self.header_host.updateGeometry()

    def _footer_mode_for_width(self, inner_width: int) -> int:
        def _effective_width(button: QPushButton) -> int:
            return button.minimumWidth() if button.minimumWidth() > 0 else button.minimumSizeHint().width()

        spacing = self.footer_grid.horizontalSpacing()
        reset_width = _effective_width(self.reset_palette_button)
        save_width = _effective_width(self.save_palette_button)
        load_width = _effective_width(self.load_palette_button)
        inline_width = reset_width + save_width + load_width + (spacing * 2)
        spaced_inline_width = inline_width + 24
        save_load_width = save_width + load_width + spacing
        if inner_width >= spaced_inline_width:
            return 1
        if inner_width >= inline_width:
            return 2
        if inner_width >= save_load_width:
            return 3
        return 4

    def _clear_footer_layout(self):
        while self.footer_grid.count():
            item = self.footer_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.footer_host)

    def _update_footer_layout(self):
        inner_width = max(0, self.width() - self.layout().contentsMargins().left() - self.layout().contentsMargins().right())
        mode = self._footer_mode_for_width(inner_width)
        self._clear_footer_layout()
        if mode == 1:
            self.footer_grid.addWidget(self.reset_palette_button, 0, 0)
            self.footer_grid.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum), 0, 1)
            self.footer_grid.addWidget(self.save_palette_button, 0, 2)
            self.footer_grid.addWidget(self.load_palette_button, 0, 3)
        elif mode == 2:
            self.footer_grid.addWidget(self.reset_palette_button, 0, 0)
            self.footer_grid.addWidget(self.save_palette_button, 0, 1)
            self.footer_grid.addWidget(self.load_palette_button, 0, 2)
        elif mode == 3:
            self.footer_grid.addWidget(self.reset_palette_button, 0, 0, 1, 2)
            self.footer_grid.addWidget(self.save_palette_button, 1, 0)
            self.footer_grid.addWidget(self.load_palette_button, 1, 1)
        else:
            self.footer_grid.addWidget(self.reset_palette_button, 0, 0)
            self.footer_grid.addWidget(self.save_palette_button, 1, 0)
            self.footer_grid.addWidget(self.load_palette_button, 2, 0)
        self.footer_host.updateGeometry()

    def _clear_swatch_buttons(self):
        while self.swatch_layout.count():
            item = self.swatch_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.buttons.clear()

    def _rebuild_swatch_buttons(self):
        self._clear_swatch_buttons()
        for color in self.palette_colors:
            button = PaletteButton(color)
            button.setProperty("palette_index", len(self.buttons))
            button.clicked.connect(lambda _checked=False, btn=button: self.select_index(self.buttons.index(btn)))
            button.customContextMenuRequested.connect(lambda pos, btn=button: self._show_swatch_menu(btn, pos))
            self.buttons.append(button)
            self.swatch_layout.addWidget(button)
        add_button = QPushButton("+")
        add_button.setFixedSize(24, 24)
        add_button.clicked.connect(self._append_swatch_from_dialog)
        self.swatch_layout.addWidget(add_button)
        self.swatch_layout.invalidate()
        self._sync_swatch_wrap_height()

    def _selected_color(self) -> str:
        if 0 <= self.selected_index < len(self.palette_colors):
            return self.palette_colors[self.selected_index]
        return "#00000000"

    def select_color(self, color: str):
        if color in self.palette_colors:
            self.select_index(self.palette_colors.index(color))

    def select_index(self, index: int):
        if not (0 <= index < len(self.palette_colors)):
            return
        self.selected_index = index
        selected_color = self.palette_colors[index]
        for button_index, button in enumerate(self.buttons):
            button.set_selected(button_index == index)
        self._sync_inputs_from_color(selected_color)
        self.colorSelected.emit(selected_color)

    def set_palette_colors(self, colors: list[str]):
        self.palette_colors = list(colors)
        previous_index = self.selected_index
        self._rebuild_swatch_buttons()
        if not self.palette_colors:
            self.selected_index = -1
            self._sync_inputs_from_color("#00000000")
            return
        self.select_index(max(0, min(previous_index, len(self.palette_colors) - 1)))

    def _sync_inputs_from_color(self, color_text: str):
        color = qcolor_from_text(color_text)
        self._syncing_inputs = True
        self.color_edit.setText(display_color_text(color_text))
        self.alpha_edit.setText(f"{round(color.alphaF() * 100):d}%")
        self._syncing_inputs = False

    def _on_inputs_edited(self):
        if self._syncing_inputs or not (0 <= self.selected_index < len(self.palette_colors)):
            return
        rgb_text = self.color_edit.text().strip()
        alpha_text = self.alpha_edit.text().strip().lower()
        parsed_rgb = parse_color_text(rgb_text)
        if parsed_rgb is None:
            self._sync_inputs_from_color(self._selected_color())
            return
        color = qcolor_from_text(parsed_rgb)
        try:
            alpha_value = alpha_text[:-1] if alpha_text.endswith("%") else alpha_text
            alpha = max(0.0, min(1.0, float(alpha_value) / 100.0))
        except ValueError:
            self._sync_inputs_from_color(self._selected_color())
            return
        color.setAlphaF(alpha)
        new_color = color_text_from_qcolor(color)
        self.palette_colors[self.selected_index] = new_color
        self.buttons[self.selected_index].color_value = new_color
        self.buttons[self.selected_index]._apply_style(True)
        self._sync_inputs_from_color(new_color)
        self.colorSelected.emit(new_color)
        self.colorsChanged.emit(list(self.palette_colors))

    def _append_swatch_from_dialog(self):
        dialog = SwatchDialog("#00000000", self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.palette_colors.append(dialog.selected_color)
        self._rebuild_swatch_buttons()
        self.select_index(len(self.palette_colors) - 1)
        self.colorsChanged.emit(list(self.palette_colors))

    def _open_swatch_dialog(self, button: PaletteButton):
        dialog = SwatchDialog(button.color_value, self)
        if dialog.exec() != QDialog.Accepted:
            return
        new_color = dialog.selected_color
        index = self.buttons.index(button)
        self.palette_colors[index] = new_color
        self.buttons[index].color_value = new_color
        self.buttons[index]._apply_style(index == self.selected_index)
        if self.selected_index == index:
            self._sync_inputs_from_color(new_color)
            self.colorSelected.emit(new_color)
        self.colorsChanged.emit(list(self.palette_colors))

    def _show_swatch_menu(self, button: PaletteButton, pos):
        if button not in self.buttons:
            return
        menu = QMenu(button)
        pick_action = menu.addAction("カラーピック")
        delete_action = menu.addAction("削除")
        if len(self.palette_colors) <= 1:
            delete_action.setEnabled(False)
        action = menu.exec(button.mapToGlobal(pos))
        if action == pick_action:
            self._open_swatch_dialog(button)
            return
        if action == delete_action and delete_action.isEnabled():
            self._delete_swatch(button)

    def _delete_swatch(self, button: PaletteButton):
        if button not in self.buttons:
            return
        index = self.buttons.index(button)
        if not (0 <= index < len(self.palette_colors)):
            return
        self.palette_colors.pop(index)
        self._rebuild_swatch_buttons()
        if not self.palette_colors:
            self.selected_index = -1
            self._sync_inputs_from_color("#00000000")
        else:
            self.select_index(max(0, min(self.selected_index, len(self.palette_colors) - 1)))
        self.colorsChanged.emit(list(self.palette_colors))

    def _swatch_drag_enter_event(self, event):
        if event.mimeData().hasFormat("application/x-gradient-palette-index"):
            event.acceptProposedAction()
            return
        event.ignore()

    def _swatch_drag_move_event(self, event):
        if event.mimeData().hasFormat("application/x-gradient-palette-index"):
            event.acceptProposedAction()
            return
        event.ignore()

    def _swatch_drop_event(self, event):
        if not event.mimeData().hasFormat("application/x-gradient-palette-index"):
            event.ignore()
            return
        try:
            source_index = int(bytes(event.mimeData().data("application/x-gradient-palette-index")).decode("utf-8"))
        except ValueError:
            event.ignore()
            return
        target_index = self._drop_target_index(event.position().toPoint())
        if target_index is None:
            event.ignore()
            return
        self._move_swatch(source_index, target_index)
        event.acceptProposedAction()

    def _drop_target_index(self, pos) -> int | None:
        child = self.swatch_wrap.childAt(pos)
        if isinstance(child, PaletteButton) and child in self.buttons:
            target_index = self.buttons.index(child)
            center = child.geometry().center()
            if pos.x() > center.x() or pos.y() > center.y():
                target_index += 1
            return target_index
        return len(self.buttons)

    def _move_swatch(self, source_index: int, target_index: int):
        if not (0 <= source_index < len(self.palette_colors)):
            return
        target_index = max(0, min(target_index, len(self.palette_colors)))
        if source_index < target_index:
            target_index -= 1
        if source_index == target_index:
            return
        color = self.palette_colors.pop(source_index)
        self.palette_colors.insert(target_index, color)
        if self.selected_index == source_index:
            self.selected_index = target_index
        elif source_index < self.selected_index <= target_index:
            self.selected_index -= 1
        elif target_index <= self.selected_index < source_index:
            self.selected_index += 1
        self._rebuild_swatch_buttons()
        if self.palette_colors:
            self.select_index(max(0, min(self.selected_index, len(self.palette_colors) - 1)))
        self.colorsChanged.emit(list(self.palette_colors))

    def resizeEvent(self, event):
        self._update_header_layout()
        self._update_footer_layout()
        self.swatch_layout.invalidate()
        self._sync_swatch_wrap_height()
        self.layout().invalidate()
        super().resizeEvent(event)
