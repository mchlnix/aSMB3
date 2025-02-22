from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from tools.asm_ide.reference_finder import ReferenceFinder, ReferenceType
from tools.asm_ide.util import is_generic_directive, is_instruction

_DEC_NUMBER_REGEX = QRegularExpression("([0-9]+)")
_HEX_NUMBER_REGEX = QRegularExpression("(\$[A-Fa-f0-9]+)")
_BIN_NUMBER_REGEX = QRegularExpression("(\%[0-1]+)")
_CONST_DEF_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\s*\=")
_DIRECTIVE_REGEX = QRegularExpression("(\.[A-Za-z_][A-Za-z]*)")
_STRING_REGEX = QRegularExpression('("[^"]*")')
_COMMENT_REGEX = QRegularExpression("(;.*)")
_LABEL_DEF_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:")
_CONST_LABEL_CALL_RAM_VAR_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)")


_DEC_NUMBER_COLOR = QColor.fromRgb(255, 0, 0)
_HEX_NUMBER_COLOR = QColor.fromRgb(0x986800)
_BIN_NUMBER_COLOR = QColor.fromRgb(0x2C91AF)
_CONST_COLOR = QColor.fromRgb(0, 51, 204)
_DIRECTIVE_COLOR = QColor.fromRgb(0xA626A4)
_STRING_COLOR = QColor.fromRgb(0x50A14F)
_COMMENT_COLOR = QColor.fromRgb(0xA0A1A7)
_LABEL_COLOR = QColor.fromRgb(0xA626A4)
_RAM_VARIABLE_COLOR = QColor.fromRgb(0xE45649)

_INSTRUCTION_COLOR = QColor.fromRgb(0x3E4047)

_DEFAULT_TEXT_COLOR = QColor.fromRgb(0x383A42)


_CLICKABLE_CONST_COLOR = QTextCharFormat()
_CLICKABLE_CONST_COLOR.setForeground(_CONST_COLOR)
_CLICKABLE_CONST_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

_CLICKABLE_LABEL_COLOR = QTextCharFormat()
_CLICKABLE_LABEL_COLOR.setForeground(_LABEL_COLOR)
_CLICKABLE_LABEL_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

_CLICKABLE_RAM_VAR_COLOR = QTextCharFormat()
_CLICKABLE_RAM_VAR_COLOR.setForeground(_RAM_VARIABLE_COLOR)
_CLICKABLE_RAM_VAR_COLOR.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

_REGEXS = [
    _DEC_NUMBER_REGEX,
    _HEX_NUMBER_REGEX,
    _BIN_NUMBER_REGEX,
    _CONST_DEF_REGEX,
    _DIRECTIVE_REGEX,
    _LABEL_DEF_REGEX,
    _CONST_LABEL_CALL_RAM_VAR_REGEX,
    _STRING_REGEX,
    _COMMENT_REGEX,
]

_COLORS = [
    _DEC_NUMBER_COLOR,
    _HEX_NUMBER_COLOR,
    _BIN_NUMBER_COLOR,
    _CONST_COLOR,
    _DIRECTIVE_COLOR,
    _LABEL_COLOR,
    _CONST_COLOR,  # Not actually used, this will be coloured, depending on what is found
    _STRING_COLOR,
    _COMMENT_COLOR,
]


class AsmSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, reference_finder: ReferenceFinder):
        super(AsmSyntaxHighlighter, self).__init__(parent)

        self._reference_finder = reference_finder

        # todo: with ReferenceType, this should be reducible to one member
        self.const_under_cursor = ""
        self.ram_variable_under_cursor = ""
        self.label_under_cursor = ""

    def highlightBlock(self, line: str, clickable=False):
        self.setFormat(0, len(line) - 1, _DEFAULT_TEXT_COLOR)
        if is_instruction(line):
            start = 0
            end = line.find(" ", start)
            instruction_length = end - start

            self.setFormat(start, instruction_length, _INSTRUCTION_COLOR)

        if is_generic_directive(line.strip()):
            start = line.find(".")
            end = line.find(" ", start)
            directive_length = end - start

            self.setFormat(start, directive_length, _DIRECTIVE_COLOR)

        for expression, color in zip(_REGEXS, _COLORS):
            match_iterator = expression.globalMatch(line)

            while match_iterator.hasNext():
                match = match_iterator.next()

                # skip the 0th capture group, which is the whole match
                for captured_index in range(1, match.lastCapturedIndex() + 1):
                    # intervene, if this is a constant, ram variable or label under the mouse cursor
                    if expression != _CONST_LABEL_CALL_RAM_VAR_REGEX:
                        self.setFormat(match.capturedStart(captured_index), match.capturedLength(captured_index), color)

                    if match.capturedView(captured_index) in [
                        self.const_under_cursor,
                        self.ram_variable_under_cursor,
                        self.label_under_cursor,
                    ]:
                        if match.capturedView(captured_index) == self.const_under_cursor:
                            text_format = _CLICKABLE_CONST_COLOR
                        elif match.capturedView(captured_index) == self.ram_variable_under_cursor:
                            text_format = _CLICKABLE_RAM_VAR_COLOR
                        else:
                            text_format = _CLICKABLE_LABEL_COLOR

                        self.setFormat(
                            match.capturedStart(captured_index),
                            match.capturedLength(captured_index),
                            text_format.toCharFormat(),
                        )

                        continue

                    const_ram_or_label = match.capturedView(captured_index).strip()

                    if const_ram_or_label not in self._reference_finder.definitions:
                        continue

                    *_, nv_type, _ = self._reference_finder.definitions[const_ram_or_label]

                    if nv_type == ReferenceType.CONSTANT:
                        color = _CONST_COLOR
                    elif nv_type == ReferenceType.RAM_VAR:
                        color = _RAM_VARIABLE_COLOR
                    elif nv_type == ReferenceType.LABEL:
                        color = _LABEL_COLOR
                    else:
                        continue

                    self.setFormat(match.capturedStart(captured_index), match.capturedLength(captured_index), color)
