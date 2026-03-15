from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
import re


class MarkdownHighlighter(QSyntaxHighlighter):

    def __init__(self, document):
        super().__init__(document)

        self.rules = []

        # 見出し
        header = QTextCharFormat()
        header.setForeground(QColor("#569CD6"))
        header.setFontWeight(700)
        self.rules.append((re.compile(r"^#{1,6} .*"), header))

        # リスト
        bullet = QTextCharFormat()
        bullet.setForeground(QColor("#4EC9B0"))
        self.rules.append((re.compile(r"^\s*[-*] "), bullet))

        # bold
        bold = QTextCharFormat()
        bold.setForeground(QColor("#DCDCAA"))
        bold.setFontWeight(700)
        self.rules.append((re.compile(r"\*\*.*?\*\*"), bold))

        # inline code
        code = QTextCharFormat()
        code.setForeground(QColor("#CE9178"))
        self.rules.append((re.compile(r"`.*?`"), code))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end-start, fmt)