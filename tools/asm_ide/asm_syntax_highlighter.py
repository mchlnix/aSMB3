from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from foundry.data_source.assembly_parser import _is_instruction
from tools.asm_ide.named_value_finder import NamedValueFinder

_DEC_NUMBER_REGEX = QRegularExpression("([0-9]+)")
_HEX_NUMBER_REGEX = QRegularExpression("(\$[A-Fa-f0-9]+)")
_BIN_NUMBER_REGEX = QRegularExpression("(\%[0-1]+)")
_CONST_DEF_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\s*\=")
_STRING_REGEX = QRegularExpression('("[^"]*")')
_COMMENT_REGEX = QRegularExpression("(;.*)")
_LABEL_DEF_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:.*")
_CONST_LABEL_CALL_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)")


_DEC_NUMBER_COLOR = QColor.fromRgb(255, 0, 0)
_HEX_NUMBER_COLOR = QColor.fromRgb(150, 150, 0)
_BIN_NUMBER_COLOR = QColor.fromRgb(0, 200, 200)
_CONST_COLOR = QColor.fromRgb(0, 51, 204)
_STRING_COLOR = QColor.fromRgb(255, 153, 0)
_COMMENT_COLOR = QColor.fromRgb(77, 153, 0)
_LABEL_COLOR = QColor.fromRgb(153, 0, 153)

_INSTRUCTION_COLOR = QColor.fromRgb(255, 0, 0)

CLICKABLE_CONST_COLOR = QTextCharFormat()
CLICKABLE_CONST_COLOR.setForeground(_CONST_COLOR)
CLICKABLE_CONST_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

CLICKABLE_LABEL_COLOR = QTextCharFormat()
CLICKABLE_LABEL_COLOR.setForeground(_LABEL_COLOR)
CLICKABLE_LABEL_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

_REGEXS = [
    _DEC_NUMBER_REGEX,
    _HEX_NUMBER_REGEX,
    _BIN_NUMBER_REGEX,
    _CONST_DEF_REGEX,
    _LABEL_DEF_REGEX,
    _CONST_LABEL_CALL_REGEX,
    _STRING_REGEX,
    _COMMENT_REGEX,
]

_COLORS = [
    _DEC_NUMBER_COLOR,
    _HEX_NUMBER_COLOR,
    _BIN_NUMBER_COLOR,
    _CONST_COLOR,
    _LABEL_COLOR,
    _CONST_COLOR,  # Not actually used
    _STRING_COLOR,
    _COMMENT_COLOR,
]


class AsmSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, named_value_finder: NamedValueFinder):
        super(AsmSyntaxHighlighter, self).__init__(parent)

        self.named_value_finder = named_value_finder

        self.const_under_cursor = ""
        self.label_under_cursor = ""

    def highlightBlock(self, line: str, clickable=False):
        if _is_instruction(line):
            start = 0
            end = line.find(" ", start)
            instruction_length = end - start

            self.setFormat(start, instruction_length, _INSTRUCTION_COLOR)

        for expression, color in zip(_REGEXS, _COLORS):
            i = expression.globalMatch(line)
            while i.hasNext():
                match = i.next()

                # skip the 0th capture group, which is the whole match
                for captured_index in range(1, match.lastCapturedIndex() + 1):
                    if expression == _CONST_LABEL_CALL_REGEX:
                        if match.capturedView(captured_index) in [
                            self.const_under_cursor,
                            self.label_under_cursor,
                        ]:
                            if match.capturedView(captured_index) == self.const_under_cursor:
                                self.setFormat(
                                    match.capturedStart(captured_index),
                                    match.capturedLength(captured_index),
                                    CLICKABLE_CONST_COLOR.toCharFormat(),
                                )
                            else:
                                self.setFormat(
                                    match.capturedStart(captured_index),
                                    match.capturedLength(captured_index),
                                    CLICKABLE_LABEL_COLOR.toCharFormat(),
                                )

                                continue
                        else:
                            const_or_label = match.capturedView(captured_index).strip()

                            if const_or_label in self.named_value_finder.constants:
                                color = _CONST_COLOR
                            elif const_or_label in self.named_value_finder.labels:
                                color = _LABEL_COLOR
                            else:
                                continue

                    self.setFormat(match.capturedStart(captured_index), match.capturedLength(captured_index), color)
