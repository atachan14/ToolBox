from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor,QPainter, QPen, QColor,QFont
from .highlighter import MarkdownHighlighter
import re

class MarkdownEditor(QPlainTextEdit):

    INDENT = "\t"

    def __init__(self):
        super().__init__()

        font = QFont("JetBrains Mono")
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        MarkdownHighlighter(self.document())

        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * 4
        )
        
        self.indent_colors = [
            QColor("#ff6b6b"),  # 赤
            QColor("#ffd43b"),  # 黄
            QColor("#40c057"),  # 緑
            QColor("#845ef7"),  # 紫
        ]
        
    def wheelEvent(self, event):

        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()

            parent = self.parent()

            if hasattr(parent, "change_font"):
                parent.change_font(1 if delta > 0 else -1)

        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.text() == "`":

            cursor = self.textCursor()

            # 直前2文字取得
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 2)
            prev = cursor.selectedText()
            cursor.clearSelection()

            if prev == "``":
                # ``` を作る
                cursor.insertText("`\n\n```")

                # カーソルを中へ
                cursor.movePosition(QTextCursor.Up)
                self.setTextCursor(cursor)

                return
        text = event.text()

        if (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.ShiftModifier):

            if event.key() == Qt.Key_T:
                self.tree_diagram()

            if event.key() == Qt.Key_D:
                self.wrap_selection("***")
                return
            if event.key() == Qt.Key_C:
                self.insert_code_block()
                return

            if event.key() == Qt.Key_B:
                self.wrap_selection("**")
                return

            if event.key() == Qt.Key_I:
                self.wrap_selection("*")
                return

            if event.key() == Qt.Key_K:
                self.wrap_selection("[", "]()", 1)
                return
            
            if event.key() == Qt.Key_L:
                self.toggle_line_prefix("- ")
                return

            if event.key() == Qt.Key_Q:
                self.toggle_line_prefix("> ")
                return
            
            if event.key() == Qt.Key_H:
                self.toggle_heading()
                return

            if event.key() == Qt.Key_Slash:
                self.toggle_comment()
                return
            
            


        if (event.modifiers() & Qt.ControlModifier) and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.continue_prefix()
            return
        
        if event.key() == Qt.Key_Tab:
            cursor = self.textCursor()

            if cursor.hasSelection():
                self.indent_selection()
            else:
                super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Backtab:
            if self.textCursor().hasSelection():
                self.unindent_selection()
            return

        # Enter → インデント継続
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):

            cursor = self.textCursor()
            block = cursor.block().text()

            indent = ""
            for ch in block:
                if ch in (" ", "\t"):
                    indent += ch
                else:
                    break

            super().keyPressEvent(event)

            if indent:
                self.insertPlainText(indent)

            return

        super().keyPressEvent(event)
        
    def indent_selection(self):

        cursor = self.textCursor()

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        doc = self.document()

        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)

        cursor.beginEditBlock()

        block = start_block

        while True:

            cursor.setPosition(block.position())
            cursor.insertText(self.INDENT)

            if block == end_block:
                break

            block = block.next()

        cursor.endEditBlock()
        
    def unindent_selection(self):

        cursor = self.textCursor()

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        doc = self.document()

        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)

        cursor.beginEditBlock()

        block = start_block

        while True:

            text = block.text()

            if text.startswith(self.INDENT):

                cursor.setPosition(block.position())
                cursor.movePosition(QTextCursor.Right,
                                    QTextCursor.KeepAnchor,
                                    len(self.INDENT))
                cursor.removeSelectedText()

            elif text.startswith("\t"):

                cursor.setPosition(block.position())
                cursor.movePosition(QTextCursor.Right,
                                    QTextCursor.KeepAnchor,
                                    1)
                cursor.removeSelectedText()

            if block == end_block:
                break

            block = block.next()

        cursor.endEditBlock()
        
    def wrap_selection(self, prefix, suffix=None, cursor_offset=0):

        if suffix is None:
            suffix = prefix

        cursor = self.textCursor()
        text = cursor.selectedText()

        if not text:
            return

        cursor.insertText(prefix + text + suffix)

        if cursor_offset:
            cursor.movePosition(QTextCursor.Left,
                                QTextCursor.MoveAnchor,
                                cursor_offset)
            self.setTextCursor(cursor)
            
    def toggle_line_prefix(self, prefix):

        cursor = self.textCursor()

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        doc = self.document()

        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)

        cursor.beginEditBlock()

        block = start_block

        while True:

            text = block.text()

            cursor.setPosition(block.position())

            if text.startswith(prefix):

                cursor.movePosition(
                    QTextCursor.Right,
                    QTextCursor.KeepAnchor,
                    len(prefix)
                )
                cursor.removeSelectedText()

            else:
                cursor.insertText(prefix)

            if block == end_block:
                break

            block = block.next()

        cursor.endEditBlock()
        
    def insert_code_block(self):

        cursor = self.textCursor()
        text = cursor.selectedText()

        block = "```\n"

        if text:
            block += text + "\n"

        block += "```"

        cursor.insertText(block)

        # カーソルを中に置く
        cursor.movePosition(QTextCursor.Up)
        self.setTextCursor(cursor)
        
    def toggle_heading(self):

        cursor = self.textCursor()

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        doc = self.document()

        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)

        cursor.beginEditBlock()

        block = start_block

        while True:

            text = block.text()

            cursor.setPosition(block.position())

            if text.startswith("# "):
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 2)
                cursor.removeSelectedText()
            else:
                cursor.insertText("# ")

            if block == end_block:
                break

            block = block.next()

        cursor.endEditBlock()
        
    def toggle_comment(self):

        cursor = self.textCursor()
        text = cursor.selectedText()

        if not text:
            return

        if text.startswith("<!--") and text.endswith("-->"):
            text = text[4:-3]
        else:
            text = "<!-- " + text + " -->"

        cursor.insertText(text)
 
    def continue_prefix(self):

        cursor = self.textCursor()

        block = cursor.block()
        text = block.text()

        # よくあるMarkdown prefix
        m = re.match(r'^(\s*(?:[-*+] |\d+\. |> ))', text)

        if not m:
            # prefixが無ければ普通の改行
            cursor.insertText("\n")
            return

        prefix = m.group(1)

        cursor.insertText("\n" + prefix)
        
    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self.viewport())

        block = self.firstVisibleBlock()
        offset = self.contentOffset()

        tab_width = self.tabStopDistance()

        while block.isValid():
            rect = self.blockBoundingGeometry(block).translated(offset)

            if not rect.isValid():
                block = block.next()
                continue

            text = block.text()

            # インデント数
            indent = 0
            i = 0
            length = len(text)

            while i < length:

                if text[i] == "\t":
                    indent += 1
                    i += 1

                elif text[i:i+4] == "    ":
                    indent += 1
                    i += 4

                else:
                    break

            # 縦ライン描画
            for i in range(indent):
                base = self.indent_colors[i % len(self.indent_colors)]
                color = QColor(base)
                color.setAlpha(50)

                pen = QPen(color)
                pen.setWidth(1)
                painter.setPen(pen)

                x = int(tab_width * i)

                painter.drawLine(
                    x,
                    int(rect.top()),
                    x,
                    int(rect.bottom())
                )

            block = block.next()
            
    def tree_diagram(self):

        cursor = self.textCursor()

        if not cursor.hasSelection():
            return

        text = cursor.selection().toPlainText()
        lines = text.splitlines()

        def get_indent(line):
            count = 0
            for ch in line:
                if ch == " ":
                    count += 1
                elif ch == "\t":
                    count += 4
                else:
                    break
            return count

        parsed = []
        for line in lines:
            if not line.strip():
                continue

            indent = get_indent(line)
            level = indent // 4
            parsed.append((level, line.strip()))

        result = []
        stack = []

        for i, (level, content) in enumerate(parsed):

            if level == 0:
                result.append(content)
                stack = []
                continue

            # stack調整
            while len(stack) > level:
                stack.pop()

            # 次に同階層があるかチェック
            is_last = True
            for j in range(i + 1, len(parsed)):
                nl, _ = parsed[j]
                if nl == level:
                    is_last = False
                    break
                if nl < level:
                    break

            prefix = ""
            for depth in range(level - 1):
                if depth < len(stack) and stack[depth]:
                    prefix += "│   "
                else:
                    prefix += "    "

            branch = "└─ " if is_last else "├─ "
            result.append(prefix + branch + content)

            if len(stack) <= level - 1:
                stack.append(not is_last)
            else:
                stack[level - 1] = not is_last

        cursor.insertText("\n".join(result))