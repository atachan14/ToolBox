from PySide6.QtWidgets import QPlainTextEdit,QCompleter
from PySide6.QtCore import Qt,QStringListModel
from PySide6.QtGui import QTextCursor
from .highlighter import MarkdownHighlighter
from core.paths import TABS_DIR
import re

class MarkdownEditor(QPlainTextEdit):
    
    INDENT = "\t"
    PAIRS = {
    "(": ")",
    "[": "]",
    "{": "}",
    '"': '"',
    "_": "_",
}
    SNIPPETS = {
    "table": "| col1 | col2 |\n|------|------|\n| text | text |",
    "img": "![alt](image.png)",
    "link": "[text](url)",
    "code": "```\n\n```",
}
    
    def __init__(self):
        super().__init__()

        MarkdownHighlighter(self.document())
        self.setTabStopDistance(20)
        
        model = QStringListModel(list(self.SNIPPETS.keys()))

        self.completer = QCompleter(model, self)
        self.completer.setWidget(self)
        self.completer.activated.connect(self.insert_snippet)
        
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

        if text in self.PAIRS:

            cursor = self.textCursor()
            close = self.PAIRS[text]

            # 選択あり → wrap
            if cursor.hasSelection():
                selected = cursor.selectedText()
                cursor.insertText(text + selected + close)
                return

            # 次の文字が閉じ記号ならスキップ
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
            next_char = cursor.selectedText()
            cursor.clearSelection()

            if next_char == close:
                cursor.movePosition(QTextCursor.Right)
                self.setTextCursor(cursor)
                return

            # 通常ペア補完
            cursor.insertText(text + close)
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)

            return
        
        if event.modifiers() & Qt.ControlModifier:

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
            
            
        if (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.ShiftModifier):

            if event.key() == Qt.Key_B:
                self.wrap_selection("***")
                return
            if event.key() == Qt.Key_K:
                self.insert_code_block()
                return

        if (event.modifiers() & Qt.ControlModifier) and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.continue_prefix()
            return
        
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Space:
            cursor_rect = self.cursorRect()
            self.completer.complete(cursor_rect)

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
        
    def insert_snippet(self, key):

        snippet = self.SNIPPETS.get(key)

        if not snippet:
            return

        cursor = self.textCursor()

        cursor.insertText(snippet)

        if key == "code":
            cursor.movePosition(QTextCursor.Up)
            self.setTextCursor(cursor)