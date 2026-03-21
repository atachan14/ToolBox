from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
import re


class MarkdownHighlighter(QSyntaxHighlighter):

    def __init__(self, document):
        super().__init__(document)

        self.rules = []
        self.bullet_pattern = re.compile(r"^(\s*)([-*+])(?=\s)")
        self.ordered_list_pattern = re.compile(r"^(\s*)(\d+\.)(?=\s)")

        # 見出し
        header = QTextCharFormat()
        header.setForeground(QColor("#569CD6"))
        header.setFontWeight(700)
        self.rules.append((re.compile(r"^#{1,6} .*"), header))

        # リスト
        bullet = QTextCharFormat()
        bullet.setForeground(QColor("#4EC9B0"))
        self.bullet_format = bullet

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
        bullet_match = self.bullet_pattern.match(text)
        if bullet_match:
            start, end = bullet_match.span(2)
            self.setFormat(start, end - start, self.bullet_format)

        ordered_match = self.ordered_list_pattern.match(text)
        if ordered_match:
            start, end = ordered_match.span(2)
            self.setFormat(start, end - start, self.bullet_format)

        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)
